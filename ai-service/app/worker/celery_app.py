from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import tempfile

from celery import Celery

from app.core.config import get_settings

logger = logging.getLogger(__name__)
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


# Async runner 
def run_async(coro):
    """Run a coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
    except RuntimeError:
        pass
    return asyncio.run(coro)

@celery_app.task(
    bind=True,
    name="tasks.reindex_content",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=300,
    time_limit=360,
)
def reindex_content_task(self, content_id: int, course_id: int):
    """
    Re-embed all document_chunks for content_id using bge-m3, writing
    results into the embedding_v2 shadow column.

    Called by ReindexService.enqueue_all().  Safe to retry.
    """
    logger.info(f"reindex_content_task: content_id={content_id}")

    async def _run():
        from app.core.database import init_async_pool, close_async_pool
        from app.services.reindex_service import reindex_service

        await init_async_pool()
        try:
            return await reindex_service.reindex_content_sync(
                content_id=content_id,
                course_id=course_id,
            )
        finally:
            await close_async_pool()

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error(f"reindex_content_task failed content_id={content_id}: {exc}", exc_info=True)

        # Mark job as failed in DB
        async def _fail():
            from app.core.database import init_async_pool, close_async_pool, get_async_conn
            await init_async_pool()
            try:
                async with get_async_conn() as conn:
                    await conn.execute(
                        """UPDATE embedding_reindex_jobs
                           SET status='failed', error_message=$1, updated_at=NOW()
                           WHERE content_id=$2""",
                        str(exc)[:300], content_id,
                    )
            finally:
                await close_async_pool()

        run_async(_fail())
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

@celery_app.task(
    bind=True,
    name="tasks.auto_index",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=600,
    time_limit=660,
)
def auto_index_task(
    self,
    content_id: int,
    course_id: int,
    file_url: str,
    content_type: str,
    force: bool = False,
):
    logger.info(f"auto_index_task: content_id={content_id}, force={force}")

    def _update_progress(stage: str, pct: int):
        self.update_state(
            state="PROGRESS",
            meta={"stage": stage, "progress": pct, "content_id": content_id},
        )

    try:
        return run_async(
            _async_auto_index_with_download(
                task=self,
                content_id=content_id,
                course_id=course_id,
                file_url=file_url,
                content_type=content_type,
                force=force,
                progress_callback=_update_progress,
            )
        )
    except Exception as exc:
        logger.error(f"auto_index_task failed content_id={content_id}: {exc}", exc_info=True)
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


async def _async_auto_index_with_download(
    task,
    content_id: int,
    course_id: int,
    file_url: str,
    content_type: str,
    force: bool,
    progress_callback,
) -> dict:
    from app.core.database import init_async_pool, close_async_pool, get_async_conn
    from app.services.auto_index_service import auto_index_service

    await init_async_pool()
    try:
        if not force:
            async with get_async_conn() as conn:
                row = await conn.fetchrow(
                    "SELECT ai_index_status FROM section_content WHERE id=$1", content_id
                )
            if row and row["ai_index_status"] == "indexed":
                return {"ok": True, "skipped": True, "reason": "already_indexed"}

        progress_callback("download", 5)
        file_bytes = await auto_index_service._download_bytes(file_url)

        return await auto_index_service.auto_index(
            content_id=content_id,
            course_id=course_id,
            file_url=file_url,
            content_type=content_type,
            file_bytes=file_bytes,
            progress_callback=progress_callback,
        )
    finally:
        await close_async_pool()


#  Task: Process document (PDF/Video embedding pipeline) 
@celery_app.task(
    bind=True,
    name="tasks.process_document",
    max_retries=3,
    default_retry_delay=60,
)
def process_document_task(
    self,
    job_id: int,
    content_id: int,
    course_id: int,
    node_id: int | None,
    file_url: str,
    content_type: str,
):
    from app.core.database import get_sync_conn, get_sync_cursor

    logger.info(f"process_document_task: job_id={job_id}")

    with get_sync_conn() as conn:
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

        url_lower = file_url.lower()
        ct_lower  = content_type.lower()
        cs, co    = settings.chunk_size, settings.chunk_overlap

        if url_lower.endswith(".pdf") or "pdf" in ct_lower:
            chunks = PDFChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".docx", ".doc")) or "word" in ct_lower:
            chunks = DocxChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".pptx", ".ppt")) or "presentation" in ct_lower:
            chunks = PptxChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".xlsx", ".xls")) or "excel" in ct_lower:
            chunks = ExcelChunker(cs, co).chunk_bytes(file_bytes)
        elif any(url_lower.endswith(e) for e in (".mp4", ".webm", ".mov")) or "video" in ct_lower:
            transcript = _get_or_generate_transcript(content_id, file_bytes)
            chunks = VideoTranscriptChunker().chunk_whisper_json(transcript) if transcript else []
        else:
            text = file_bytes.decode("utf-8", errors="replace")
            raw  = PDFChunker(cs, co)._split_text(text)
            chunks = [DocumentChunk(text=c, index=i, source_type="document",
                                    page_number=1, language=detect_language(c))
                      for i, c in enumerate(raw)]

        if not chunks:
            _mark_job(job_id, "completed", 0)
            return {"chunks_created": 0}

        async def _store():
            from app.services.rag_service import rag_service
            from app.core.database import init_async_pool, close_async_pool
            chunk_dicts = [
                {"text": c.text, "index": c.index, "source_type": c.source_type,
                 "page_number": c.page_number, "start_time_sec": c.start_time_sec,
                 "end_time_sec": c.end_time_sec, "language": c.language}
                for c in chunks
            ]
            await init_async_pool()
            try:
                ids = await rag_service.store_chunks_batch(
                    content_id=content_id, course_id=course_id,
                    chunks=chunk_dicts, node_id=node_id,
                )
                return len(ids)
            finally:
                await close_async_pool()

        n_chunks = run_async(_store())
        _mark_job(job_id, "completed", n_chunks)
        return {"chunks_created": n_chunks}

    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
        _mark_job(job_id, "failed", error=str(exc))
        raise self.retry(exc=exc)


# Helpers 

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


def _get_or_generate_transcript(content_id: int, video_bytes: bytes) -> dict | None:
    from app.core.database import get_sync_conn, get_sync_cursor
    with get_sync_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute("SELECT metadata FROM section_content WHERE id=%s", (content_id,))
            row = cur.fetchone()
            if row and row.get("metadata"):
                meta = row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if "transcript" in meta:
                    return meta["transcript"]

    try:
        import whisper
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name
        model  = whisper.load_model("base")
        result = model.transcribe(tmp_path)
        os.unlink(tmp_path)
        return result
    except ImportError:
        return None


def _mark_job(job_id: int, status: str, chunks: int = 0, error: str = "") -> None:
    from app.core.database import get_sync_conn, get_sync_cursor
    with get_sync_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute(
                """UPDATE document_processing_jobs
                   SET status=%s, chunks_created=%s, completed_at=NOW(),
                       error_message=%s, updated_at=NOW()
                   WHERE id=%s""",
                (status, chunks, error or None, job_id),
            )