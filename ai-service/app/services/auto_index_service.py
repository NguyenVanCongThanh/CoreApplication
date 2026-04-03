from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from app.core.config import get_settings
from app.core.database import get_async_conn
from app.core.llm import (
    chat_complete_json,
    create_embeddings_batch,
)
from app.services.chunker import (
    PDFChunker,
    DocxChunker,
    PptxChunker,
    ExcelChunker,
    VideoTranscriptChunker,
    DocumentChunk,
    detect_language,
    sanitize_text,
)

logger = logging.getLogger(__name__)
settings = get_settings()

#  Tuning constants 
RELATION_SIMILARITY_THRESHOLD = 0.62
MAX_NODES_PER_DOCUMENT = 8
MIN_NODES_PER_DOCUMENT = 2
EMBED_BATCH_SIZE = 16
MAX_EXCERPT_CHARS = 9000
MAX_EXISTING_NODES_FOR_GRAPH = 200


#  Data classes 

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


#  LLM Prompts 

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
    doc_title: str | None,
    detected_headings: list[str],
    max_nodes: int,
) -> str:
    """
    Xây dựng prompt giàu ngữ cảnh cho node extraction + prerequisite trong 1 lần gọi.
    Gộp 2 prompt cũ thành 1 để tiết kiệm ~50% LLM latency.
    """
    lang_hint = "Tên chủ đề ưu tiên tiếng Việt" if language == "vi" else "Topic names in English preferred"
    file_hint_map = {
        "pdf": "tài liệu PDF (có thể là giáo trình, bài giảng, báo cáo)",
        "docx": "tài liệu Word (có thể là giáo án, bài viết học thuật)",
        "pptx": "bản trình chiếu PowerPoint (mỗi slide thường là 1 ý chính)",
        "xlsx": "bảng tính Excel (dữ liệu có cấu trúc, chú ý headers và labels)",
        "txt": "file văn bản thuần (chú ý cấu trúc đoạn văn)",
        "video": "transcript video bài giảng (chú ý mốc thời gian và chủ đề chuyển đổi)",
    }
    file_hint = file_hint_map.get(file_type, "tài liệu học tập")

    heading_context = ""
    if detected_headings:
        tops = detected_headings[:20]
        heading_context = f"\nCÁC TIÊU ĐỀ/HEADING PHÁT HIỆN ĐƯỢC:\n" + "\n".join(f"  - {h}" for h in tops) + "\n"

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


#  File extension → file_type mapping 

def _detect_file_type(file_url: str, content_type: str) -> str:
    url_lower = file_url.lower()
    ct_lower = content_type.lower()

    if url_lower.endswith(".pdf") or "pdf" in ct_lower:
        return "pdf"
    if url_lower.endswith(".docx") or url_lower.endswith(".doc") or "word" in ct_lower:
        return "docx"
    if url_lower.endswith(".pptx") or url_lower.endswith(".ppt") or "presentation" in ct_lower:
        return "pptx"
    if url_lower.endswith(".xlsx") or url_lower.endswith(".xls") or "spreadsheet" in ct_lower or "excel" in ct_lower:
        return "xlsx"
    if any(url_lower.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".avi")) or "video" in ct_lower:
        return "video"
    return "txt"


#  Heading extractor (để cung cấp thêm context cho LLM) 

def _extract_headings(text: str, max_headings: int = 30) -> list[str]:
    """
    Heuristic: dòng ngắn (<= 80 ký tự) kết thúc không bằng dấu chấm,
    bắt đầu bằng chữ hoa, hoặc là heading dạng số (I. II. 1. 2. 1.1 ...).
    Dùng để cung cấp cấu trúc tài liệu cho LLM mà không tốn nhiều token.
    """
    import re
    headings: list[str] = []
    heading_pattern = re.compile(
        r'^(?:'
        r'\d+[\.\)]\s+'           # 1. hoặc 1)
        r'|[IVXivx]+[\.\)]\s+'    # I. II. III.
        r'|[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴĐÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸ]'  # Hoa
        r')'
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


def _extract_doc_title(text: str) -> str | None:
    """Lấy dòng đầu tiên không rỗng làm title hint."""
    for line in text.split("\n")[:10]:
        line = line.strip()
        if line and 5 < len(line) < 120:
            return line
    return None


#  Smart excerpt: đầu + đều các đoạn giữa + cuối 

def _smart_excerpt(text: str, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """
    Cải tiến: lấy mẫu đồng đều từ toàn bộ tài liệu.
    Phân chia text thành N window, lấy đoạn đầu của mỗi window.
    Kết quả đại diện cho cấu trúc toàn bộ tài liệu tốt hơn là đầu+giữa+cuối.
    """
    if len(text) <= max_chars:
        return text

    # Chia thành 5 phần, mỗi phần lấy 1/5 * max_chars
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


#  Main Service 

class AutoIndexService:

    #  Public entry point 

    async def auto_index(
        self,
        content_id: int,
        course_id: int,
        file_url: str,
        content_type: str,
        file_bytes: bytes | None = None,                     # NEW: tránh download lại
        progress_callback: Callable[[str, int], None] | None = None,  # NEW: progress reporting
    ) -> dict:
        """
        Full auto-index pipeline.
        - `file_bytes`: nếu Celery task đã download, truyền thẳng vào để tránh download lần 2.
        - `progress_callback(stage, pct)`: được gọi sau mỗi bước (stage=tên bước, pct=0-100).
        """
        logger.info(f"AutoIndex start: content_id={content_id}, course_id={course_id}, type={content_type}")

        def _progress(stage: str, pct: int):
            logger.debug(f"AutoIndex [{content_id}] {stage}: {pct}%")
            if progress_callback:
                progress_callback(stage, pct)

        try:
            _progress("download", 0)

            # 1. Download file bytes (một lần duy nhất)
            if file_bytes is None:
                file_bytes = await self._download_bytes(file_url)

            if not file_bytes:
                await self._update_content_status(content_id, "failed", "Empty file")
                return {"ok": False, "error": "Empty file"}

            _progress("extract", 10)

            # 2. Detect file type + extract text + structured chunks
            file_type = _detect_file_type(file_url, content_type)
            raw_text, structured_chunks = await self._extract_text_and_chunks(
                file_bytes, file_type, content_id
            )

            if not raw_text.strip():
                await self._update_content_status(content_id, "failed", "Empty document text")
                return {"ok": False, "error": "Empty document text"}

            _progress("llm_analysis", 20)

            # 3. Detect language từ sample đầu tài liệu
            language = detect_language(raw_text[:3000])

            # 4. LLM: extract nodes + prerequisites trong 1 lần gọi
            nodes, relations = await self._extract_nodes_and_relations(
                raw_text, file_type, language, file_url
            )

            if not nodes:
                await self._update_content_status(content_id, "failed", "No nodes extracted")
                return {"ok": False, "error": "No nodes extracted"}

            _progress("embed_nodes", 40)

            # 5. Embed node descriptions (batch)
            node_desc_texts = [
                f"{n.name_vi or n.name}: {n.description} Từ khóa: {', '.join(n.keywords)}"
                for n in nodes
            ]
            node_embeddings = await _batch_embed(node_desc_texts)

            _progress("create_nodes", 50)

            # 6. Tạo knowledge_nodes trong DB (batch)
            node_ids = await self._create_knowledge_nodes_batch(
                nodes, node_embeddings, course_id, content_id
            )

            # 7. Tạo prerequisite/related relations từ LLM output
            await self._create_llm_relations(relations, node_ids, course_id)

            _progress("chunk_embed", 60)

            # 8. Chunk + embed + assign chunks → nodes
            n_chunks = await self._chunk_and_store(
                file_bytes=file_bytes,
                file_type=file_type,
                structured_chunks=structured_chunks,
                content_id=content_id,
                course_id=course_id,
                node_ids=node_ids,
                node_embeddings=node_embeddings,
                language=language,
            )

            _progress("build_graph", 90)

            # 9. Build cross-document graph edges
            await self._build_graph_edges(node_ids, node_embeddings, course_id)

            # 10. Mark indexed
            await self._update_content_status(content_id, "indexed")

            _progress("done", 100)

            logger.info(
                f"AutoIndex done: content_id={content_id}, "
                f"nodes={len(node_ids)}, chunks={n_chunks}, lang={language}"
            )
            return {
                "ok": True,
                "node_ids": node_ids,
                "nodes_created": len(node_ids),
                "chunks_created": n_chunks,
                "language": language,
                "file_type": file_type,
            }

        except Exception as e:
            logger.error(f"AutoIndex failed content_id={content_id}: {e}", exc_info=True)
            await self._update_content_status(content_id, "failed", str(e)[:300])
            raise

    #  Step 1: Download 

    async def _download_bytes(self, file_url: str) -> bytes:
        """
        Download file từ MinIO, trả về raw bytes.
        Dùng streaming để tránh spike bộ nhớ với file lớn.
        """
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
                for chunk in response.stream(1 * 1024 * 1024):  # 1MB chunks
                    buf.write(chunk)
                return buf.getvalue()
            finally:
                response.close()
                response.release_conn()

        return await loop.run_in_executor(None, _sync_download)

    #  Step 2: Extract text + structured chunks 

    async def _extract_text_and_chunks(
        self,
        file_bytes: bytes,
        file_type: str,
        content_id: int,
    ) -> tuple[str, list[DocumentChunk]]:
        """
        Trích xuất text thuần và danh sách DocumentChunk (với page_number/timestamp).
        Dùng chunker gốc để đảm bảo page metadata được giữ nguyên.
        """
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
                # Transcript phải được load từ DB hoặc Whisper (xử lý ở Celery task)
                # Ở đây fallback về empty để auto_index không crash
                logger.warning(f"Video type: transcript must be pre-generated (content_id={content_id})")
                return []

            # txt hoặc unknown
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

        # Ghép lại thành raw_text để gửi cho LLM (dùng chunk text thay vì re-parse)
        raw_text = "\n\n".join(c.text for c in chunks)
        return raw_text, chunks

    #  Step 3: LLM - Extract nodes + prerequisites (1 call) 

    async def _extract_nodes_and_relations(
        self,
        raw_text: str,
        file_type: str,
        language: str,
        file_url: str,
    ) -> tuple[list[ExtractedNode], list[ExtractedRelation]]:
        """
        Gộp node extraction + prerequisite detection thành 1 LLM call.
        Cải tiến vs cũ: cung cấp thêm headings, title, file type → LLM hiểu ngữ cảnh tốt hơn.
        """
        # Tính số nodes hợp lý dựa trên độ dài tài liệu
        n_nodes = min(
            MAX_NODES_PER_DOCUMENT,
            max(MIN_NODES_PER_DOCUMENT, len(raw_text) // 1500),
        )

        # Lấy metadata cấu trúc tài liệu (không tốn token nhiều)
        doc_title = _extract_doc_title(raw_text)
        headings = _extract_headings(raw_text)

        # Lấy excerpt thông minh
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
                model=settings.quiz_model,   # Dùng model mạnh hơn cho analysis
                temperature=0.15,            # Gần như deterministic để consistent
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"LLM node extraction failed: {e}", exc_info=True)
            # Fallback: tạo 1 node generic từ title
            fallback_name = doc_title or "Nội dung tài liệu"
            return (
                [ExtractedNode(
                    name=fallback_name, name_vi=fallback_name,
                    name_en=fallback_name, description="",
                    keywords=[], order_index=0,
                )],
                [],
            )

        # Parse nodes
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

        # Parse relations (prerequisites từ LLM)
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

        logger.info(f"LLM extracted {len(nodes)} nodes, {len(relations)} relations")
        return nodes, relations

    #  Step 4: Create nodes in DB (batch) 

    async def _create_knowledge_nodes_batch(
        self,
        nodes: list[ExtractedNode],
        embeddings: list[list[float]],
        course_id: int,
        content_id: int,
    ) -> list[int]:
        """
        Batch insert knowledge_nodes bằng asyncpg executemany.
        Nhanh hơn loop đơn lẻ với nhiều nodes.
        Sử dụng description_embedding_v2 (1024d) cho BAAI/bge-m3.
        """
        if not nodes:
            return []

        records = []
        for node, embedding in zip(nodes, embeddings):
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            records.append((
                course_id,
                node.name,
                node.name_vi,
                node.name_en,
                node.description,
                embedding_str,
                node.order_index,
                content_id,
            ))

        node_ids: list[int] = []
        async with get_async_conn() as conn:
            # asyncpg không có executemany returning → dùng vòng lặp trong 1 transaction
            async with conn.transaction():
                for rec in records:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO knowledge_nodes
                            (course_id, name, name_vi, name_en, description,
                             description_embedding_v2, level, order_index,
                             source_content_id, auto_generated)
                        VALUES ($1,$2,$3,$4,$5,$6::vector,0,$7,$8,true)
                        RETURNING id
                        """,
                        *rec,
                    )
                    node_ids.append(row["id"])

        logger.info(f"Created {len(node_ids)} knowledge nodes (batch)")
        return node_ids

    #  Step 5: Create LLM-derived relations 

    async def _create_llm_relations(
        self,
        relations: list[ExtractedRelation],
        node_ids: list[int],
        course_id: int,
    ) -> None:
        """Lưu prerequisite/related relations từ kết quả LLM."""
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

        logger.info(f"Created {len(relations)} LLM-derived relations")

    #  Step 6: Chunk + embed + assign + store 

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
        """
        Dùng structured_chunks (đã có page_number/timestamp) thay vì re-chunk từ text.
        Embed tất cả chunks theo batch → assign mỗi chunk → node gần nhất (vectorized).
        """
        if not structured_chunks:
            return 0

        chunk_texts = [c.text for c in structured_chunks]

        # Embed chunks theo sub-batches để tránh OOM
        chunk_embeddings = await _batch_embed(chunk_texts)

        # Assign chunk → closest node (numpy vectorized, O(n_chunks * n_nodes))
        node_emb_matrix = np.array(node_embeddings)  # (n_nodes, dim)
        # Normalize rows để cosine = dot product
        node_norms = np.linalg.norm(node_emb_matrix, axis=1, keepdims=True) + 1e-8
        node_emb_norm = node_emb_matrix / node_norms

        chunk_emb_matrix = np.array(chunk_embeddings)   # (n_chunks, dim)
        chunk_norms = np.linalg.norm(chunk_emb_matrix, axis=1, keepdims=True) + 1e-8
        chunk_emb_norm = chunk_emb_matrix / chunk_norms

        # (n_chunks, n_nodes) cosine similarities
        sims = chunk_emb_norm @ node_emb_norm.T
        best_node_local = sims.argmax(axis=1)  # shape: (n_chunks,)
        assigned_node_ids = [node_ids[i] for i in best_node_local.tolist()]

        # Batch insert chunks vào DB trong 1 transaction
        stored = await self._batch_insert_chunks(
            content_id=content_id,
            course_id=course_id,
            chunks=structured_chunks,
            embeddings=chunk_embeddings,
            assigned_node_ids=assigned_node_ids,
        )

        logger.info(f"Stored {stored} chunks for content_id={content_id}")
        return stored

    async def _batch_insert_chunks(
        self,
        content_id: int,
        course_id: int,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        assigned_node_ids: list[int],
    ) -> int:
        """
        Insert tất cả chunks trong 1 transaction để đảm bảo atomicity.
        Dùng ON CONFLICT DO UPDATE để idempotent khi re-index.
        Sử dụng embedding_v2 (1024d) cho BAAI/bge-m3.
        """
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
                    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

                    await conn.execute(
                        """
                        INSERT INTO document_chunks
                            (content_id, course_id, node_id, chunk_text, chunk_index,
                             chunk_hash, embedding_v2, source_type, page_number,
                             start_time_sec, end_time_sec, language, status)
                        VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12,'ready')
                        ON CONFLICT (chunk_hash) DO UPDATE SET
                            embedding_v2 = EXCLUDED.embedding_v2,
                            node_id     = EXCLUDED.node_id,
                            status      = 'ready'
                        """,
                        content_id, course_id, node_id,
                        chunk_text, chunk.index, chunk_hash, embedding_str,
                        chunk.source_type,
                        chunk.page_number,
                        chunk.start_time_sec,
                        chunk.end_time_sec,
                        chunk.language,
                    )
                    stored += 1

        return stored

    #  Step 7: Cross-document graph edges 

    async def _build_graph_edges(
        self,
        new_node_ids: list[int],
        new_node_embeddings: list[list[float]],
        course_id: int,
    ) -> None:
        """
        So sánh nodes mới với existing nodes trong course.
        Giới hạn MAX_EXISTING_NODES_FOR_GRAPH để tránh N² explosion.
        Sử dụng description_embedding_v2 (1024d) cho BAAI/bge-m3.
        """
        if not new_node_ids:
            return

        async with get_async_conn() as conn:
            existing_rows = await conn.fetch(
                """
                SELECT id, description_embedding_v2
                FROM knowledge_nodes
                WHERE course_id = $1
                  AND id != ALL($2::bigint[])
                  AND description_embedding_v2 IS NOT NULL
                ORDER BY created_at DESC
                LIMIT $3
                """,
                course_id,
                new_node_ids,
                MAX_EXISTING_NODES_FOR_GRAPH,
            )

        if not existing_rows:
            # Không có existing nodes → chỉ tạo edges giữa nodes mới với nhau
            await self._create_intra_document_edges(new_node_ids, new_node_embeddings, course_id)
            return

        # Parse embeddings từ DB
        existing_ids: list[int] = []
        existing_embs: list[list[float]] = []
        for r in existing_rows:
            emb_str = r["description_embedding_v2"]
            if isinstance(emb_str, str):
                emb = [float(x) for x in emb_str.strip("[]").split(",")]
            else:
                emb = list(emb_str)
            existing_ids.append(r["id"])
            existing_embs.append(emb)

        # Vectorized cosine similarity
        new_matrix = np.array(new_node_embeddings)
        existing_matrix = np.array(existing_embs)

        # Normalize
        new_norms = np.linalg.norm(new_matrix, axis=1, keepdims=True) + 1e-8
        exist_norms = np.linalg.norm(existing_matrix, axis=1, keepdims=True) + 1e-8
        new_norm = new_matrix / new_norms
        exist_norm = existing_matrix / exist_norms

        # (n_new, n_existing)
        cross_sims = new_norm @ exist_norm.T

        edges: list[tuple[int, int, float]] = []

        # Cross-document edges
        for i, new_id in enumerate(new_node_ids):
            for j, exist_id in enumerate(existing_ids):
                sim = float(cross_sims[i, j])
                if sim >= RELATION_SIMILARITY_THRESHOLD:
                    edges.append((new_id, exist_id, sim))

        # Intra-document edges (new nodes với nhau)
        intra_sims = new_norm @ new_norm.T
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

        logger.info(f"Created/updated {len(edges)} graph edges for course_id={course_id}")

    async def _create_intra_document_edges(
        self,
        node_ids: list[int],
        embeddings: list[list[float]],
        course_id: int,
    ) -> None:
        """Tạo edges giữa các nodes trong cùng tài liệu."""
        if len(node_ids) < 2:
            return

        matrix = np.array(embeddings)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8
        normed = matrix / norms
        sims = normed @ normed.T

        edges: list[tuple[int, int, float]] = []
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                sim = float(sims[i, j])
                if sim >= RELATION_SIMILARITY_THRESHOLD:
                    edges.append((node_ids[i], node_ids[j], sim))

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

    #  Utility 

    async def _update_content_status(
        self,
        content_id: int,
        status: str,
        error_msg: str | None = None,
    ) -> None:
        async with get_async_conn() as conn:
            await conn.execute(
                "UPDATE section_content SET ai_index_status=$1 WHERE id=$2",
                status, content_id,
            )
        if error_msg:
            logger.warning(f"content_id={content_id} → {status}: {error_msg}")


#  Embedding helper với sub-batching 

async def _batch_embed(texts: list[str]) -> list[list[float]]:
    """
    Embed danh sách texts theo sub-batch để tránh OOM với tài liệu lớn.
    """
    results: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        sub = texts[i: i + EMBED_BATCH_SIZE]
        batch_result = await create_embeddings_batch(sub)
        results.extend(batch_result)
    return results


# Singleton
auto_index_service = AutoIndexService()