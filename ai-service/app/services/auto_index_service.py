"""
ai-service/app/services/auto_index_service.py

Tự động phân tích tài liệu → tạo knowledge nodes → build graph.
Pipeline:
  1. Download + extract text từ MinIO
  2. LLM trích xuất 3-8 chủ đề kiến thức chính (nodes)
  3. Tạo nodes trong DB + embed description của từng node
  4. Chunk document, embed từng chunk
  5. Assign mỗi chunk → node gần nhất (cosine similarity)
  6. Tìm nodes liên quan trong cùng course (cross-document graph)
  7. Tạo knowledge_node_relations
  8. Cập nhật content ai_index_status = 'indexed'
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.database import get_async_conn
from app.core.llm import (
    chat_complete_json,
    create_embedding,
    create_embeddings_batch,
    get_embed_model,
)
from app.services.chunker import PDFChunker, VideoTranscriptChunker, detect_language

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Threshold để tạo graph edge giữa 2 nodes ─────────────────────────────────
RELATION_SIMILARITY_THRESHOLD = 0.62  # tránh noise, chỉ lấy edge thực sự liên quan
MAX_NODES_PER_DOCUMENT = 8            # tránh over-segmentation
MIN_NODES_PER_DOCUMENT = 2            # ít nhất 2 nodes


@dataclass
class ExtractedNode:
    name: str
    name_vi: str
    name_en: str
    description: str
    keywords: list[str]
    order_index: int


# ── LLM Prompts ───────────────────────────────────────────────────────────────

NODE_EXTRACTION_SYSTEM = (
    "Bạn là chuyên gia phân tích giáo trình và thiết kế chương trình học. "
    "Nhiệm vụ: phân tích tài liệu và xác định các chủ đề kiến thức cốt lõi. "
    "Chỉ trả về JSON hợp lệ, không thêm text nào khác."
)

NODE_EXTRACTION_PROMPT = """Phân tích đoạn trích tài liệu sau và xác định {max_nodes} chủ đề kiến thức QUAN TRỌNG NHẤT.

Mỗi chủ đề phải:
- Là một khái niệm/kỹ năng độc lập có thể học và kiểm tra được
- Có đủ nội dung trong tài liệu để tạo ra câu hỏi trắc nghiệm
- Không quá chung chung (ví dụ: "Lập trình") hoặc quá chi tiết (ví dụ: "Cú pháp biến x")

TÀI LIỆU:
{document_excerpt}

Trả về JSON:
{{
  "nodes": [
    {{
      "name": "Tên chủ đề tiếng Việt",
      "name_en": "English topic name",
      "description": "Mô tả ngắn 1-2 câu về chủ đề này trong tài liệu",
      "keywords": ["từ khóa 1", "từ khóa 2", "từ khóa 3"]
    }}
  ]
}}
"""

PREREQUISITE_PROMPT = """Dựa trên các chủ đề kiến thức sau, xác định quan hệ "prerequisite" (tiên quyết).
Quan hệ A→B nghĩa là: cần hiểu A trước mới học được B.
Chỉ tạo quan hệ nếu THỰC SỰ cần thiết, không tạo quá nhiều.

Các chủ đề:
{nodes_list}

Trả về JSON:
{{
  "prerequisites": [
    {{"source_index": 0, "target_index": 2, "reason": "lý do ngắn"}}
  ]
}}
"""


class AutoIndexService:

    # ── Public entry point ─────────────────────────────────────────────────────

    async def auto_index(
        self,
        content_id: int,
        course_id: int,
        file_url: str,
        content_type: str,
        existing_node_ids: list[int] | None = None,
    ) -> dict:
        """
        Full auto-index pipeline. Được gọi từ Celery task.
        Trả về dict kết quả để Celery lưu vào result backend.
        """
        logger.info(f"AutoIndex start: content_id={content_id}, course_id={course_id}")

        try:
            # 1. Download + extract text
            raw_text = await self._download_and_extract(file_url, content_type)
            if not raw_text.strip():
                await self._update_content_status(content_id, "failed", "Empty document")
                return {"ok": False, "error": "Empty document"}

            # 2. Detect language
            language = detect_language(raw_text[:2000])

            # 3. LLM: extract knowledge nodes
            nodes = await self._extract_nodes(raw_text, language)
            if not nodes:
                await self._update_content_status(content_id, "failed", "No nodes extracted")
                return {"ok": False, "error": "No nodes extracted"}

            # 4. Embed node descriptions
            node_descriptions = [
                f"{n.name_vi or n.name}: {n.description}" for n in nodes
            ]
            node_embeddings = await create_embeddings_batch(node_descriptions)

            # 5. Tạo knowledge_nodes trong DB
            node_ids = await self._create_knowledge_nodes(
                nodes, node_embeddings, course_id, content_id
            )

            # 6. LLM: tìm prerequisite relations giữa nodes mới
            await self._create_prerequisite_relations(nodes, node_ids, course_id, language)

            # 7. Chunk document + embed + assign chunks → nodes
            n_chunks = await self._chunk_and_store(
                raw_text, content_id, course_id, node_ids, node_embeddings, language,
                file_url, content_type
            )

            # 8. Build cross-document graph (so sánh với existing nodes)
            await self._build_graph_edges(
                node_ids, node_embeddings, course_id
            )

            # 9. Mark indexed
            await self._update_content_status(content_id, "indexed")

            logger.info(
                f"AutoIndex done: content_id={content_id}, "
                f"nodes={len(node_ids)}, chunks={n_chunks}"
            )
            return {
                "ok": True,
                "node_ids": node_ids,
                "nodes_created": len(node_ids),
                "chunks_created": n_chunks,
                "language": language,
            }

        except Exception as e:
            logger.error(f"AutoIndex failed content_id={content_id}: {e}", exc_info=True)
            await self._update_content_status(content_id, "failed", str(e)[:200])
            raise

    # ── Step 1: Download ───────────────────────────────────────────────────────

    async def _download_and_extract(self, file_url: str, content_type: str) -> str:
        """Download từ MinIO và extract text."""
        import asyncio
        import os
        from minio import Minio
        from app.services.chunker import PDFChunker

        loop = asyncio.get_event_loop()

        def _sync_download() -> bytes:
            client = Minio(
                os.getenv("MINIO_ENDPOINT"),
                access_key=os.getenv("MINIO_ACCESS_KEY"),
                secret_key=os.getenv("MINIO_SECRET_KEY"),
                secure=False,
            )
            response = client.get_object(os.getenv("MINIO_BUCKET"), file_url)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        file_bytes = await loop.run_in_executor(None, _sync_download)

        # Extract text (PDF hoặc text file)
        if "pdf" in content_type.lower() or file_url.endswith(".pdf"):
            chunks = PDFChunker(chunk_size=99999, overlap=0).chunk_bytes(file_bytes)
            return "\n\n".join(c.text for c in chunks)
        else:
            return file_bytes.decode("utf-8", errors="replace")

    # ── Step 2: Extract nodes via LLM ─────────────────────────────────────────

    async def _extract_nodes(self, text: str, language: str) -> list[ExtractedNode]:
        """Dùng LLM để xác định các knowledge nodes từ tài liệu."""
        # Giới hạn text để tiết kiệm token (lấy đầu + cuối + giữa)
        excerpt = self._smart_excerpt(text, max_chars=6000)
        n_nodes = min(MAX_NODES_PER_DOCUMENT, max(MIN_NODES_PER_DOCUMENT, len(text) // 2000))

        prompt = NODE_EXTRACTION_PROMPT.format(
            max_nodes=n_nodes,
            document_excerpt=excerpt,
        )

        messages = [
            {"role": "system", "content": NODE_EXTRACTION_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        result = await chat_complete_json(
            messages=messages,
            model=settings.chat_model,  # dùng model nhanh hơn cho extraction
            temperature=0.2,
            max_tokens=2048,
        )

        raw_nodes = result.get("nodes", [])
        extracted: list[ExtractedNode] = []

        for i, n in enumerate(raw_nodes[:MAX_NODES_PER_DOCUMENT]):
            if not n.get("name"):
                continue
            extracted.append(ExtractedNode(
                name=n.get("name_vi") or n.get("name", ""),
                name_vi=n.get("name_vi") or n.get("name", ""),
                name_en=n.get("name_en") or n.get("name", ""),
                description=n.get("description", ""),
                keywords=n.get("keywords", []),
                order_index=i,
            ))

        logger.info(f"Extracted {len(extracted)} nodes from document")
        return extracted

    def _smart_excerpt(self, text: str, max_chars: int) -> str:
        """Lấy đoạn đại diện của tài liệu (đầu + giữa + cuối)."""
        if len(text) <= max_chars:
            return text
        third = max_chars // 3
        mid_start = len(text) // 2 - third // 2
        return (
            text[:third]
            + "\n\n[...]\n\n"
            + text[mid_start: mid_start + third]
            + "\n\n[...]\n\n"
            + text[-third:]
        )

    # ── Step 3: Create nodes in DB ─────────────────────────────────────────────

    async def _create_knowledge_nodes(
        self,
        nodes: list[ExtractedNode],
        embeddings: list[list[float]],
        course_id: int,
        content_id: int,
    ) -> list[int]:
        """Lưu nodes vào DB, trả về danh sách node_ids."""
        node_ids: list[int] = []

        async with get_async_conn() as conn:
            for node, embedding in zip(nodes, embeddings):
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

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
                    embedding_str,
                    node.order_index,
                    content_id,
                )
                node_ids.append(row["id"])

        logger.info(f"Created {len(node_ids)} knowledge nodes")
        return node_ids

    # ── Step 4: Create prerequisite relations ─────────────────────────────────

    async def _create_prerequisite_relations(
        self,
        nodes: list[ExtractedNode],
        node_ids: list[int],
        course_id: int,
        language: str,
    ) -> None:
        """LLM xác định prerequisite giữa các nodes mới."""
        if len(nodes) < 2:
            return

        nodes_list = "\n".join(
            f"{i}. {n.name_vi} ({n.name_en}): {n.description}"
            for i, n in enumerate(nodes)
        )
        messages = [
            {"role": "system", "content": "Bạn là chuyên gia thiết kế chương trình học. Chỉ trả về JSON hợp lệ."},
            {"role": "user", "content": PREREQUISITE_PROMPT.format(nodes_list=nodes_list)},
        ]

        try:
            result = await chat_complete_json(
                messages=messages,
                model=settings.chat_model,
                temperature=0.1,
                max_tokens=512,
            )
            prerequisites = result.get("prerequisites", [])
        except Exception as e:
            logger.warning(f"Prerequisite extraction failed: {e}")
            return

        async with get_async_conn() as conn:
            for rel in prerequisites:
                src_idx = rel.get("source_index")
                tgt_idx = rel.get("target_index")
                if not (isinstance(src_idx, int) and isinstance(tgt_idx, int)):
                    continue
                if src_idx >= len(node_ids) or tgt_idx >= len(node_ids):
                    continue
                if src_idx == tgt_idx:
                    continue

                await conn.execute(
                    """
                    INSERT INTO knowledge_node_relations
                        (course_id, source_node_id, target_node_id,
                         relation_type, strength, auto_generated)
                    VALUES ($1,$2,$3,'prerequisite',0.9,true)
                    ON CONFLICT (source_node_id, target_node_id, relation_type) DO NOTHING
                    """,
                    course_id,
                    node_ids[src_idx],
                    node_ids[tgt_idx],
                )

    # ── Step 5: Chunk + embed + store ─────────────────────────────────────────

    async def _chunk_and_store(
        self,
        text: str,
        content_id: int,
        course_id: int,
        node_ids: list[int],
        node_embeddings: list[list[float]],
        language: str,
        file_url: str,
        content_type: str,
    ) -> int:
        """Chunk document, embed, assign chunk → closest node, store."""
        from app.services.rag_service import rag_service

        # Chunk dùng existing PDFChunker hoặc text chunker
        from app.services.chunker import PDFChunker, DocumentChunk
        chunker = PDFChunker(
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        text_chunks = chunker._split_text(text)

        if not text_chunks:
            return 0

        # Embed tất cả chunks cùng lúc (batch)
        chunk_embeddings = await create_embeddings_batch(text_chunks)

        # Assign mỗi chunk → node gần nhất
        import numpy as np
        node_emb_matrix = np.array(node_embeddings)  # shape: (n_nodes, dim)

        chunk_dicts: list[dict] = []
        for idx, (chunk_text, chunk_emb) in enumerate(zip(text_chunks, chunk_embeddings)):
            # Cosine similarity với từng node
            chunk_emb_arr = np.array(chunk_emb)
            similarities = node_emb_matrix @ chunk_emb_arr / (
                np.linalg.norm(node_emb_matrix, axis=1) * np.linalg.norm(chunk_emb_arr) + 1e-8
            )
            best_node_local_idx = int(similarities.argmax())
            assigned_node_id = node_ids[best_node_local_idx]

            chunk_dicts.append({
                "text": chunk_text,
                "index": idx,
                "source_type": "document",
                "page_number": None,
                "start_time_sec": None,
                "end_time_sec": None,
                "language": language,
                "_node_id_override": assigned_node_id,
            })

        # Store chunks
        # Cần store với đúng node_id → dùng thẳng raw SQL thay vì rag_service.store_chunks_batch
        # (vì rag_service.store_chunks_batch chỉ nhận 1 node_id cho tất cả chunks)
        n_stored = await self._store_chunks_with_node_assignment(
            content_id, course_id, chunk_dicts, chunk_embeddings
        )
        return n_stored

    async def _store_chunks_with_node_assignment(
        self,
        content_id: int,
        course_id: int,
        chunk_dicts: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        """Store chunks với đúng node_id cho từng chunk."""
        from app.services.rag_service import _sanitize
        import re

        stored = 0
        async with get_async_conn() as conn:
            for chunk, embedding in zip(chunk_dicts, embeddings):
                chunk_text = _sanitize(chunk["text"])
                if not chunk_text.strip():
                    continue

                node_id = chunk.get("_node_id_override")
                chunk_hash = hashlib.sha256(
                    f"{content_id}:{chunk['index']}:{chunk_text}".encode()
                ).hexdigest()
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

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
                    chunk_text, chunk["index"], chunk_hash, embedding_str,
                    chunk.get("source_type", "document"),
                    chunk.get("page_number"),
                    chunk.get("start_time_sec"),
                    chunk.get("end_time_sec"),
                    chunk.get("language", "vi"),
                )
                stored += 1

        return stored

    # ── Step 6: Build cross-document graph ────────────────────────────────────

    async def _build_graph_edges(
        self,
        new_node_ids: list[int],
        new_node_embeddings: list[list[float]],
        course_id: int,
    ) -> None:
        """
        So sánh nodes mới với TẤT CẢ nodes hiện có trong course.
        Nếu cosine similarity > threshold → tạo 'related' edge.
        """
        if not new_node_ids:
            return

        async with get_async_conn() as conn:
            # Lấy tất cả nodes hiện có trong course (trừ nodes vừa tạo)
            existing_rows = await conn.fetch(
                """
                SELECT id, description_embedding
                FROM knowledge_nodes
                WHERE course_id = $1
                  AND id != ALL($2::bigint[])
                  AND description_embedding IS NOT NULL
                """,
                course_id,
                new_node_ids,
            )

        if not existing_rows:
            return

        import numpy as np
        existing_ids = [r["id"] for r in existing_rows]
        existing_embs = []
        for r in existing_rows:
            # asyncpg trả về string dạng "[0.1,0.2,...]"
            emb_str = r["description_embedding"]
            if isinstance(emb_str, str):
                emb = [float(x) for x in emb_str.strip("[]").split(",")]
            else:
                emb = list(emb_str)
            existing_embs.append(emb)

        existing_matrix = np.array(existing_embs)

        edges_to_create: list[tuple[int, int, float]] = []

        for new_id, new_emb in zip(new_node_ids, new_node_embeddings):
            new_arr = np.array(new_emb)
            # Cosine similarity với tất cả existing nodes
            norms = np.linalg.norm(existing_matrix, axis=1) * np.linalg.norm(new_arr) + 1e-8
            sims = existing_matrix @ new_arr / norms

            for exist_id, sim in zip(existing_ids, sims.tolist()):
                if sim >= RELATION_SIMILARITY_THRESHOLD:
                    edges_to_create.append((new_id, exist_id, float(sim)))

        # Cũng so sánh các nodes mới với nhau
        new_matrix = np.array(new_node_embeddings)
        for i, (id_a, emb_a) in enumerate(zip(new_node_ids, new_node_embeddings)):
            for j, (id_b, emb_b) in enumerate(zip(new_node_ids, new_node_embeddings)):
                if i >= j:
                    continue
                sim = float(
                    np.dot(emb_a, emb_b)
                    / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-8)
                )
                if sim >= RELATION_SIMILARITY_THRESHOLD:
                    edges_to_create.append((id_a, id_b, sim))

        if not edges_to_create:
            return

        async with get_async_conn() as conn:
            for src, tgt, strength in edges_to_create:
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

        logger.info(f"Created/updated {len(edges_to_create)} graph edges")

    # ── Utility ───────────────────────────────────────────────────────────────

    async def _update_content_status(
        self,
        content_id: int,
        status: str,
        error_msg: str | None = None,
    ) -> None:
        async with get_async_conn() as conn:
            await conn.execute(
                "UPDATE section_content SET ai_index_status=$1 WHERE id=$2",
                status,
                content_id,
            )
        if error_msg:
            logger.warning(f"content_id={content_id} status={status}: {error_msg}")


auto_index_service = AutoIndexService()