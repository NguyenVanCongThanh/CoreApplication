"""
ai-service/app/services/rag_service.py
Retrieval-Augmented Generation service.
- Semantic search via pgvector cosine similarity
- Context assembly for LLM prompts
- Chunk storage and retrieval
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.core.database import get_async_conn
from app.core.llm import create_embedding, create_embeddings_batch
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _sanitize(text: str) -> str:
    """
    Safety net: strip null bytes and other PostgreSQL-incompatible control chars.
    Primary sanitization happens in chunker.py; this is a second line of defense.
    """
    import re
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


@dataclass
class RetrievedChunk:
    chunk_id: int
    chunk_text: str
    similarity: float
    source_type: str          # 'document' | 'video'
    page_number: int | None
    start_time_sec: int | None
    end_time_sec: int | None
    content_id: int | None
    node_id: int | None
    language: str


class RAGService:
    """
    Core RAG engine.
    Stores document chunks with embeddings and retrieves
    the most relevant ones for a given query.
    """

    # ── Storage ──────────────────────────────────────────────────────────────

    async def store_chunk(
        self,
        content_id: int,
        course_id: int,
        chunk_text: str,
        chunk_index: int,
        node_id: int | None = None,
        source_type: str = "document",
        page_number: int | None = None,
        start_time_sec: int | None = None,
        end_time_sec: int | None = None,
        language: str = "vi",
    ) -> int:
        """Embed and store a single chunk. Returns chunk_id."""
        chunk_text = _sanitize(chunk_text)
        chunk_hash = hashlib.sha256(f"{content_id}:{chunk_index}:{chunk_text}".encode()).hexdigest()

        embedding = await create_embedding(chunk_text)
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO document_chunks
                    (content_id, course_id, node_id, chunk_text, chunk_index, chunk_hash,
                     embedding, source_type, page_number, start_time_sec, end_time_sec, language, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12,'ready')
                ON CONFLICT (chunk_hash) DO UPDATE
                    SET embedding = EXCLUDED.embedding,
                        status    = 'ready'
                RETURNING id
                """,
                content_id, course_id, node_id, chunk_text, chunk_index, chunk_hash,
                embedding_str, source_type, page_number, start_time_sec, end_time_sec, language,
            )
        return row["id"]

    async def store_chunks_batch(
        self,
        content_id: int,
        course_id: int,
        chunks: list[dict],
        node_id: int | None = None,
    ) -> list[int]:
        """
        Batch store for efficiency. Each chunk dict:
        {text, index, source_type, page_number?, start_time_sec?, end_time_sec?, language?}
        """
        for chunk in chunks:
            chunk["text"] = _sanitize(chunk["text"])

        texts = [c["text"] for c in chunks]
        
        # Process in smaller sub-batches to avoid memory spikes
        batch_size = 16
        embeddings = []
        for i in range(0, len(texts), batch_size):
            sub_batch = texts[i : i + batch_size]
            sub_embeddings = await create_embeddings_batch(sub_batch)
            embeddings.extend(sub_embeddings)

        chunk_ids: list[int] = []
        async with get_async_conn() as conn:
            for chunk, embedding in zip(chunks, embeddings):
                chunk_hash = hashlib.sha256(
                    f"{content_id}:{chunk['index']}:{chunk['text']}".encode()
                ).hexdigest()
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

                row = await conn.fetchrow(
                    """
                    INSERT INTO document_chunks
                        (content_id, course_id, node_id, chunk_text, chunk_index, chunk_hash,
                         embedding, source_type, page_number, start_time_sec, end_time_sec,
                         language, status)
                    VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12,'ready')
                    ON CONFLICT (chunk_hash) DO UPDATE
                        SET embedding = EXCLUDED.embedding, status = 'ready'
                    RETURNING id
                    """,
                    content_id, course_id, node_id,
                    chunk["text"], chunk["index"], chunk_hash,
                    embedding_str,
                    chunk.get("source_type", "document"),
                    chunk.get("page_number"),
                    chunk.get("start_time_sec"),
                    chunk.get("end_time_sec"),
                    chunk.get("language", "vi"),
                )
                chunk_ids.append(row["id"])

        return chunk_ids

    # ── Retrieval ─────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        course_id: int | None = None,
        node_id: int | None = None,
        content_id: int | None = None,
        top_k: int | None = None,
        min_similarity: float = 0.30,
    ) -> list[RetrievedChunk]:
        """
        Semantic search using pgvector cosine similarity.
        Returns top-k most relevant chunks.
        """
        top_k = top_k or settings.top_k_chunks
        query_embedding = await create_embedding(query)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Build dynamic WHERE clause
        conditions = ["status = 'ready'"]
        params: list = [embedding_str, top_k]
        idx = 3

        if course_id is not None:
            conditions.append(f"course_id = ${idx}")
            params.append(course_id)
            idx += 1
        if node_id is not None:
            conditions.append(f"node_id = ${idx}")
            params.append(node_id)
            idx += 1
        if content_id is not None:
            conditions.append(f"content_id = ${idx}")
            params.append(content_id)
            idx += 1

        where = " AND ".join(conditions)

        sql = f"""
            SELECT
                id, chunk_text, content_id, node_id,
                source_type, page_number, start_time_sec, end_time_sec, language,
                1 - (embedding <=> $1::vector) AS similarity
            FROM document_chunks
            WHERE {where}
              AND 1 - (embedding <=> $1::vector) >= {min_similarity}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """

        async with get_async_conn() as conn:
            rows = await conn.fetch(sql, *params)

        return [
            RetrievedChunk(
                chunk_id=r["id"],
                chunk_text=r["chunk_text"],
                similarity=float(r["similarity"]),
                source_type=r["source_type"],
                page_number=r["page_number"],
                start_time_sec=r["start_time_sec"],
                end_time_sec=r["end_time_sec"],
                content_id=r["content_id"],
                node_id=r["node_id"],
                language=r["language"],
            )
            for r in rows
        ]

    async def search_for_question(
        self,
        question_id: int,
        course_id: int,
        top_k: int = 3,
    ) -> list[RetrievedChunk]:
        """
        Given a quiz question, find the most relevant chunks.
        Useful for error diagnosis when student answers wrong.
        """
        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                "SELECT question_text, node_id, reference_chunk_id FROM quiz_questions WHERE id = $1",
                question_id,
            )

        if not row:
            return []

        pinned_chunks: list[RetrievedChunk] = []
        if row["reference_chunk_id"]:
            async with get_async_conn() as conn:
                c = await conn.fetchrow(
                    """SELECT id, chunk_text, content_id, node_id,
                              source_type, page_number, start_time_sec, end_time_sec, language
                       FROM document_chunks WHERE id = $1""",
                    row["reference_chunk_id"],
                )
            if c:
                pinned_chunks = [
                    RetrievedChunk(
                        chunk_id=c["id"], chunk_text=c["chunk_text"],
                        similarity=1.0, source_type=c["source_type"],
                        page_number=c["page_number"], start_time_sec=c["start_time_sec"],
                        end_time_sec=c["end_time_sec"], content_id=c["content_id"],
                        node_id=c["node_id"], language=c["language"],
                    )
                ]

        semantic = await self.search(
            query=row["question_text"],
            course_id=course_id,
            node_id=row["node_id"],
            top_k=top_k,
        )

        seen_ids = {c.chunk_id for c in pinned_chunks}
        result = list(pinned_chunks)
        for chunk in semantic:
            if chunk.chunk_id not in seen_ids:
                result.append(chunk)
                seen_ids.add(chunk.chunk_id)

        return result[:top_k]

    async def delete_chunks_for_content(self, content_id: int) -> int:
        """Remove all chunks for a content item (e.g., when file is re-uploaded)."""
        async with get_async_conn() as conn:
            result = await conn.execute(
                "DELETE FROM document_chunks WHERE content_id = $1", content_id
            )
        deleted = int(result.split()[-1])
        logger.info(f"Deleted {deleted} chunks for content_id={content_id}")
        return deleted

    async def get_chunk(self, chunk_id: int) -> dict | None:
        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                """SELECT id, chunk_text, content_id, node_id,
                          source_type, page_number, start_time_sec, end_time_sec, language
                   FROM document_chunks WHERE id = $1""",
                chunk_id,
            )
        return dict(row) if row else None


# Singleton
rag_service = RAGService()