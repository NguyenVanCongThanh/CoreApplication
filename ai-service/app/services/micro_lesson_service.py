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
from app.core.llm_gateway import TASK_MICRO_LESSON_GEN
from app.services.chunker import detect_language

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Constants tuned for "5 minutes of reading" ───────────────────────────────
# Average Vietnamese reader: ~200 wpm; "5 minutes" ≈ 1000 words.
# We aim for 700–1100 words per lesson (LLM has wiggle room).
WORDS_PER_MINUTE = 200


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
    node_id: Optional[int] = None


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
        if not source_content_id:
            await self._post_status(job_id, "failed", 0, "missing_content_id", 0, "Yêu cầu phải có source_content_id")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 5, "checking_index", 0, "")

        from app.core.database import get_ai_conn
        from app.services.auto_index_service import auto_index_service

        is_indexed = False
        async with get_ai_conn() as conn:
            row = await conn.fetchrow("SELECT id FROM knowledge_nodes WHERE source_content_id=$1 LIMIT 1", source_content_id)
            is_indexed = row is not None

        if not is_indexed:
            await self._post_status(job_id, "processing", 10, "auto_indexing", 0, "")
            file_bytes = await auto_index_service._download_bytes(source_file_path)
            if not file_bytes:
                await self._post_status(job_id, "failed", 0, "download_failed", 0, "Không tải được file nguồn")
                return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

            from app.services.auto_index_service import _detect_file_type
            file_type = _detect_file_type(source_file_path, source_file_type)
            try:
                if file_type == "text":
                    text_content = file_bytes.decode("utf-8", errors="replace")
                    await auto_index_service.auto_index_text(
                        content_id=source_content_id, course_id=course_id, title="", text_content=text_content
                    )
                else:
                    await auto_index_service.auto_index(
                        content_id=source_content_id, course_id=course_id, file_url=source_file_path,
                        content_type=file_type, file_bytes=file_bytes
                    )
            except Exception as exc:
                logger.error("Auto index failed: %s", exc)
                await self._post_status(job_id, "failed", 0, "index_failed", 0, str(exc))
                return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 50, "fetching_nodes", 0, "")
        nodes_with_chunks = await self._fetch_nodes_and_chunks(source_content_id)
        if not nodes_with_chunks:
            await self._post_status(job_id, "failed", 0, "no_nodes", 0, "Không tìm thấy Node kiến thức nào từ tài liệu này")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 60, "generating_lessons", len(nodes_with_chunks), "")

        lessons = []
        for i, item in enumerate(nodes_with_chunks):
            lesson = await self._generate_lesson_for_node(
                node=item["node"],
                chunks=item["chunks"],
                target_minutes=target_minutes,
                language=language,
                order_index=i,
            )
            if lesson:
                lessons.append(lesson)
            progress = 60 + int(30 * (i + 1) / len(nodes_with_chunks))
            await self._post_status(job_id, "processing", progress, "generating_lessons", len(nodes_with_chunks), "")

        if not lessons:
            await self._post_status(job_id, "failed", 0, "split_failed", 0, "LLM không tạo được bài học nào")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 95, "saving", len(lessons), "")
        await self._post_lessons(job_id, course_id, section_id, source_content_id, lessons, language)
        await self._post_status(job_id, "completed", 100, "done", len(lessons), "")
        return GenerationResult(job_id=job_id, course_id=course_id, lessons=lessons, language=language)

    async def generate_from_youtube(
        self,
        *,
        job_id: int,
        course_id: int,
        section_id: Optional[int],
        source_content_id: Optional[int],
        youtube_url: str,
        target_minutes: int = 5,
        language: str = "vi",
    ) -> GenerationResult:
        if not source_content_id:
            await self._post_status(job_id, "failed", 0, "missing_content_id", 0, "Yêu cầu phải có source_content_id")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 5, "checking_index", 0, "")
        from app.core.database import get_ai_conn
        from app.services.auto_index_service import auto_index_service

        is_indexed = False
        async with get_ai_conn() as conn:
            row = await conn.fetchrow("SELECT id FROM knowledge_nodes WHERE source_content_id=$1 LIMIT 1", source_content_id)
            is_indexed = row is not None

        if not is_indexed:
            await self._post_status(job_id, "processing", 10, "auto_indexing", 0, "")
            try:
                await auto_index_service.auto_index(
                    content_id=source_content_id, course_id=course_id, file_url=youtube_url,
                    content_type="video/youtube", file_bytes=b""
                )
            except Exception as exc:
                logger.error("Auto index failed: %s", exc)
                await self._post_status(job_id, "failed", 0, "index_failed", 0, str(exc))
                return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 50, "fetching_nodes", 0, "")
        nodes_with_chunks = await self._fetch_nodes_and_chunks(source_content_id)
        if not nodes_with_chunks:
            await self._post_status(job_id, "failed", 0, "no_nodes", 0, "Không tìm thấy Node kiến thức nào từ tài liệu này")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 60, "generating_lessons", len(nodes_with_chunks), "")

        lessons = []
        for i, item in enumerate(nodes_with_chunks):
            lesson = await self._generate_lesson_for_node(
                node=item["node"], chunks=item["chunks"], target_minutes=target_minutes, language=language, order_index=i,
            )
            if lesson:
                lessons.append(lesson)
            progress = 60 + int(30 * (i + 1) / len(nodes_with_chunks))
            await self._post_status(job_id, "processing", progress, "generating_lessons", len(nodes_with_chunks), "")

        if not lessons:
            await self._post_status(job_id, "failed", 0, "split_failed", 0, "LLM không tạo được bài học nào")
            return GenerationResult(job_id=job_id, course_id=course_id, lessons=[], language=language)

        await self._post_status(job_id, "processing", 95, "saving", len(lessons), "")
        await self._post_lessons(job_id, course_id, section_id, source_content_id, lessons, language)
        await self._post_status(job_id, "completed", 100, "done", len(lessons), "")
        return GenerationResult(job_id=job_id, course_id=course_id, lessons=lessons, language=language)

    async def _fetch_nodes_and_chunks(self, source_content_id: int) -> list[dict]:
        from app.core.database import get_ai_conn
        async with get_ai_conn() as conn:
            nodes_rows = await conn.fetch(
                "SELECT id, name, description FROM knowledge_nodes WHERE source_content_id=$1 ORDER BY id", 
                source_content_id
            )
            if not nodes_rows:
                return []
            
            chunks_rows = await conn.fetch(
                "SELECT node_id, chunk_text FROM document_chunks WHERE content_id=$1 ORDER BY chunk_index",
                source_content_id
            )
            
            node_map = {}
            for row in nodes_rows:
                node_map[row["id"]] = {
                    "node": {"id": row["id"], "name": row["name"], "description": row["description"]},
                    "chunks": [],
                }
            
            for row in chunks_rows:
                nid = row["node_id"]
                if nid in node_map:
                    node_map[nid]["chunks"].append(row["chunk_text"])
            
            return [n for n in node_map.values() if n["chunks"]]

    async def _generate_lesson_for_node(
        self,
        node: dict,
        chunks: list[str],
        target_minutes: int,
        language: str,
        order_index: int,
    ) -> Optional[GeneratedLesson]:
        markdown_doc = "\n\n".join(chunks)
        truncated = _truncate_markdown(markdown_doc, max_chars=15_000)

        # Extract image URLs
        valid_image_urls = sorted(list({u for u in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", truncated)}))
        image_lines = "\n".join(f"- {url}" for url in valid_image_urls)

        target_words = target_minutes * WORDS_PER_MINUTE
        sys_msg = _SPLITTER_SYSTEM_VI if language == "vi" else _SPLITTER_SYSTEM_EN
        
        user_msg = (
            f"Bạn cần viết một bài học Micro-lesson (thời lượng ~{target_minutes} phút, ~{target_words} từ) "
            f"cho chủ đề sau:\n"
            f"TÊN CHỦ ĐỀ: {node['name']}\n"
            f"MÔ TẢ: {node['description']}\n\n"
            "## YÊU CẦU\n"
            "1. Dựa trên TÀI LIỆU NGUỒN bên dưới, hãy viết một bài học hoàn chỉnh.\n"
            "2. Trả về JSON theo schema yêu cầu.\n"
            "3. Khi minh họa, hãy chèn ảnh bằng Markdown (ví dụ: ![mô tả](URL)). Chỉ dùng các URL có trong TÀI LIỆU NGUỒN hoặc danh sách AVAILABLE IMAGES.\n"
            "4. Văn phong học thuật, dễ hiểu.\n\n"
            f"## AVAILABLE IMAGES\n{image_lines or '(không có ảnh)'}\n\n"
            "## SCHEMA JSON BẮT BUỘC\n"
            "{\n"
            '  "title": "string",\n'
            '  "summary": "string",\n'
            '  "objectives": ["string", ...],\n'
            '  "markdown_content": "string",\n'
            '  "estimated_minutes": 5,\n'
            '  "image_urls": ["..."]\n'
            "}\n\n"
            "## TÀI LIỆU NGUỒN (Markdown)\n"
            f"{truncated}\n"
        )

        try:
            result = await chat_complete_json(
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                model=settings.quiz_model,
                temperature=0.25,
                max_tokens=4000,
                task=TASK_MICRO_LESSON_GEN,
            )
        except Exception as exc:
            logger.error("Lesson generation LLM failed: %s", exc)
            return None

        if not isinstance(result, dict):
            return None

        md = (result.get("markdown_content") or "").strip()
        title = (result.get("title") or "").strip()
        if not md or not title:
            return None

        md = _strip_unknown_image_urls(md, set(valid_image_urls))
        referenced = sorted({u for u in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", md) if u in valid_image_urls})

        objectives = result.get("objectives") or []
        if not isinstance(objectives, list):
            objectives = [str(objectives)]
        objectives = [str(o).strip() for o in objectives if str(o).strip()][:6]

        est_min = result.get("estimated_minutes") or target_minutes
        try:
            est_min = max(2, min(15, int(est_min)))
        except:
            est_min = target_minutes

        return GeneratedLesson(
            title=title[:500],
            summary=(result.get("summary") or "").strip()[:500],
            objectives=objectives,
            markdown_content=md,
            estimated_minutes=est_min,
            image_urls=referenced,
            order_index=order_index,
            node_id=node["id"],
        )

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
                    "node_id": l.node_id,
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