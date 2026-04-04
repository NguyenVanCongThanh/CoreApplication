from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.database import get_async_conn

logger = logging.getLogger(__name__)
settings = get_settings()


class ReindexService:

    async def enqueue_all(self, course_id: int | None = None) -> dict:
        """
        Create one embedding_reindex_jobs row per section_content item
        that has at least one indexed chunk and hasn't been migrated yet.
        Returns summary counts.
        """
        from app.worker.celery_app import reindex_content_task

        async with get_async_conn() as conn:
            # Find content items that need re-indexing
            rows = await conn.fetch(
                """
                SELECT DISTINCT sc.id AS content_id, sc.section_id,
                       cs.course_id
                FROM section_content sc
                JOIN course_sections cs ON cs.id = sc.section_id
                JOIN document_chunks dc ON dc.content_id = sc.id
                WHERE dc.embedding IS NULL
                  AND ($1::BIGINT IS NULL OR cs.course_id = $1)
                ORDER BY sc.id
                """,
                course_id,
            )

        if not rows:
            return {"enqueued": 0, "message": "Nothing to reindex"}

        # Insert tracking rows (skip existing pending/processing)
        async with get_async_conn() as conn:
            await conn.executemany(
                """
                INSERT INTO embedding_reindex_jobs
                    (course_id, content_id, status)
                VALUES ($1, $2, 'pending')
                ON CONFLICT DO NOTHING
                """,
                [(r["course_id"], r["content_id"]) for r in rows],
            )

        # Enqueue Celery tasks in batches
        batch = settings.reindex_batch_size
        enqueued = 0
        for i in range(0, len(rows), batch):
            for row in rows[i: i + batch]:
                reindex_content_task.delay(
                    content_id=row["content_id"],
                    course_id=row["course_id"],
                )
                enqueued += 1

        logger.info(f"Enqueued {enqueued} reindex jobs")
        return {"enqueued": enqueued}

    async def get_progress(self) -> dict:
        """Return aggregate progress from the v_reindex_progress view."""
        async with get_async_conn() as conn:
            row = await conn.fetchrow("SELECT * FROM v_reindex_progress")
        return dict(row) if row else {}

    async def reindex_content_sync(self, content_id: int, course_id: int) -> dict:
        """
        Re-embed all chunks for a single content_id using bge-m3.
        Called by the Celery task; can also be awaited directly in tests.
        """
        from app.core.embeddings import create_passage_embeddings_batch

        # Mark job as processing
        async with get_async_conn() as conn:
            await conn.execute(
                """
                UPDATE embedding_reindex_jobs
                SET status = 'processing', started_at = NOW(), updated_at = NOW()
                WHERE content_id = $1
                """,
                content_id,
            )
            rows = await conn.fetch(
                "SELECT id, chunk_text FROM document_chunks WHERE content_id = $1 ORDER BY id",
                content_id,
            )

        if not rows:
            await self._mark_job(content_id, "done", 0, 0)
            return {"chunks": 0}

        chunk_ids   = [r["id"] for r in rows]
        chunk_texts = [r["chunk_text"] for r in rows]

        # Embed in sub-batches
        BATCH = 32
        all_embeddings: list[list[float]] = []
        for i in range(0, len(chunk_texts), BATCH):
            batch_embs = await create_passage_embeddings_batch(chunk_texts[i: i + BATCH])
            all_embeddings.extend(batch_embs)

        # Bulk-update embedding
        records = [
            ("[" + ",".join(str(v) for v in emb) + "]", cid)
            for cid, emb in zip(chunk_ids, all_embeddings)
        ]

        async with get_async_conn() as conn:
            async with conn.transaction():
                await conn.executemany(
                    "UPDATE document_chunks SET embedding = $1::vector, embedding_model = 'bge-m3' WHERE id = $2",
                    records,
                )

        # Update knowledge_nodes description_embedding for this content
        await self._reindex_node_embeddings(content_id)

        await self._mark_job(content_id, "done", len(chunk_ids), len(chunk_ids))
        logger.info(f"Reindexed {len(chunk_ids)} chunks for content_id={content_id}")
        return {"chunks": len(chunk_ids)}

    async def _reindex_node_embeddings(self, content_id: int) -> None:
        """Re-embed knowledge_node descriptions for nodes derived from this content."""
        from app.core.embeddings import create_passage_embeddings_batch

        async with get_async_conn() as conn:
            node_rows = await conn.fetch(
                "SELECT id, name, description FROM knowledge_nodes WHERE source_content_id = $1",
                content_id,
            )
        if not node_rows:
            return

        texts = [
            f"{r['name']}: {r['description'] or ''}"
            for r in node_rows
        ]
        embeddings = await create_passage_embeddings_batch(texts)

        records = [
            ("[" + ",".join(str(v) for v in emb) + "]", r["id"])
            for r, emb in zip(node_rows, embeddings)
        ]
        async with get_async_conn() as conn:
            async with conn.transaction():
                await conn.executemany(
                    "UPDATE knowledge_nodes SET description_embedding = $1::vector WHERE id = $2",
                    records,
                )

    async def _mark_job(
        self,
        content_id: int,
        status: str,
        chunks_total: int,
        chunks_done: int,
        error: str | None = None,
    ) -> None:
        async with get_async_conn() as conn:
            await conn.execute(
                """
                UPDATE embedding_reindex_jobs
                SET status = $1, chunks_total = $2, chunks_done = $3,
                    error_message = $4, completed_at = NOW(), updated_at = NOW()
                WHERE content_id = $5
                """,
                status, chunks_total, chunks_done, error, content_id,
            )


reindex_service = ReindexService()