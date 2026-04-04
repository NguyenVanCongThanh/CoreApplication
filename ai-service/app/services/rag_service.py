from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.core.database import get_async_conn
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _sanitize(text: str) -> str:
    import re
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

_IS_BGE = "bge" in settings.embedding_model.lower()
_SEARCH_COL   = "embedding"
_SEARCH_OP    = f"{_SEARCH_COL} <=> $1::vector"


@dataclass
class RetrievedChunk:
    chunk_id: int
    chunk_text: str
    similarity: float
    source_type: str
    page_number: int | None
    start_time_sec: int | None
    end_time_sec: int | None
    content_id: int | None
    node_id: int | None
    language: str


class RAGService:
    # Storage
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
        from app.core.embeddings import create_passage_embedding
        chunk_text = _sanitize(chunk_text)
        chunk_hash = hashlib.sha256(
            f"{content_id}:{chunk_index}:{chunk_text}".encode()
        ).hexdigest()

        embedding = await create_passage_embedding(chunk_text)
        emb_str   = "[" + ",".join(str(v) for v in embedding) + "]"

        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO document_chunks
                    (content_id, course_id, node_id, chunk_text, chunk_index,
                     chunk_hash, {_SEARCH_COL}, source_type, page_number,
                     start_time_sec, end_time_sec, language, status,
                     embedding_model)
                VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12,'ready',$13)
                ON CONFLICT (chunk_hash) DO UPDATE
                    SET {_SEARCH_COL} = EXCLUDED.{_SEARCH_COL},
                        embedding_model = EXCLUDED.embedding_model,
                        status = 'ready'
                RETURNING id
                """,
                content_id, course_id, node_id, chunk_text, chunk_index,
                chunk_hash, emb_str, source_type, page_number,
                start_time_sec, end_time_sec, language,
                settings.embedding_model,
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
        Bulk-store chunks using a single asyncpg executemany() transaction.

        Each chunk dict: {text, index, source_type, page_number?,
                          start_time_sec?, end_time_sec?, language?}

        Performance note
        ----------------
        asyncpg executemany() pipelines all INSERTs in one round-trip,
        reducing per-chunk latency from ~2 ms to ~0.1 ms — a 10-20x speedup
        for 200+ chunk documents.  The trade-off is that RETURNING is not
        supported with executemany, so we query the inserted IDs in a
        second (cheap) SELECT.
        """
        from app.core.embeddings import create_passage_embeddings_batch

        if not chunks:
            return []

        # Sanitise
        for c in chunks:
            c["text"] = _sanitize(c["text"])

        # Embed in sub-batches to avoid OOM
        texts = [c["text"] for c in chunks]
        EMBED_BATCH = 32
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            batch_embs = await create_passage_embeddings_batch(texts[i: i + EMBED_BATCH])
            embeddings.extend(batch_embs)

        # Build records for executemany
        hashes: list[str] = []
        records: list[tuple] = []
        for chunk, emb in zip(chunks, embeddings):
            h = hashlib.sha256(
                f"{content_id}:{chunk['index']}:{chunk['text']}".encode()
            ).hexdigest()
            hashes.append(h)
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            records.append((
                content_id,
                course_id,
                node_id,
                chunk["text"],
                chunk["index"],
                h,
                emb_str,
                chunk.get("source_type", "document"),
                chunk.get("page_number"),
                chunk.get("start_time_sec"),
                chunk.get("end_time_sec"),
                chunk.get("language", "vi"),
                settings.embedding_model,
            ))

        sql = f"""
            INSERT INTO document_chunks
                (content_id, course_id, node_id, chunk_text, chunk_index,
                 chunk_hash, {_SEARCH_COL}, source_type, page_number,
                 start_time_sec, end_time_sec, language, status, embedding_model)
            VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12,'ready',$13)
            ON CONFLICT (chunk_hash) DO UPDATE
                SET {_SEARCH_COL}    = EXCLUDED.{_SEARCH_COL},
                    embedding_model  = EXCLUDED.embedding_model,
                    status           = 'ready'
        """

        async with get_async_conn() as conn:
            async with conn.transaction():
                await conn.executemany(sql, records)

            # Fetch inserted/updated IDs
            rows = await conn.fetch(
                "SELECT id FROM document_chunks WHERE chunk_hash = ANY($1)",
                hashes,
            )

        return [r["id"] for r in rows]

    
    # Retrieval
    

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
        Semantic search via pgvector cosine similarity.

        During migration, fetches `rerank_fetch_k` candidates (default 15)
        and the caller decides whether to rerank.  Pass top_k to cap results
        before reranking when you know you won't rerank (e.g., internal calls).
        """
        from app.core.embeddings import create_embedding

        fetch_k = settings.rerank_fetch_k if settings.use_reranker else (top_k or settings.top_k_chunks)

        query_embedding = await create_embedding(query)
        emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Build WHERE clause
        conditions = [f"status = 'ready'", f"{_SEARCH_COL} IS NOT NULL"]
        params: list = [emb_str, fetch_k]
        idx = 3

        if course_id is not None:
            conditions.append(f"course_id = ${idx}")
            params.append(course_id); idx += 1
        if node_id is not None:
            conditions.append(f"node_id = ${idx}")
            params.append(node_id); idx += 1
        if content_id is not None:
            conditions.append(f"content_id = ${idx}")
            params.append(content_id); idx += 1

        where = " AND ".join(conditions)

        sql = f"""
            SELECT
                id, chunk_text, content_id, node_id,
                source_type, page_number, start_time_sec, end_time_sec, language,
                1 - ({_SEARCH_OP}) AS similarity
            FROM document_chunks
            WHERE {where}
              AND 1 - ({_SEARCH_OP}) >= {min_similarity}
            ORDER BY {_SEARCH_COL} <=> $1::vector
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

    async def _search_and_rerank(
        self,
        query: str,
        top_k: int,
        **search_kwargs,
    ) -> list[RetrievedChunk]:
        """
        Fetch up to rerank_fetch_k candidates from pgvector,
        then rerank with the cross-encoder, returning top_k.
        """
        candidates = await self.search(query=query, **search_kwargs)

        if not candidates or not settings.use_reranker:
            return candidates[:top_k]

        from app.core.embeddings import rerank_chunks
        return await rerank_chunks(
            query=query,
            chunks=candidates,
            text_fn=lambda c: c.chunk_text,
            top_k=top_k,
        )

    async def search_multilingual(
        self,
        query: str,
        course_id: int | None = None,
        node_id: int | None = None,
        content_id: int | None = None,
        top_k: int | None = None,
        min_similarity: float = 0.25,
    ) -> list[RetrievedChunk]:
        """
        Main public search method.

        Pipeline (bge-m3 native mode):
          pgvector ANN  →  cross-encoder rerank  →  top_k results

        Pipeline (nomic translation mode):
          translate  →  dual pgvector search  →  RRF merge  →  rerank  →  top_k
        """
        from app.core.multilingual import multilingual_search

        top_k = top_k or settings.top_k_chunks

        # Run multilingual retrieval (returns up to rerank_fetch_k candidates)
        candidates = await multilingual_search(
            search_fn=self.search,
            query=query,
            top_k=top_k if not settings.use_reranker else settings.rerank_fetch_k,
            id_fn=lambda c: c.chunk_id,
            min_similarity=min_similarity,
            course_id=course_id,
            node_id=node_id,
            content_id=content_id,
        )

        if not candidates or not settings.use_reranker:
            return candidates[:top_k]

        # Rerank
        from app.core.embeddings import rerank_chunks
        return await rerank_chunks(
            query=query,
            chunks=candidates,
            text_fn=lambda c: c.chunk_text,
            top_k=top_k,
        )

    async def search_for_question(
        self,
        question_id: int,
        course_id: int,
        top_k: int = 3,
    ) -> list[RetrievedChunk]:
        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                "SELECT question_text, node_id, reference_chunk_id FROM quiz_questions WHERE id = $1",
                question_id,
            )
        if not row:
            return []

        pinned: list[RetrievedChunk] = []
        if row["reference_chunk_id"]:
            async with get_async_conn() as conn:
                c = await conn.fetchrow(
                    """SELECT id, chunk_text, content_id, node_id,
                              source_type, page_number, start_time_sec, end_time_sec, language
                       FROM document_chunks WHERE id = $1""",
                    row["reference_chunk_id"],
                )
            if c:
                pinned = [RetrievedChunk(
                    chunk_id=c["id"], chunk_text=c["chunk_text"], similarity=1.0,
                    source_type=c["source_type"], page_number=c["page_number"],
                    start_time_sec=c["start_time_sec"], end_time_sec=c["end_time_sec"],
                    content_id=c["content_id"], node_id=c["node_id"],
                    language=c["language"],
                )]

        semantic = await self.search_multilingual(
            query=row["question_text"],
            course_id=course_id,
            node_id=row["node_id"],
            top_k=top_k,
        )

        seen = {c.chunk_id for c in pinned}
        result = list(pinned)
        for chunk in semantic:
            if chunk.chunk_id not in seen:
                result.append(chunk)
                seen.add(chunk.chunk_id)

        return result[:top_k]

    async def delete_chunks_for_content(self, content_id: int) -> int:
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