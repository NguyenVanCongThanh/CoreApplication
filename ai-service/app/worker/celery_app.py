from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import tempfile

from celery import Celery

from app.core.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "ai_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_time_limit - 60,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)


# ── Async runner ───────────────────────────────────────────────────────────────

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


# ── Helper: init AI pool only, run coro, close pool ───────────────────────────

async def _with_pools(coro_fn):
    """
    Open AI DB pool, run coro_fn(), close pool.
    LMS pool is no longer needed — AI service is fully independent.
    """
    from app.core.llm import reset_async_clients
    from app.core.database import init_ai_pool, close_ai_pool
    from app.services.qdrant_service import qdrant_service
    
    reset_async_clients()
    
    await init_ai_pool()
    try:
        return await coro_fn()
    finally:
        await asyncio.gather(close_ai_pool(), qdrant_service.close())


# ── Tasks ──────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True, name="tasks.reindex_content",
    max_retries=3, default_retry_delay=60,
    soft_time_limit=300, time_limit=360,
)
def reindex_content_task(self, content_id: int, course_id: int):
    logger.info("reindex_content_task: content_id=%d", content_id)

    async def _run():
        from app.services.reindex_service import reindex_service
        return await reindex_service.reindex_content_sync(
            content_id=content_id, course_id=course_id,
        )

    try:
        return run_async(_with_pools(_run))
    except Exception as exc:
        logger.error("reindex_content_task failed content_id=%d: %s", content_id, exc, exc_info=True)

        async def _fail():
            from app.core.database import init_ai_pool, close_ai_pool, get_ai_conn
            await init_ai_pool()
            try:
                async with get_ai_conn() as conn:
                    await conn.execute(
                        """UPDATE embedding_reindex_jobs
                           SET status='failed', error_message=$1, updated_at=NOW()
                           WHERE content_id=$2""",
                        str(exc)[:300], content_id,
                    )
            finally:
                await close_ai_pool()

        run_async(_fail())
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(
    bind=True, name="tasks.auto_index",
    max_retries=2, default_retry_delay=30,
    soft_time_limit=600, time_limit=660,
)
def auto_index_task(self, content_id, course_id, file_url, content_type, force=False):
    logger.info("auto_index_task: content_id=%d force=%s", content_id, force)

    def _progress(stage, pct):
        self.update_state(
            state="PROGRESS",
            meta={"stage": stage, "progress": pct, "content_id": content_id},
        )

    try:
        return run_async(_with_pools(
            lambda: _async_auto_index(
                content_id=content_id, course_id=course_id,
                file_url=file_url, content_type=content_type,
                force=force, progress_cb=_progress,
            )
        ))
    except Exception as exc:
        logger.error("auto_index_task failed content_id=%d: %s", content_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@celery_app.task(
    bind=True, name="tasks.auto_index_text",
    max_retries=3, default_retry_delay=30, time_limit=660,
)
def auto_index_text_task(self, content_id, course_id, title, text_content, force=False):
    logger.info("auto_index_text_task: content_id=%d title=%s", content_id, title)

    def _progress(stage, pct):
        self.update_state(
            state="PROGRESS",
            meta={"stage": stage, "progress": pct, "content_id": content_id},
        )

    try:
        return run_async(_with_pools(
            lambda: _async_auto_index_text(
                content_id=content_id, course_id=course_id,
                title=title, text_content=text_content,
                force=force, progress_cb=_progress,
            )
        ))
    except Exception as exc:
        logger.error("auto_index_text_task failed content_id=%d: %s", content_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@celery_app.task(
    bind=True, name="tasks.process_document",
    max_retries=3, default_retry_delay=60,
)
def process_document_task(
    self, job_id, content_id, course_id, node_id, file_url, content_type
):
    from app.core.database import get_sync_ai_conn, get_sync_cursor

    logger.info("process_document_task: job_id=%d", job_id)

    with get_sync_ai_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute(
                "UPDATE document_processing_jobs SET status='processing', started_at=NOW() WHERE id=%s",
                (job_id,),
            )

    try:
        file_bytes = _download_file(file_url)

        from app.services.chunker import (
            PDFChunker, DocxChunker, PptxChunker, ExcelChunker,
            VideoTranscriptChunker, DocumentChunk, detect_language,
        )
        cs, co    = settings.chunk_size, settings.chunk_overlap
        url_lower = file_url.lower()
        ct_lower  = content_type.lower()

        if url_lower.endswith(".pdf") or "pdf" in ct_lower:
            chunks = PDFChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".docx", ".doc")) or "word" in ct_lower:
            chunks = DocxChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".pptx", ".ppt")) or "presentation" in ct_lower:
            chunks = PptxChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".xlsx", ".xls")) or "excel" in ct_lower:
            chunks = ExcelChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".md", ".markdown", ".txt")) or ct_lower in (
            "text", "markdown", "text/markdown", "text/plain"
        ):
            from app.services.chunker import MarkdownChunker
            chunks = MarkdownChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".png", ".jpg", ".jpeg", ".gif", ".webp")) or ct_lower.startswith("image/"):
            from app.services.chunker import ImageChunker
            chunks = ImageChunker().chunk_bytes(file_bytes)
        else:
            text  = file_bytes.decode("utf-8", errors="replace")
            raw   = PDFChunker(cs, co)._split_text(text)
            chunks = [
                DocumentChunk(text=c, index=i, source_type="document",
                              page_number=1, language=detect_language(c))
                for i, c in enumerate(raw)
            ]

        if not chunks:
            _mark_ai_job(job_id, "completed", 0)
            return {"chunks_created": 0}

        async def _store():
            from app.services.rag_service import rag_service
            chunk_dicts = [
                {"text": c.text, "index": c.index, "source_type": c.source_type,
                 "page_number": c.page_number, "start_time_sec": c.start_time_sec,
                 "end_time_sec": c.end_time_sec, "language": c.language}
                for c in chunks
            ]
            ids = await rag_service.store_chunks_batch(
                content_id=content_id, course_id=course_id,
                chunks=chunk_dicts, node_id=node_id,
            )
            return len(ids)

        n_chunks = run_async(_with_pools(lambda: _store()))
        _mark_ai_job(job_id, "completed", n_chunks)
        return {"chunks_created": n_chunks}

    except Exception as exc:
        logger.error("Job %d failed: %s", job_id, exc, exc_info=True)
        _mark_ai_job(job_id, "failed", error=str(exc))
        raise self.retry(exc=exc)


# ── Async task helpers ─────────────────────────────────────────────────────────

async def _async_auto_index(content_id, course_id, file_url, content_type, force, progress_cb):
    from app.core.llm import reset_async_clients
    from app.core.database import get_ai_conn
    from app.services.auto_index_service import auto_index_service

    reset_async_clients()

    if not force:
        # Check status from AI DB instead of LMS DB
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                "SELECT status FROM content_index_status WHERE content_id=$1", content_id
            )
        if row and row["status"] == "indexed":
            return {"ok": True, "skipped": True, "reason": "already_indexed"}

    progress_cb("download", 5)
    file_bytes = await auto_index_service._download_bytes(file_url)
    return await auto_index_service.auto_index(
        content_id=content_id, course_id=course_id,
        file_url=file_url, content_type=content_type,
        file_bytes=file_bytes, progress_callback=progress_cb,
    )


async def _async_auto_index_text(content_id, course_id, title, text_content, force, progress_cb):
    from app.core.llm import reset_async_clients
    from app.core.database import get_ai_conn
    from app.services.auto_index_service import auto_index_service

    reset_async_clients()

    if not force:
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                "SELECT status FROM content_index_status WHERE content_id=$1", content_id
            )
        if row and row["status"] == "indexed":
            return {"ok": True, "skipped": True, "reason": "already_indexed"}

    progress_cb("parse", 5)
    return await auto_index_service.auto_index_text(
        content_id=content_id, course_id=course_id,
        title=title, text_content=text_content,
        progress_callback=progress_cb,
    )


# ── Sync helpers ───────────────────────────────────────────────────────────────

def _download_file(url: str) -> bytes:
    from minio import Minio
    client = Minio(
        os.getenv("MINIO_ENDPOINT", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=False,
    )
    response = client.get_object(os.getenv("MINIO_BUCKET", "lms-files"), url)
    try:
        buf = io.BytesIO()
        for chunk in response.stream(1 * 1024 * 1024):
            buf.write(chunk)
        return buf.getvalue()
    finally:
        response.close()
        response.release_conn()


def _mark_ai_job(job_id: int, status: str, chunks: int = 0, error: str = "") -> None:
    from app.core.database import get_sync_ai_conn, get_sync_cursor
    with get_sync_ai_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute(
                """UPDATE document_processing_jobs
                   SET status=%s, chunks_created=%s, completed_at=NOW(),
                       error_message=%s, updated_at=NOW()
                   WHERE id=%s""",
                (status, chunks, error or None, job_id),
            )