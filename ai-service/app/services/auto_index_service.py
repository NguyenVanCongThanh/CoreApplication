from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from app.core.config import get_settings
from app.core.database import get_async_conn
from app.core.llm import chat_complete_json, create_embeddings_batch
from app.services.chunker import (
    PDFChunker,
    DocxChunker,
    PptxChunker,
    ExcelChunker,
    MarkdownChunker,
    ImageChunker,
    VideoTranscriptChunker,
    DocumentChunk,
    detect_language,
    sanitize_text,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Tuning constants ──────────────────────────────────────────────────────────
RELATION_SIMILARITY_THRESHOLD = 0.62
MAX_NODES_PER_DOCUMENT = 8
MIN_NODES_PER_DOCUMENT = 2
EMBED_BATCH_SIZE = 16
MAX_EXCERPT_CHARS = 9000
MAX_EXISTING_NODES_FOR_GRAPH = 200

# Node deduplication thresholds
DEDUP_HARD_THRESHOLD = 0.92   # >= this → reuse exact existing node
DEDUP_SOFT_THRESHOLD = 0.80   # >= this → merge description into existing node


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ExtractedNode:
    name: str
    name_vi: str
    name_en: str
    description: str
    keywords: list[str]
    order_index: int


@dataclass
class ExtractedRelation:
    source_index: int
    target_index: int
    relation_type: str   # 'prerequisite' | 'related'
    reason: str
    strength: float = 0.85


# ── LLM prompts (unchanged from original) ─────────────────────────────────────

NODE_EXTRACTION_SYSTEM = """\
Bạn là chuyên gia phân tích giáo trình đại học và thiết kế chương trình học.
Nhiệm vụ: đọc tài liệu học thuật và xác định cấu trúc kiến thức của nó.
Nguyên tắc:
- Mỗi node là MỘT khái niệm/kỹ năng có thể dạy và kiểm tra độc lập.
- Không quá chung (ví dụ: "Lập trình") mà cũng không quá chi tiết (ví dụ: "Cú pháp dòng 5").
- Description phải đủ để viết được 3-5 câu hỏi trắc nghiệm.
- Quan hệ prerequisite chỉ khi thực sự CẦN THIẾT để học node kia.
CHỈ trả về JSON hợp lệ, không thêm bất kỳ text nào khác ngoài JSON.\
"""


def build_node_extraction_prompt(
    document_excerpt: str,
    file_type: str,
    language: str,
    doc_title: Optional[str],
    detected_headings: list[str],
    max_nodes: int,
) -> str:
    lang_hint = "Tên chủ đề ưu tiên tiếng Việt" if language == "vi" else "Topic names in English preferred"
    file_hint_map = {
        "pdf":   "tài liệu PDF (có thể là giáo trình, bài giảng, báo cáo)",
        "docx":  "tài liệu Word (có thể là giáo án, bài viết học thuật)",
        "pptx":  "bản trình chiếu PowerPoint (mỗi slide thường là 1 ý chính)",
        "xlsx":  "bảng tính Excel (dữ liệu có cấu trúc, chú ý headers và labels)",
        "text":  "tài liệu Markdown (có thể có hình ảnh, bảng, code; headings đã được giữ nguyên)",
        "image": "hình ảnh đã được mô tả bằng ngôn ngữ tự nhiên",
        "video": "transcript video bài giảng (chú ý mốc thời gian và chủ đề chuyển đổi)",
        "txt":   "file văn bản thuần (chú ý cấu trúc đoạn văn)",
    }
    file_hint = file_hint_map.get(file_type, "tài liệu học tập")

    heading_context = ""
    if detected_headings:
        tops = detected_headings[:20]
        heading_context = "\nCÁC TIÊU ĐỀ/HEADING PHÁT HIỆN ĐƯỢC:\n" + "\n".join(
            f"  - {h}" for h in tops
        ) + "\n"

    title_context = f"\nTIÊU ĐỀ TÀI LIỆU: {doc_title}\n" if doc_title else ""

    schema = """{
  "nodes": [
    {
      "name_vi": "Tên chủ đề tiếng Việt",
      "name_en": "English topic name",
      "description": "Mô tả 2-3 câu về nội dung cụ thể trong tài liệu này",
      "keywords": ["từ khóa 1", "từ khóa 2", "từ khóa 3", "từ khóa 4"]
    }
  ],
  "prerequisites": [
    {
      "source_index": 0,
      "target_index": 2,
      "relation_type": "prerequisite",
      "reason": "Lý do ngắn gọn tại sao cần học node 0 trước node 2",
      "strength": 0.9
    }
  ]
}"""

    return f"""\
Loại tài liệu: {file_hint}
{title_context}{heading_context}
NHIỆM VỤ:
1. Xác định ĐÚNG {max_nodes} chủ đề kiến thức quan trọng nhất từ tài liệu.
2. Xác định các quan hệ prerequisite giữa chúng (chỉ tạo nếu thực sự cần thiết).
{lang_hint}.

NỘI DUNG TÀI LIỆU:
{document_excerpt}

Trả về JSON theo schema (không thêm bất kỳ text nào ngoài JSON):
{schema}"""


# ── File type detection ────────────────────────────────────────────────────────

def _detect_file_type(file_url: str, content_type: str) -> str:
    url_lower = file_url.lower()
    ct_lower = content_type.lower()

    if url_lower.endswith(".pdf") or "pdf" in ct_lower:
        return "pdf"
    if url_lower.endswith((".docx", ".doc")) or "word" in ct_lower:
        return "docx"
    if url_lower.endswith((".pptx", ".ppt")) or "presentation" in ct_lower:
        return "pptx"
    if url_lower.endswith((".xlsx", ".xls")) or "spreadsheet" in ct_lower or "excel" in ct_lower:
        return "xlsx"
    if url_lower.endswith((".mp4", ".webm", ".mov", ".avi")) or "video" in ct_lower:
        return "video"
    # TEXT / MARKDOWN
    if (
        url_lower.endswith((".md", ".markdown", ".txt"))
        or content_type in ("text/markdown", "text/plain", "TEXT", "text")
        or ct_lower in ("text", "markdown", "text/markdown", "text/plain")
    ):
        return "text"
    # IMAGE
    if (
        url_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"))
        or ct_lower.startswith("image/")
        or ct_lower in ("image", "IMAGE")
    ):
        return "image"
    return "txt"


def _get_image_mime(file_url: str, content_type: str) -> str:
    url_lower = file_url.lower()
    if url_lower.endswith(".png"):
        return "image/png"
    if url_lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if url_lower.endswith(".gif"):
        return "image/gif"
    if url_lower.endswith(".webp"):
        return "image/webp"
    if content_type.startswith("image/"):
        return content_type
    return "image/jpeg"


# ── Heading / title extractors ────────────────────────────────────────────────

def _extract_headings(text: str, max_headings: int = 30) -> list[str]:
    import re
    headings: list[str] = []
    # Markdown headings (## style)
    for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE):
        headings.append(m.group(2).strip())
        if len(headings) >= max_headings:
            break
    # Fallback: plain-text heuristic headings
    if not headings:
        heading_pattern = re.compile(
            r"^(?:\d+[\.\)]\s+|[IVXivx]+[\.\)]\s+|[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴ])"
        )
        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) > 80 or line.endswith("."):
                continue
            if heading_pattern.match(line) or (line.isupper() and len(line) > 3):
                headings.append(line)
                if len(headings) >= max_headings:
                    break
    return headings


def _extract_doc_title(text: str) -> Optional[str]:
    import re
    # For markdown, first H1 is the title
    m = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    # Fallback: first non-empty line
    for line in text.split("\n")[:10]:
        line = line.strip()
        if line and 5 < len(line) < 120:
            return line
    return None


def _smart_excerpt(text: str, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    n_parts = 5
    part_size = max_chars // n_parts
    total_len = len(text)
    step = total_len // n_parts
    parts: list[str] = []
    for i in range(n_parts):
        start = i * step
        end = min(start + part_size, total_len)
        snippet = text[start:end].strip()
        if snippet:
            parts.append(snippet)
    return "\n\n[...]\n\n".join(parts)


# ── Embedding batch helper ─────────────────────────────────────────────────────

async def _batch_embed(texts: list[str]) -> list[list[float]]:
    results: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        sub = texts[i: i + EMBED_BATCH_SIZE]
        batch = await create_embeddings_batch(sub)
        results.extend(batch)
    return results


# ── MinIO Helper ──────────────────────────────────────────────────────────────

def _get_minio_presigned_url(path_key: str, expires_in_seconds: int = 3600) -> Optional[str]:
    """
    Get presigned URL from LMS Go backend (safe, unified access control).
    path_key: relative path without leading / (e.g. "files/image/xxx.png")
    
    Calls: GET /api/v1/files/presigned/{path_key}?expires={expires_in_seconds}
    Returns: presigned_url (full MinIO HTTP URL for direct access)
    """
    try:
        import httpx
        
        # LMS backend URL from settings
        lms_base = settings.lms_api_url.rstrip("/")  # e.g. "http://lms-backend:8081"
        presigned_endpoint = f"{lms_base}/api/v1/files/presigned/{path_key}"
        
        # Make synchronous request
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                presigned_endpoint,
                params={"expires": expires_in_seconds},
                headers={"X-API-Secret": settings.ai_service_secret},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                presigned_url = data.get("presigned_url")
                logger.debug("Got presigned URL for path=%s", path_key[:50])
                return presigned_url
            else:
                logger.warning(
                    "LMS presigned endpoint returned %d for %s: %s",
                    resp.status_code, path_key[:50], resp.text[:200]
                )
                return None
        
    except Exception as exc:
        logger.warning("Failed to get presigned URL from LMS backend for %s: %s", path_key[:50], exc)
        return None


# ── Main service ───────────────────────────────────────────────────────────────

class AutoIndexService:

    # ─ Public entry point ────────────────────────────────────────────────────

    async def auto_index(
        self,
        content_id: int,
        course_id: int,
        file_url: str,
        content_type: str,
        file_bytes: Optional[bytes] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> dict:
        logger.info("AutoIndex start: content_id=%d, course_id=%d, type=%s", content_id, course_id, content_type)

        def _progress(stage: str, pct: int):
            logger.debug("AutoIndex [%d] %s: %d%%", content_id, stage, pct)
            if progress_callback:
                progress_callback(stage, pct)

        try:
            _progress("download", 0)

            if file_bytes is None:
                file_bytes = await self._download_bytes(file_url)

            if not file_bytes:
                await self._update_content_status(content_id, "failed", "Empty file")
                return {"ok": False, "error": "Empty file"}

            _progress("extract", 10)

            file_type = _detect_file_type(file_url, content_type)
            raw_text, structured_chunks = await self._extract_text_and_chunks(
                file_bytes, file_type, content_id, file_url
            )

            if not raw_text.strip():
                await self._update_content_status(content_id, "failed", "Empty document text")
                return {"ok": False, "error": "Empty document text"}

            _progress("llm_analysis", 20)

            language = detect_language(raw_text[:3000])

            nodes, relations = await self._extract_nodes_and_relations(
                raw_text, file_type, language, file_url
            )

            if not nodes:
                await self._update_content_status(content_id, "failed", "No nodes extracted")
                return {"ok": False, "error": "No nodes extracted"}

            _progress("embed_nodes", 40)

            node_desc_texts = [
                f"{n.name_vi or n.name}: {n.description} Từ khóa: {', '.join(n.keywords)}"
                for n in nodes
            ]
            node_embeddings = await _batch_embed(node_desc_texts)

            _progress("dedup_nodes", 48)

            # ── NEW: deduplicate nodes against existing course nodes ──────────
            (
                truly_new_nodes,
                truly_new_embs,
                idx_to_existing,
            ) = await self._deduplicate_nodes(nodes, node_embeddings, course_id)

            _progress("create_nodes", 52)

            # Create only genuinely new nodes
            new_node_ids: list[int] = []
            if truly_new_nodes:
                new_node_ids = await self._create_knowledge_nodes_batch(
                    truly_new_nodes, truly_new_embs, course_id, content_id
                )

            # Build full node_ids list preserving original order
            # (for correct chunk assignment)
            all_node_ids, all_node_embeddings = self._build_combined_node_list(
                nodes, node_embeddings, idx_to_existing, truly_new_nodes, new_node_ids
            )

            # Create LLM-derived relations
            await self._create_llm_relations(relations, all_node_ids, course_id)

            _progress("chunk_embed", 60)

            n_chunks = await self._chunk_and_store(
                file_bytes=file_bytes,
                file_type=file_type,
                structured_chunks=structured_chunks,
                content_id=content_id,
                course_id=course_id,
                node_ids=all_node_ids,
                node_embeddings=all_node_embeddings,
                language=language,
            )

            _progress("build_graph", 90)

            await self._build_graph_edges(all_node_ids, all_node_embeddings, course_id)

            await self._update_content_status(content_id, "indexed")
            _progress("done", 100)

            logger.info(
                "AutoIndex done: content_id=%d, new_nodes=%d, reused_nodes=%d, chunks=%d",
                content_id, len(new_node_ids), len(idx_to_existing), n_chunks,
            )
            return {
                "ok": True,
                "node_ids": all_node_ids,
                "new_nodes_created": len(new_node_ids),
                "nodes_reused": len(idx_to_existing),
                "chunks_created": n_chunks,
                "language": language,
                "file_type": file_type,
            }

        except Exception as exc:
            logger.error("AutoIndex failed content_id=%d: %s", content_id, exc, exc_info=True)
            await self._update_content_status(content_id, "failed", str(exc)[:300])
            raise

    async def auto_index_text(
        self,
        content_id: int,
        course_id: int,
        title: str,
        text_content: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> dict:
        """
        Auto-index TEXT content (direct text, not from file).
        Similar to auto_index but:
        - No file download needed
        - Text processing directly from input
        - No structured chunks extraction (text is already clean)
        """
        logger.info(
            "AutoIndexText start: content_id=%d, course_id=%d, title=%s, text_len=%d",
            content_id, course_id, title, len(text_content),
        )

        def _progress(stage: str, pct: int):
            logger.debug("AutoIndexText [%d] %s: %d%%", content_id, stage, pct)
            if progress_callback:
                progress_callback(stage, pct)

        try:
            _progress("parse", 10)

            if not text_content.strip():
                await self._update_content_status(content_id, "failed", "Empty text content")
                return {"ok": False, "error": "Empty text content"}

            # Auto-detect language from first 3000 chars
            language = detect_language(text_content[:3000])
            logger.info("AutoIndexText: Detected language=%s", language)

            _progress("llm_analysis", 25)

            # Extract nodes/relations from raw text (simplified for TEXT content)
            # file_type='text' tells LLM it's markdown-like text, not a PDF/document
            nodes, relations = await self._extract_nodes_and_relations(
                text_content, file_type="text", language=language, doc_title=title
            )

            if not nodes:
                await self._update_content_status(content_id, "failed", "No nodes extracted")
                return {"ok": False, "error": "No nodes extracted"}

            _progress("embed_nodes", 40)

            node_desc_texts = [
                f"{n.name_vi or n.name}: {n.description} Từ khóa: {', '.join(n.keywords)}"
                for n in nodes
            ]
            node_embeddings = await _batch_embed(node_desc_texts)

            _progress("dedup_nodes", 48)

            # Deduplicate against existing nodes
            (
                truly_new_nodes,
                truly_new_embs,
                idx_to_existing,
            ) = await self._deduplicate_nodes(nodes, node_embeddings, course_id)

            _progress("create_nodes", 52)

            # Create new nodes
            new_node_ids: list[int] = []
            if truly_new_nodes:
                new_node_ids = await self._create_knowledge_nodes_batch(
                    truly_new_nodes, truly_new_embs, course_id, content_id
                )

            # Build combined node IDs list
            all_node_ids, all_node_embeddings = self._build_combined_node_list(
                nodes, node_embeddings, idx_to_existing, truly_new_nodes, new_node_ids
            )

            # Create LLM-derived relations
            await self._create_llm_relations(relations, all_node_ids, course_id)

            _progress("chunk_embed", 60)

            # For TEXT content, use async MarkdownChunker with VLM image descriptions
            from app.services.chunker import MarkdownChunker
            from app.core.vlm import describe_image_url
            
            chunker = MarkdownChunker()
            
            # Define async image describer that uses VLM
            async def image_describer(image_url: str, alt_text: str) -> str:
                """Describe image using VLM for better semantic search."""
                # Convert relative paths to MinIO presigned URLs
                url_to_use = image_url
                if image_url.startswith("/"):
                    path_key = image_url.lstrip("/")
                    presigned_url = _get_minio_presigned_url(path_key)
                    if presigned_url:
                        url_to_use = presigned_url
                
                return await describe_image_url(
                    image_url=url_to_use,
                    language=language,
                    alt_text=alt_text,
                )
            
            # Use async chunking with VLM image descriptions
            structured_chunks = await chunker.chunk_async(
                markdown_text=text_content,
                image_describer=image_describer,
            )

            # Store chunks and assign to nodes
            n_chunks = await self._chunk_and_store(
                file_bytes=text_content.encode("utf-8"),  # Not actually used, just for compatibility
                file_type="text",
                structured_chunks=structured_chunks,
                content_id=content_id,
                course_id=course_id,
                node_ids=all_node_ids,
                node_embeddings=all_node_embeddings,
                language=language,
            )

            _progress("build_graph", 90)

            await self._build_graph_edges(all_node_ids, all_node_embeddings, course_id)

            await self._update_content_status(content_id, "indexed")
            _progress("done", 100)

            logger.info(
                "AutoIndexText done: content_id=%d, new_nodes=%d, reused_nodes=%d, chunks=%d",
                content_id, len(new_node_ids), len(idx_to_existing), n_chunks,
            )
            return {
                "ok": True,
                "node_ids": all_node_ids,
                "new_nodes_created": len(new_node_ids),
                "nodes_reused": len(idx_to_existing),
                "chunks_created": n_chunks,
                "language": language,
                "file_type": "text",
            }

        except Exception as exc:
            logger.error("AutoIndexText failed content_id=%d: %s", content_id, exc, exc_info=True)
            await self._update_content_status(content_id, "failed", str(exc)[:300])
            raise

    # ─ Step 1: Download ───────────────────────────────────────────────────────

    async def _download_bytes(self, file_url: str) -> bytes:
        loop = asyncio.get_event_loop()

        def _sync_download() -> bytes:
            from minio import Minio
            client = Minio(
                os.getenv("MINIO_ENDPOINT", ""),
                access_key=os.getenv("MINIO_ACCESS_KEY", ""),
                secret_key=os.getenv("MINIO_SECRET_KEY", ""),
                secure=False,
            )
            bucket = os.getenv("MINIO_BUCKET", "lms-files")
            response = client.get_object(bucket, file_url)
            try:
                buf = io.BytesIO()
                for chunk in response.stream(1 * 1024 * 1024):
                    buf.write(chunk)
                return buf.getvalue()
            finally:
                response.close()
                response.release_conn()

        return await loop.run_in_executor(None, _sync_download)

    # ─ Step 2: Extract text + chunks ─────────────────────────────────────────

    async def _extract_text_and_chunks(
        self,
        file_bytes: bytes,
        file_type: str,
        content_id: int,
        file_url: str = "",
    ) -> tuple[str, list[DocumentChunk]]:

        # ── TEXT (Markdown) — async path with VLM ─────────────────────────
        if file_type == "text":
            from app.core.vlm import describe_image_url

            text = file_bytes.decode("utf-8", errors="replace")
            language = detect_language(text[:2000])

            chunker = MarkdownChunker(
                chunk_size=settings.chunk_size,
                overlap=settings.chunk_overlap,
            )
            
            # Create wrapper to convert relative image paths to MinIO presigned URLs
            async def image_describer_with_minio(url: str, alt_text: str) -> str:
                # If relative path (starts with /), convert to MinIO presigned URL
                if url.startswith("/"):
                    path_key = url.lstrip("/")
                    presigned_url = _get_minio_presigned_url(path_key)
                    if presigned_url:
                        return await describe_image_url(presigned_url, language=language, alt_text=alt_text)
                # Already a full URL, use directly
                return await describe_image_url(url, language=language, alt_text=alt_text)
            
            chunks = await chunker.chunk_async(
                text,
                image_describer=image_describer_with_minio,
            )
            raw_text = "\n\n".join(c.text for c in chunks)
            return raw_text, chunks

        # ── IMAGE — async VLM description ──────────────────────────────────
        if file_type == "image":
            mime = _get_image_mime(file_url, "image/jpeg")
            language = "vi"

            chunker = ImageChunker()
            chunks = await chunker.chunk_async(file_bytes, mime_type=mime, language=language)
            raw_text = chunks[0].text if chunks else ""
            return raw_text, chunks

        # ── All other types — run sync chunkers in executor ────────────────
        loop = asyncio.get_event_loop()

        def _sync_extract() -> list[DocumentChunk]:
            chunker_map = {
                "pdf":  PDFChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap),
                "docx": DocxChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap),
                "pptx": PptxChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap),
                "xlsx": ExcelChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap),
            }
            if file_type in chunker_map:
                return chunker_map[file_type].chunk_bytes(file_bytes)

            if file_type == "video":
                logger.warning("Video type: transcript must be pre-generated (content_id=%d)", content_id)
                return []

            # txt or unknown
            text = file_bytes.decode("utf-8", errors="replace")
            chunker = PDFChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
            raw = chunker._split_text(text)
            return [
                DocumentChunk(
                    text=sanitize_text(c), index=i,
                    source_type="document", page_number=1,
                    language=detect_language(c),
                )
                for i, c in enumerate(raw)
            ]

        chunks = await loop.run_in_executor(None, _sync_extract)
        raw_text = "\n\n".join(c.text for c in chunks)
        return raw_text, chunks

    # ─ Step 3: LLM node + relation extraction ─────────────────────────────

    async def _extract_nodes_and_relations(
        self,
        raw_text: str,
        file_type: str,
        language: str,
        file_url: str = "",
        doc_title: Optional[str] = None,
    ) -> tuple[list[ExtractedNode], list[ExtractedRelation]]:
        n_nodes = min(
            MAX_NODES_PER_DOCUMENT,
            max(MIN_NODES_PER_DOCUMENT, len(raw_text) // 1500),
        )
        # Use provided doc_title, or extract from raw_text if not provided
        if doc_title is None:
            doc_title = _extract_doc_title(raw_text)
        headings = _extract_headings(raw_text)
        excerpt = _smart_excerpt(raw_text, MAX_EXCERPT_CHARS)

        prompt = build_node_extraction_prompt(
            document_excerpt=excerpt,
            file_type=file_type,
            language=language,
            doc_title=doc_title,
            detected_headings=headings,
            max_nodes=n_nodes,
        )
        messages = [
            {"role": "system", "content": NODE_EXTRACTION_SYSTEM},
            {"role": "user",   "content": prompt},
        ]

        try:
            result = await chat_complete_json(
                messages=messages,
                model=settings.quiz_model,
                temperature=0.15,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.error("LLM node extraction failed: %s", exc, exc_info=True)
            fallback_name = doc_title or "Nội dung tài liệu"
            return (
                [ExtractedNode(
                    name=fallback_name, name_vi=fallback_name,
                    name_en=fallback_name, description="",
                    keywords=[], order_index=0,
                )],
                [],
            )

        raw_nodes = result.get("nodes", [])
        nodes: list[ExtractedNode] = []
        for i, n in enumerate(raw_nodes[:MAX_NODES_PER_DOCUMENT]):
            name_vi = n.get("name_vi") or n.get("name", "")
            name_en = n.get("name_en") or n.get("name", "")
            if not (name_vi or name_en):
                continue
            nodes.append(ExtractedNode(
                name=name_vi or name_en,
                name_vi=name_vi,
                name_en=name_en,
                description=n.get("description", "")[:500],
                keywords=n.get("keywords", [])[:8],
                order_index=i,
            ))

        raw_rels = result.get("prerequisites", [])
        relations: list[ExtractedRelation] = []
        for r in raw_rels:
            src = r.get("source_index")
            tgt = r.get("target_index")
            if not (isinstance(src, int) and isinstance(tgt, int)):
                continue
            if src == tgt or src >= len(nodes) or tgt >= len(nodes):
                continue
            relations.append(ExtractedRelation(
                source_index=src,
                target_index=tgt,
                relation_type=r.get("relation_type", "prerequisite"),
                reason=r.get("reason", ""),
                strength=float(r.get("strength", 0.85)),
            ))

        logger.info("LLM extracted %d nodes, %d relations", len(nodes), len(relations))
        return nodes, relations

    # ─ Step 4 NEW: Node deduplication ────────────────────────────────────────

    async def _deduplicate_nodes(
        self,
        nodes: list[ExtractedNode],
        embeddings: list[list[float]],
        course_id: int,
    ) -> tuple[
        list[ExtractedNode],   # truly new nodes (to be created)
        list[list[float]],     # their embeddings
        dict[int, int],        # original_idx → existing_node_id (duplicates)
    ]:
        """
        Compare proposed nodes against existing knowledge nodes in this course.

        Similarity >= DEDUP_HARD_THRESHOLD (0.92):
            Treat as identical — reuse existing node, do NOT create new one.

        DEDUP_SOFT_THRESHOLD (0.80) <= sim < DEDUP_HARD_THRESHOLD:
            Similar but distinct — merge new description into existing node so
            it becomes richer, and still reuse it for chunk assignment.

        sim < DEDUP_SOFT_THRESHOLD:
            Genuinely new concept — create new node.

        Returns idx_to_existing: maps original node list index → existing DB node ID.
        """
        async with get_async_conn() as conn:
            existing_rows = await conn.fetch(
                """
                SELECT id, name, description, description_embedding
                FROM knowledge_nodes
                WHERE course_id = $1 AND description_embedding IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 500
                """,
                course_id,
            )

        if not existing_rows:
            # No existing nodes; everything is new
            return nodes, embeddings, {}

        # Parse existing embeddings
        existing_ids: list[int] = []
        existing_embs: list[list[float]] = []
        existing_names: list[str] = []

        for row in existing_rows:
            emb_str = row["description_embedding"]
            if isinstance(emb_str, str):
                emb = [float(x) for x in emb_str.strip("[]").split(",")]
            else:
                emb = list(emb_str)
            existing_ids.append(row["id"])
            existing_embs.append(emb)
            existing_names.append(row["name"])

        existing_matrix = np.array(existing_embs)   # (n_exist, dim)
        new_matrix = np.array(embeddings)            # (n_new, dim)

        # Cosine similarity matrix (n_new, n_exist)
        existing_norms = np.linalg.norm(existing_matrix, axis=1, keepdims=True) + 1e-8
        new_norms = np.linalg.norm(new_matrix, axis=1, keepdims=True) + 1e-8
        existing_norm = existing_matrix / existing_norms
        new_norm = new_matrix / new_norms
        sims = new_norm @ existing_norm.T  # (n_new, n_exist)

        truly_new_nodes: list[ExtractedNode] = []
        truly_new_embs: list[list[float]] = []
        idx_to_existing: dict[int, int] = {}

        for i, (node, emb) in enumerate(zip(nodes, embeddings)):
            best_j = int(sims[i].argmax())
            best_sim = float(sims[i, best_j])
            existing_id = existing_ids[best_j]

            if best_sim >= DEDUP_HARD_THRESHOLD:
                idx_to_existing[i] = existing_id
                logger.info(
                    "[dedup:hard] '%s' → reuse node %d '%s' (sim=%.3f)",
                    node.name, existing_id, existing_names[best_j], best_sim,
                )

            elif best_sim >= DEDUP_SOFT_THRESHOLD:
                # Merge: enrich the existing node's description
                await self._merge_node_description(
                    existing_id, node.description, node.keywords
                )
                idx_to_existing[i] = existing_id
                logger.info(
                    "[dedup:soft] '%s' → merge into node %d '%s' (sim=%.3f)",
                    node.name, existing_id, existing_names[best_j], best_sim,
                )

            else:
                truly_new_nodes.append(node)
                truly_new_embs.append(emb)
                logger.debug(
                    "[dedup:new] '%s' (best sim=%.3f with '%s')",
                    node.name, best_sim, existing_names[best_j],
                )

        logger.info(
            "[dedup] %d new / %d reused (hard=%d soft=%d) out of %d proposed",
            len(truly_new_nodes),
            len(idx_to_existing),
            sum(1 for i, eid in idx_to_existing.items()
                if float(sims[i, existing_ids.index(eid)]) >= DEDUP_HARD_THRESHOLD),
            sum(1 for i, eid in idx_to_existing.items()
                if float(sims[i, existing_ids.index(eid)]) < DEDUP_HARD_THRESHOLD),
            len(nodes),
        )
        return truly_new_nodes, truly_new_embs, idx_to_existing

    async def _merge_node_description(
        self, node_id: int, new_description: str, new_keywords: list[str]
    ) -> None:
        """Append new description info to an existing node."""
        if not new_description:
            return
        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                "SELECT description FROM knowledge_nodes WHERE id=$1", node_id
            )
            existing_desc = (row["description"] or "") if row else ""
            if new_description not in existing_desc:
                merged = (existing_desc + " | " + new_description).strip(" |")[:800]
            else:
                merged = existing_desc
            await conn.execute(
                "UPDATE knowledge_nodes SET description=$1, updated_at=NOW() WHERE id=$2",
                merged, node_id,
            )

    def _build_combined_node_list(
        self,
        original_nodes: list[ExtractedNode],
        original_embeddings: list[list[float]],
        idx_to_existing: dict[int, int],
        truly_new_nodes: list[ExtractedNode],
        new_node_ids: list[int],
    ) -> tuple[list[int], list[list[float]]]:
        """
        Rebuild the full ordered node_ids + embeddings list preserving original
        node order so chunk assignment indices stay consistent.

        Returns:
          all_node_ids       — node DB IDs in original node order
          all_node_embeddings — embeddings in same order
        """
        new_idx_iter = iter(zip(new_node_ids, [e for n, e in zip(original_nodes, original_embeddings)
                                               if original_nodes.index(n) not in idx_to_existing]))
        # We need a different approach: map truly_new positions
        truly_new_original_indices = [
            i for i in range(len(original_nodes)) if i not in idx_to_existing
        ]

        all_node_ids: list[int] = []
        all_node_embeddings: list[list[float]] = []

        new_node_cursor = 0
        for i, (node, emb) in enumerate(zip(original_nodes, original_embeddings)):
            if i in idx_to_existing:
                all_node_ids.append(idx_to_existing[i])
                all_node_embeddings.append(emb)
            else:
                if new_node_cursor < len(new_node_ids):
                    all_node_ids.append(new_node_ids[new_node_cursor])
                    all_node_embeddings.append(emb)
                    new_node_cursor += 1

        return all_node_ids, all_node_embeddings

    # ─ Step 5: Create new nodes in DB ────────────────────────────────────────

    async def _create_knowledge_nodes_batch(
        self,
        nodes: list[ExtractedNode],
        embeddings: list[list[float]],
        course_id: int,
        content_id: int,
    ) -> list[int]:
        if not nodes:
            return []

        node_ids: list[int] = []
        async with get_async_conn() as conn:
            async with conn.transaction():
                for node, embedding in zip(nodes, embeddings):
                    emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
                    row = await conn.fetchrow(
                        """
                        INSERT INTO knowledge_nodes
                            (course_id, name, name_vi, name_en, description,
                             description_embedding, level, order_index,
                             source_content_id, auto_generated)
                        VALUES ($1,$2,$3,$4,$5,$6::vector,0,$7,$8,true)
                        RETURNING id
                        """,
                        course_id,
                        node.name,
                        node.name_vi,
                        node.name_en,
                        node.description,
                        emb_str,
                        node.order_index,
                        content_id,
                    )
                    node_ids.append(row["id"])

        logger.info("Created %d new knowledge nodes", len(node_ids))
        return node_ids

    # ─ Step 6: LLM relations ─────────────────────────────────────────────────

    async def _create_llm_relations(
        self,
        relations: list[ExtractedRelation],
        node_ids: list[int],
        course_id: int,
    ) -> None:
        if not relations:
            return
        async with get_async_conn() as conn:
            async with conn.transaction():
                for rel in relations:
                    if rel.source_index >= len(node_ids) or rel.target_index >= len(node_ids):
                        continue
                    await conn.execute(
                        """
                        INSERT INTO knowledge_node_relations
                            (course_id, source_node_id, target_node_id,
                             relation_type, strength, auto_generated)
                        VALUES ($1,$2,$3,$4,$5,true)
                        ON CONFLICT (source_node_id, target_node_id, relation_type) DO UPDATE
                            SET strength = GREATEST(
                                knowledge_node_relations.strength,
                                EXCLUDED.strength
                            )
                        """,
                        course_id,
                        node_ids[rel.source_index],
                        node_ids[rel.target_index],
                        rel.relation_type,
                        round(rel.strength, 3),
                    )

    # ─ Step 7: Chunk + embed + assign ────────────────────────────────────────

    async def _chunk_and_store(
        self,
        file_bytes: bytes,
        file_type: str,
        structured_chunks: list[DocumentChunk],
        content_id: int,
        course_id: int,
        node_ids: list[int],
        node_embeddings: list[list[float]],
        language: str,
    ) -> int:
        if not structured_chunks:
            return 0

        chunk_texts = [c.text for c in structured_chunks]
        chunk_embeddings = await _batch_embed(chunk_texts)

        # Vectorized chunk→node assignment
        node_emb_matrix = np.array(node_embeddings)
        node_norms = np.linalg.norm(node_emb_matrix, axis=1, keepdims=True) + 1e-8
        node_emb_norm = node_emb_matrix / node_norms

        chunk_emb_matrix = np.array(chunk_embeddings)
        chunk_norms = np.linalg.norm(chunk_emb_matrix, axis=1, keepdims=True) + 1e-8
        chunk_emb_norm = chunk_emb_matrix / chunk_norms

        sims = chunk_emb_norm @ node_emb_norm.T  # (n_chunks, n_nodes)
        best_node_local = sims.argmax(axis=1)
        assigned_node_ids = [node_ids[i] for i in best_node_local.tolist()]

        stored = await self._batch_insert_chunks(
            content_id=content_id,
            course_id=course_id,
            chunks=structured_chunks,
            embeddings=chunk_embeddings,
            assigned_node_ids=assigned_node_ids,
        )

        logger.info("Stored %d chunks for content_id=%d", stored, content_id)
        return stored

    async def _batch_insert_chunks(
        self,
        content_id: int,
        course_id: int,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        assigned_node_ids: list[int],
    ) -> int:
        from app.services.rag_service import _sanitize
        stored = 0
        async with get_async_conn() as conn:
            async with conn.transaction():
                for chunk, embedding, node_id in zip(chunks, embeddings, assigned_node_ids):
                    chunk_text = _sanitize(chunk.text)
                    if not chunk_text.strip():
                        continue
                    chunk_hash = hashlib.sha256(
                        f"{content_id}:{chunk.index}:{chunk_text}".encode()
                    ).hexdigest()
                    emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
                    await conn.execute(
                        """
                        INSERT INTO document_chunks
                            (content_id, course_id, node_id, chunk_text, chunk_index,
                             chunk_hash, embedding, source_type, page_number,
                             start_time_sec, end_time_sec, language, status)
                        VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12,'ready')
                        ON CONFLICT (chunk_hash) DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            node_id   = EXCLUDED.node_id,
                            status    = 'ready'
                        """,
                        content_id, course_id, node_id,
                        chunk_text, chunk.index, chunk_hash, emb_str,
                        chunk.source_type,
                        chunk.page_number,
                        chunk.start_time_sec,
                        chunk.end_time_sec,
                        chunk.language,
                    )
                    stored += 1
        return stored

    # ─ Step 8: Cross-document graph edges ────────────────────────────────────

    async def _build_graph_edges(
        self,
        new_node_ids: list[int],
        new_node_embeddings: list[list[float]],
        course_id: int,
    ) -> None:
        if not new_node_ids:
            return

        async with get_async_conn() as conn:
            existing_rows = await conn.fetch(
                """
                SELECT id, description_embedding
                FROM knowledge_nodes
                WHERE course_id = $1
                  AND id != ALL($2::bigint[])
                  AND description_embedding IS NOT NULL
                ORDER BY created_at DESC
                LIMIT $3
                """,
                course_id,
                new_node_ids,
                MAX_EXISTING_NODES_FOR_GRAPH,
            )

        if not existing_rows:
            await self._create_intra_document_edges(new_node_ids, new_node_embeddings, course_id)
            return

        existing_ids: list[int] = []
        existing_embs: list[list[float]] = []
        for r in existing_rows:
            emb_str = r["description_embedding"]
            if isinstance(emb_str, str):
                emb = [float(x) for x in emb_str.strip("[]").split(",")]
            else:
                emb = list(emb_str)
            existing_ids.append(r["id"])
            existing_embs.append(emb)

        new_matrix = np.array(new_node_embeddings)
        existing_matrix = np.array(existing_embs)

        new_norms = np.linalg.norm(new_matrix, axis=1, keepdims=True) + 1e-8
        exist_norms = np.linalg.norm(existing_matrix, axis=1, keepdims=True) + 1e-8
        new_norm = new_matrix / new_norms
        exist_norm = existing_matrix / exist_norms

        cross_sims = new_norm @ exist_norm.T
        intra_sims = new_norm @ new_norm.T

        edges: list[tuple[int, int, float]] = []

        for i, new_id in enumerate(new_node_ids):
            for j, exist_id in enumerate(existing_ids):
                sim = float(cross_sims[i, j])
                if sim >= RELATION_SIMILARITY_THRESHOLD:
                    edges.append((new_id, exist_id, sim))

        for i in range(len(new_node_ids)):
            for j in range(i + 1, len(new_node_ids)):
                sim = float(intra_sims[i, j])
                if sim >= RELATION_SIMILARITY_THRESHOLD:
                    edges.append((new_node_ids[i], new_node_ids[j], sim))

        if not edges:
            return

        async with get_async_conn() as conn:
            async with conn.transaction():
                for src, tgt, strength in edges:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_node_relations
                            (course_id, source_node_id, target_node_id,
                             relation_type, strength, auto_generated)
                        VALUES ($1,$2,$3,'related',$4,true)
                        ON CONFLICT (source_node_id, target_node_id, relation_type) DO UPDATE
                            SET strength = GREATEST(
                                knowledge_node_relations.strength,
                                EXCLUDED.strength
                            )
                        """,
                        course_id, src, tgt, round(strength, 3),
                    )

        logger.info("Created/updated %d graph edges for course_id=%d", len(edges), course_id)

    async def _create_intra_document_edges(
        self,
        node_ids: list[int],
        embeddings: list[list[float]],
        course_id: int,
    ) -> None:
        if len(node_ids) < 2:
            return
        matrix = np.array(embeddings)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8
        normed = matrix / norms
        sims = normed @ normed.T
        edges = [
            (node_ids[i], node_ids[j], float(sims[i, j]))
            for i in range(len(node_ids))
            for j in range(i + 1, len(node_ids))
            if float(sims[i, j]) >= RELATION_SIMILARITY_THRESHOLD
        ]
        if not edges:
            return
        async with get_async_conn() as conn:
            async with conn.transaction():
                for src, tgt, strength in edges:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_node_relations
                            (course_id, source_node_id, target_node_id,
                             relation_type, strength, auto_generated)
                        VALUES ($1,$2,$3,'related',$4,true)
                        ON CONFLICT (source_node_id, target_node_id, relation_type) DO NOTHING
                        """,
                        course_id, src, tgt, round(strength, 3),
                    )

    # ─ Utility ───────────────────────────────────────────────────────────────

    async def _update_content_status(
        self,
        content_id: int,
        status: str,
        error_msg: Optional[str] = None,
    ) -> None:
        async with get_async_conn() as conn:
            await conn.execute(
                "UPDATE section_content SET ai_index_status=$1 WHERE id=$2",
                status, content_id,
            )
        if error_msg:
            logger.warning("content_id=%d → %s: %s", content_id, status, error_msg)


# Singleton
auto_index_service = AutoIndexService()