"""
ai-service/app/worker/celery_app.py
Celery worker for heavy async tasks:
- PDF/Video processing and embedding
- Batch quiz generation
These run outside of the HTTP request cycle to avoid timeouts.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import tempfile

import httpx
from celery import Celery

from app.core.config import get_settings

from minio import Minio

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Celery app ────────────────────────────────────────────────────────────────
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
    worker_prefetch_multiplier=1,  # prevent memory overload on large PDFs
    task_acks_late=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)


def run_async(coro):
    """Run coroutine in sync Celery task context."""
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


# ── Task: Process document (PDF/Video) ───────────────────────────────────────

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
    content_type: str,  # 'application/pdf' | 'video/mp4' | ...
):
    """
    Download file from MinIO, chunk it, embed, store in pgvector.
    Updates document_processing_jobs status throughout.
    """
    from app.core.database import get_sync_conn, get_sync_cursor
    from app.services.chunker import PDFChunker, VideoTranscriptChunker

    logger.info(f"Processing job_id={job_id} content_id={content_id}")

    # Mark job as processing
    with get_sync_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute(
                "UPDATE document_processing_jobs SET status='processing', started_at=NOW() WHERE id=%s",
                (job_id,),
            )

    try:
        # ── Download file from MinIO / URL ──────────────────────────────────
        file_bytes = _download_file(file_url)

        # ── Extract chunks based on content type ────────────────────────────
        from app.services.chunker import (
            PDFChunker, VideoTranscriptChunker, 
            DocxChunker, PptxChunker, ExcelChunker,
            DocumentChunk, detect_language
        )

        if "pdf" in content_type.lower() or file_url.endswith(".pdf"):
            chunker = PDFChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
            chunks = chunker.chunk_bytes(file_bytes)
        elif any(ext in file_url.lower() for ext in (".docx", ".doc")):
            chunker = DocxChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
            chunks = chunker.chunk_bytes(file_bytes)
        elif any(ext in file_url.lower() for ext in (".pptx", ".ppt")):
            chunker = PptxChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
            chunks = chunker.chunk_bytes(file_bytes)
        elif any(ext in file_url.lower() for ext in (".xlsx", ".xls")):
            chunker = ExcelChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
            chunks = chunker.chunk_bytes(file_bytes)
        elif any(ext in file_url.lower() for ext in (".mp4", ".webm", ".mov", ".avi", "video")):
            # For video, we need a transcript first
            # In production: run Whisper here or use pre-generated transcript
            transcript = _get_or_generate_transcript(content_id, file_bytes)
            if transcript:
                chunker = VideoTranscriptChunker()
                chunks = chunker.chunk_whisper_json(transcript)
            else:
                logger.warning(f"No transcript available for content {content_id}")
                chunks = []
        elif file_url.endswith(".txt") or "text" in content_type.lower():
            text = file_bytes.decode("utf-8", errors="replace")
            chunker = PDFChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
            # Treat as single-page document
            raw_chunks = chunker._split_text(text)
            chunks = [
                DocumentChunk(
                    text=c, index=i, source_type="document",
                    page_number=1, language=detect_language(c)
                )
                for i, c in enumerate(raw_chunks)
            ]
        else:
            logger.warning(f"Unsupported content type: {content_type}")
            chunks = []

        if not chunks:
            _mark_job(job_id, "completed", 0)
            return {"chunks_created": 0}

        # ── Store chunks (sync wrapper around async) ─────────────────────────
        async def _store_all():
            from app.services.rag_service import rag_service
            chunk_dicts = [
                {
                    "text": c.text,
                    "index": c.index,
                    "source_type": c.source_type,
                    "page_number": c.page_number,
                    "start_time_sec": c.start_time_sec,
                    "end_time_sec": c.end_time_sec,
                    "language": c.language,
                }
                for c in chunks
            ]
            # Must init pool for each task because asyncio.run creates a new loop
            from app.core.database import init_async_pool, close_async_pool
            await init_async_pool()
            try:
                ids = await rag_service.store_chunks_batch(
                    content_id=content_id,
                    course_id=course_id,
                    chunks=chunk_dicts,
                    node_id=node_id,
                )
                return len(ids)
            finally:
                await close_async_pool()

        n_chunks = run_async(_store_all())
        _mark_job(job_id, "completed", n_chunks)
        logger.info(f"Job {job_id}: created {n_chunks} chunks")
        return {"chunks_created": n_chunks}

    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
        _mark_job(job_id, "failed", error=str(exc))
        raise self.retry(exc=exc)


def _download_file(url: str) -> bytes:
    """Download file from MinIO and return bytes. 
    Uses streaming to reduce peak memory during download.
    """
    client = Minio(
        os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        secure=False
    )
    bucket = os.getenv("MINIO_BUCKET")
    
    response = client.get_object(bucket, url)
    try:
        # Read in chunks to avoid single large allocation spike
        buf = io.BytesIO()
        for chunk in response.stream(1 * 1024 * 1024): # 1MB chunks
            buf.write(chunk)
        return buf.getvalue()
    finally:
        response.close()
        response.release_conn()


def _get_or_generate_transcript(content_id: int, video_bytes: bytes) -> dict | None:
    """
    Try to load existing transcript from DB, or run Whisper if available.
    Returns Whisper-format dict or None.
    """
    # Check if transcript already exists
    from app.core.database import get_sync_conn, get_sync_cursor
    with get_sync_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute(
                "SELECT metadata FROM section_content WHERE id=%s", (content_id,)
            )
            row = cur.fetchone()
            if row and row.get("metadata"):
                meta = row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if "transcript" in meta:
                    return meta["transcript"]

    # Try Whisper (only if installed)
    try:
        import whisper
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        model = whisper.load_model("base")  # 'base' balances speed/accuracy
        result = model.transcribe(tmp_path, task="transcribe")
        os.unlink(tmp_path)

        # Whisper returns {"segments": [{"start", "end", "text"}]}
        return result
    except ImportError:
        logger.info("Whisper not installed — skipping video transcription")
        return None


def _mark_job(job_id: int, status: str, chunks: int = 0, error: str = ""):
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