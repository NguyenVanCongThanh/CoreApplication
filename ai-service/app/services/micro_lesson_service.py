"""
ai-service/app/services/micro_lesson_service.py

Generate bite-sized (~5 minute) Markdown lessons from a teacher-uploaded
file (PDF/DOCX/PPTX/XLSX/Image) or a YouTube URL.

Pipeline
--------
  1. Download the source from MinIO (or fetch the YouTube transcript).
  2. Convert to a normalised Markdown document (file_to_markdown), which
     also extracts embedded images to MinIO.
  3. Ask an LLM to split the document into N semantic micro-lessons,
     each ~5 minutes of reading time. The LLM is allowed (and guided)
     to reuse the inline image URLs that already exist in the Markdown.
  4. POST each generated lesson back to the LMS via callback so they
     appear instantly in the teacher's UI as drafts.

The LMS owns the canonical lesson rows; this service only computes them
and pushes via HTTP. Status updates flow back through the same callback
endpoint, keeping the data ownership boundary clean.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.llm import chat_complete_json
from app.core.llm_gateway import TASK_QUIZ_GEN
from app.services.chunker import detect_language

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Constants tuned for "5 minutes of reading" ───────────────────────────────
# Average Vietnamese reader: ~200 wpm; "5 minutes" ≈ 1000 words.
# We aim for 700–1100 words per lesson (LLM has wiggle room).
WORDS_PER_MINUTE = 200
MAX_LESSONS_PER_DOC = 25
MIN_LESSONS_PER_DOC = 1


# ── Prompt builders ──────────────────────────────────────────────────────────

_SPLITTER_SYSTEM_VI = (
    "Bạn là chuyên gia thiết kế chương trình micro-learning. Nhiệm vụ của bạn "
    "là biến tài liệu dài thành chuỗi các bài học nhỏ, mỗi bài 4–6 phút đọc "
    "(khoảng 700–1100 từ). Mỗi bài phải hoàn chỉnh về mặt khái niệm — học viên "
    "đọc một bài là hiểu trọn ý đó, không cần đọc bài khác. Luôn trả về JSON "
    "đúng schema được yêu cầu, không kèm văn bản giải thích."
)

_SPLITTER_SYSTEM_EN = (
    "You are an expert micro-learning curriculum designer. Your job is to "
    "split a long document into a sequence of short, self-contained lessons, "
    "each 4–6 minutes of reading (~700–1100 words). Each lesson must be "
    "conceptually complete — a learner should grasp the idea from one lesson "
    "without needing the others. Always return JSON matching the requested "
    "schema, with no extra commentary."
)


def _build_splitter_prompt(
    *,
    markdown_doc: str,
    target_minutes: int,
    target_lessons: int,
    available_images: list[dict],
    language: str,
) -> str:
    target_words = target_minutes * WORDS_PER_MINUTE
    image_lines = ""
    if available_images:
        image_lines = "\n".join(
            f"- ({img['url']}) trang {img.get('page_number') or '?'}, gợi ý: {img.get('caption_hint') or 'không có'}"
            for img in available_images[:40]
        )

    if language == "vi":
        return (
            f"Tài liệu sau đây cần được chia thành {target_lessons} bài học micro, "
            f"mỗi bài tương đương khoảng {target_minutes} phút đọc (~{target_words} từ).\n\n"
            "## YÊU CẦU\n"
            "1. Cắt theo ranh giới khái niệm — không cắt giữa câu/đoạn quan trọng.\n"
            "2. Mỗi bài học có:\n"
            "   - title: tiêu đề ngắn gọn (≤ 80 ký tự).\n"
            "   - summary: tóm tắt 1–2 câu (~30 từ).\n"
            "   - objectives: 2–4 mục tiêu học cụ thể, đo được.\n"
            "   - markdown_content: thân bài viết bằng Markdown, có heading ##/###, "
            "danh sách, bảng, công thức nếu cần. KHÔNG lặp lại title.\n"
            "   - estimated_minutes: số phút đọc ước tính (3–7).\n"
            "   - image_urls: mảng URL ảnh từ danh sách bên dưới mà bài này có dùng.\n"
            "3. Khi muốn minh họa, hãy chèn ảnh bằng cú pháp Markdown ![mô tả](URL) "
            "DÙNG ĐÚNG URL trong danh sách 'AVAILABLE IMAGES' bên dưới — không bịa URL.\n"
            "4. Bài học phải đứng độc lập: định nghĩa lại ký hiệu/biến số nếu cần.\n"
            "5. Văn phong tiếng Việt rõ ràng, học thuật nhưng dễ tiếp cận.\n\n"
            f"## AVAILABLE IMAGES\n{image_lines or '(không có ảnh)'}\n\n"
            "## SCHEMA JSON BẮT BUỘC\n"
            "{\n"
            '  "lessons": [\n'
            "    {\n"
            '      "title": "string",\n'
            '      "summary": "string",\n'
            '      "objectives": ["string", ...],\n'
            '      "markdown_content": "string",\n'
            '      "estimated_minutes": 5,\n'
            '      "image_urls": ["..."]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "## TÀI LIỆU NGUỒN (Markdown)\n"
            f"{markdown_doc}\n"
        )
    return (
        f"The following document must be split into {target_lessons} micro-lessons, "
        f"each ~{target_minutes} minutes of reading (~{target_words} words).\n\n"
        "## REQUIREMENTS\n"
        "1. Split on conceptual boundaries — never mid-sentence.\n"
        "2. Each lesson must include:\n"
        "   - title: concise title (≤ 80 chars).\n"
        "   - summary: 1–2 sentences (~30 words).\n"
        "   - objectives: 2–4 specific, measurable learning objectives.\n"
        "   - markdown_content: lesson body in Markdown with ##/### headings, "
        "lists, tables, formulas as needed. Do NOT repeat the title.\n"
        "   - estimated_minutes: 3–7.\n"
        "   - image_urls: array of URLs (from list below) used in this lesson.\n"
        "3. When illustrating, embed images as ![alt](URL) using EXACT URLs from "
        "the AVAILABLE IMAGES list — do not invent URLs.\n"
        "4. Lessons must be self-contained: redefine variables/symbols if needed.\n"
        "5. Clear, academic but accessible English.\n\n"
        f"## AVAILABLE IMAGES\n{image_lines or '(no images)'}\n\n"
        "## REQUIRED JSON SCHEMA\n"
        "{\n"
        '  "lessons": [\n'
        "    {\n"
        '      "title": "string",\n'
        '      "summary": "string",\n'
        '      "objectives": ["string", ...],\n'
        '      "markdown_content": "string",\n'
        '      "estimated_minutes": 5,\n'
        '      "image_urls": ["..."]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "## SOURCE DOCUMENT (Markdown)\n"
        f"{markdown_doc}\n"
    )


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class GeneratedLesson:
    title: str
    summary: str
    objectives: list[str]
    markdown_content: str
    estimated_minutes: int
    image_urls: list[str]
    order_index: int


@dataclass
class GenerationResult:
    job_id: int
    course_id: int
    lessons: list[GeneratedLesson]
    language: str


# ── Service ──────────────────────────────────────────────────────────────────

class MicroLessonService:

    async def generate_from_file(
        self,
        *,
        job_id: int,
        course_id: int,
        section_id: Optional[int],
        source_content_id: Optional[int],
        source_file_path: str,
        source_file_type: str,
        target_minutes: int = 5,
        language: str = "vi",
    ) -> GenerationResult:
        """Main entry: download → convert → split → callback."""
        await self._post_status(job_id, "processing", 5, "downloading", 0, "")

        from app.services.auto_index_service import _detect_file_type

        # ── 1) Download source bytes ─────────────────────────────────────
        from app.services.auto_index_service import auto_index_service
        file_bytes = await auto_index_service._download_bytes(source_file_path)
        if not file_bytes:
            await self._post_status(job_id, "failed", 0, "download_failed", 0,
                                    "Không tải được file nguồn")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 25, "extracting", 0, "")

        # ── 2) Convert to Markdown ───────────────────────────────────────
        from app.services.file_to_markdown import convert_to_markdown

        file_type = _detect_file_type(source_file_path, source_file_type or "")
        storage_prefix = f"micro-lesson/{course_id}/{job_id}"
        converted = await convert_to_markdown(
            file_bytes=file_bytes,
            file_type=file_type,
            storage_prefix=storage_prefix,
            language=language,
        )

        if not converted.markdown.strip():
            await self._post_status(job_id, "failed", 0, "empty_doc", 0,
                                    "Tài liệu rỗng sau khi trích xuất")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 55, "splitting", 0, "")

        # Auto-detect language if caller didn't specify
        if not language:
            language = detect_language(converted.markdown[:3000])

        lessons = await self._split_into_lessons(
            converted.markdown, converted.images, target_minutes, language,
        )

        if not lessons:
            await self._post_status(job_id, "failed", 0, "split_failed", 0,
                                    "LLM không tạo được bài học")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 85, "saving", len(lessons), "")

        # ── 4) Push lessons back to LMS ──────────────────────────────────
        await self._post_lessons(job_id, course_id, section_id, source_content_id, lessons, language)

        await self._post_status(job_id, "completed", 100, "done", len(lessons), "")
        return GenerationResult(job_id=job_id, course_id=course_id, lessons=lessons, language=language)

    async def generate_from_youtube(
        self,
        *,
        job_id: int,
        course_id: int,
        section_id: Optional[int],
        youtube_url: str,
        target_minutes: int = 5,
        language: str = "vi",
    ) -> GenerationResult:
        """Alternative entry: pull YouTube transcript and treat it as the doc."""
        await self._post_status(job_id, "processing", 10, "fetching_transcript", 0, "")

        from app.services.youtube_service import youtube_fetcher

        try:
            transcript = await youtube_fetcher.fetch(youtube_url, preferred_language=language)
        except Exception as exc:
            logger.error("YouTube fetch failed: %s", exc, exc_info=True)
            await self._post_status(job_id, "failed", 0, "youtube_failed", 0, str(exc)[:300])
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        segments = transcript.get("segments", [])
        if not segments:
            await self._post_status(job_id, "failed", 0, "empty_transcript", 0, "Transcript rỗng")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        # Stitch transcript into Markdown with timestamp anchors so the
        # splitter can refer back to time ranges.
        md_parts: list[str] = ["# Bản ghi video YouTube\n"]
        for seg in segments:
            start = int(seg.get("start", 0))
            text = seg.get("text", "").strip()
            if text:
                md_parts.append(f"- [{_fmt_ts(start)}] {text}")
        markdown = "\n".join(md_parts)
        language = transcript.get("language") or language

        await self._post_status(job_id, "processing", 55, "splitting", 0, "")

        lessons = await self._split_into_lessons(markdown, [], target_minutes, language)
        if not lessons:
            await self._post_status(job_id, "failed", 0, "split_failed", 0, "Không tạo được bài học")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 85, "saving", len(lessons), "")
        await self._post_lessons(job_id, course_id, section_id, None, lessons, language)
        await self._post_status(job_id, "completed", 100, "done", len(lessons), "")
        return GenerationResult(job_id=job_id, course_id=course_id, lessons=lessons, language=language)

    # ── Splitting via LLM ────────────────────────────────────────────────

    async def _split_into_lessons(
        self,
        markdown_doc: str,
        images,
        target_minutes: int,
        language: str,
    ) -> list[GeneratedLesson]:
        word_count = len(markdown_doc.split())
        target_words = target_minutes * WORDS_PER_MINUTE
        target_lessons = max(
            MIN_LESSONS_PER_DOC,
            min(MAX_LESSONS_PER_DOC, round(word_count / max(1, target_words))),
        )

        # If the doc is gigantic we still need to fit into the model context.
        # Keep ~25k chars of source — ~6k tokens — and let the LLM rely on
        # the heading structure that file_to_markdown already produced.
        truncated = _truncate_markdown(markdown_doc, max_chars=25_000)

        image_specs = [
            {
                "url": img.url,
                "page_number": img.page_number,
                "caption_hint": img.caption_hint,
            }
            for img in (images or [])
        ]

        system = _SPLITTER_SYSTEM_VI if language == "vi" else _SPLITTER_SYSTEM_EN
        user = _build_splitter_prompt(
            markdown_doc=truncated,
            target_minutes=target_minutes,
            target_lessons=target_lessons,
            available_images=image_specs,
            language=language,
        )

        try:
            result = await chat_complete_json(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=settings.quiz_model,
                temperature=0.25,
                max_tokens=8000,
                task=TASK_QUIZ_GEN,
            )
        except Exception as exc:
            logger.error("Lesson splitter LLM failed: %s", exc, exc_info=True)
            return []

        raw_lessons = result.get("lessons") if isinstance(result, dict) else result
        if not isinstance(raw_lessons, list):
            return []

        valid_image_urls = {img.url for img in (images or [])}
        lessons: list[GeneratedLesson] = []
        for i, raw in enumerate(raw_lessons[:MAX_LESSONS_PER_DOC]):
            if not isinstance(raw, dict):
                continue
            md = (raw.get("markdown_content") or "").strip()
            title = (raw.get("title") or "").strip()
            if not md or not title:
                continue

            # Sanitize image URLs in markdown — the LLM occasionally invents URLs
            md = _strip_unknown_image_urls(md, valid_image_urls)
            referenced = sorted({u for u in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", md)
                                 if u in valid_image_urls})

            objectives = raw.get("objectives") or []
            if not isinstance(objectives, list):
                objectives = [str(objectives)]
            objectives = [str(o).strip() for o in objectives if str(o).strip()][:6]

            est_min = raw.get("estimated_minutes") or target_minutes
            try:
                est_min = max(2, min(15, int(est_min)))
            except Exception:
                est_min = target_minutes

            lessons.append(GeneratedLesson(
                title=title[:500],
                summary=(raw.get("summary") or "").strip()[:500],
                objectives=objectives,
                markdown_content=md,
                estimated_minutes=est_min,
                image_urls=referenced,
                order_index=i,
            ))
        return lessons

    # ── HTTP callback into LMS ───────────────────────────────────────────

    async def _post_lessons(
        self,
        job_id: int,
        course_id: int,
        section_id: Optional[int],
        source_content_id: Optional[int],
        lessons: list[GeneratedLesson],
        language: str,
    ) -> None:
        payload = {
            "job_id": job_id,
            "course_id": course_id,
            "section_id": section_id,
            "source_content_id": source_content_id,
            "language": language,
            "lessons": [
                {
                    "title": l.title,
                    "summary": l.summary,
                    "objectives": l.objectives,
                    "markdown_content": l.markdown_content,
                    "estimated_minutes": l.estimated_minutes,
                    "image_urls": l.image_urls,
                    "order_index": l.order_index,
                }
                for l in lessons
            ],
        }
        await self._lms_post("/api/v1/internal/micro-lessons/lessons", payload)

    async def _post_status(
        self,
        job_id: int,
        status: str,
        progress: int,
        stage: str,
        lessons_count: int,
        error: str,
    ) -> None:
        await self._lms_post("/api/v1/internal/micro-lessons/status", {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "stage": stage,
            "lessons_count": lessons_count,
            "error": error,
        })

    async def _lms_post(self, path: str, body: dict) -> None:
        url = settings.lms_service_url.rstrip("/") + path
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers={"X-API-Secret": settings.ai_service_secret},
                )
                if resp.status_code >= 400:
                    logger.warning("LMS callback %s → %d: %s", path, resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("LMS callback %s failed: %s", path, exc)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_ts(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _truncate_markdown(md: str, max_chars: int) -> str:
    if len(md) <= max_chars:
        return md
    head = md[: max_chars // 2]
    tail = md[-max_chars // 2:]
    return f"{head}\n\n[…đã rút gọn để vừa context window…]\n\n{tail}"


def _strip_unknown_image_urls(md: str, valid_urls: set[str]) -> str:
    """Replace ![alt](url) where url isn't in the valid set with bare alt text."""
    def _sub(m: re.Match) -> str:
        url = m.group(2)
        if url in valid_urls:
            return m.group(0)
        alt = m.group(1).strip() or "hình minh họa"
        return f"_({alt})_"

    return re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", _sub, md)


# Singleton
micro_lesson_service = MicroLessonService()