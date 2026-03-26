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


#  Async runner 

def run_async(coro):
    """Chạy coroutine trong sync Celery context."""
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


#  Task: Auto-Index document 

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
    force: bool = False,   # NEW: force re-index ngay cả khi đã indexed
):
    """
    Celery task: Auto-index tài liệu → tạo knowledge nodes → build graph.

    Cải tiến vs cũ:
    - Download file TRONG task này (1 lần duy nhất), pass bytes vào service
    - Idempotency: skip nếu đã 'indexed' và force=False
    - Progress state: PROGRESS với metadata để frontend poll được
    - Retry với exponential backoff
    """
    logger.info(
        f"auto_index_task start: content_id={content_id}, "
        f"course_id={course_id}, type={content_type}, force={force}"
    )

    def _update_progress(stage: str, pct: int):
        """Cập nhật Celery task state để frontend có thể poll progress."""
        self.update_state(
            state="PROGRESS",
            meta={"stage": stage, "progress": pct, "content_id": content_id},
        )

    try:
        result = run_async(
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
        return result

    except Exception as exc:
        logger.error(
            f"auto_index_task failed content_id={content_id}: {exc}", exc_info=True
        )
        # Exponential backoff: lần 1 sau 30s, lần 2 sau 90s
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
    """
    Async core của auto_index_task:
    1. Idempotency check
    2. Download file bytes (1 lần)
    3. Gọi auto_index_service với bytes đã có
    """
    from app.core.database import init_async_pool, close_async_pool, get_async_conn
    from app.services.auto_index_service import auto_index_service

    await init_async_pool()
    try:
        #  Idempotency check 
        if not force:
            async with get_async_conn() as conn:
                row = await conn.fetchrow(
                    "SELECT ai_index_status FROM section_content WHERE id=$1",
                    content_id,
                )
            if row and row["ai_index_status"] == "indexed":
                logger.info(
                    f"content_id={content_id} already indexed, skipping "
                    f"(use force=True to re-index)"
                )
                return {"ok": True, "skipped": True, "reason": "already_indexed"}

        #  Download file (1 lần duy nhất) 
        progress_callback("download", 5)
        file_bytes = await auto_index_service._download_bytes(file_url)
        logger.info(
            f"Downloaded {len(file_bytes) / 1024:.1f} KB for content_id={content_id}"
        )

        #  Chạy full pipeline 
        result = await auto_index_service.auto_index(
            content_id=content_id,
            course_id=course_id,
            file_url=file_url,
            content_type=content_type,
            file_bytes=file_bytes,          # pass bytes, không download lại
            progress_callback=progress_callback,
        )

        return result

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
    content_type: str,   # 'application/pdf' | 'video/mp4' | 'application/vnd.openxmlformats...'
):
    """
    Download file từ MinIO, chunk, embed, store vào pgvector.
    Cập nhật document_processing_jobs status xuyên suốt.

    Hỗ trợ: PDF, DOCX, PPTX, XLSX, TXT, video (với transcript).
    """
    from app.core.database import get_sync_conn, get_sync_cursor

    logger.info(f"process_document_task: job_id={job_id}, content_id={content_id}")

    # Đánh dấu đang xử lý
    with get_sync_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute(
                "UPDATE document_processing_jobs "
                "SET status='processing', started_at=NOW() WHERE id=%s",
                (job_id,),
            )

    try:
        #  Download 
        file_bytes = _download_file(file_url)

        #  Extract chunks theo file type 
        from app.services.chunker import (
            PDFChunker, DocxChunker, PptxChunker, ExcelChunker,
            VideoTranscriptChunker, DocumentChunk, detect_language,
        )

        file_url_lower = file_url.lower()
        ct_lower = content_type.lower()
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap

        if file_url_lower.endswith(".pdf") or "pdf" in ct_lower:
            chunks = PDFChunker(chunk_size, overlap).chunk_bytes(file_bytes)

        elif any(file_url_lower.endswith(e) for e in (".docx", ".doc")) or "word" in ct_lower:
            chunks = DocxChunker(chunk_size, overlap).chunk_bytes(file_bytes)

        elif any(file_url_lower.endswith(e) for e in (".pptx", ".ppt")) or "presentation" in ct_lower:
            chunks = PptxChunker(chunk_size, overlap).chunk_bytes(file_bytes)

        elif any(file_url_lower.endswith(e) for e in (".xlsx", ".xls")) or "spreadsheet" in ct_lower or "excel" in ct_lower:
            chunks = ExcelChunker(chunk_size, overlap).chunk_bytes(file_bytes)

        elif (
            any(file_url_lower.endswith(e) for e in (".mp4", ".webm", ".mov", ".avi"))
            or "video" in ct_lower
        ):
            transcript = _get_or_generate_transcript(content_id, file_bytes)
            if transcript:
                chunks = VideoTranscriptChunker().chunk_whisper_json(transcript)
            else:
                logger.warning(f"No transcript for content {content_id}, skipping")
                chunks = []

        elif file_url_lower.endswith(".txt") or "text/plain" in ct_lower:
            text = file_bytes.decode("utf-8", errors="replace")
            chunker = PDFChunker(chunk_size, overlap)
            raw = chunker._split_text(text)
            chunks = [
                DocumentChunk(
                    text=c, index=i, source_type="document",
                    page_number=1, language=detect_language(c),
                )
                for i, c in enumerate(raw)
            ]

        else:
            logger.warning(f"Unsupported content type: {content_type} for {file_url}")
            chunks = []

        if not chunks:
            _mark_job(job_id, "completed", 0)
            return {"chunks_created": 0}

        #  Store chunks (async in sync context) 
        async def _store_all():
            from app.services.rag_service import rag_service
            from app.core.database import init_async_pool, close_async_pool

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


#  Helpers 

def _download_file(url: str) -> bytes:
    """
    Download file từ MinIO, dùng streaming để giảm peak memory.
    """
    from minio import Minio

    client = Minio(
        os.getenv("MINIO_ENDPOINT", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=False,
    )
    bucket = os.getenv("MINIO_BUCKET", "lms-files")

    response = client.get_object(bucket, url)
    try:
        buf = io.BytesIO()
        for chunk in response.stream(1 * 1024 * 1024):
            buf.write(chunk)
        return buf.getvalue()
    finally:
        response.close()
        response.release_conn()


def _get_or_generate_transcript(content_id: int, video_bytes: bytes) -> dict | None:
    """
    Tải transcript từ DB hoặc chạy Whisper nếu có.
    Trả về Whisper-format dict hoặc None.
    """
    from app.core.database import get_sync_conn, get_sync_cursor

    # Kiểm tra transcript đã có trong DB chưa
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

    # Fallback: chạy Whisper nếu có
    try:
        import whisper
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        model = whisper.load_model("base")
        result = model.transcribe(tmp_path, task="transcribe")
        os.unlink(tmp_path)
        return result

    except ImportError:
        logger.info("Whisper not installed — skipping video transcription")
        return None


def _mark_job(job_id: int, status: str, chunks: int = 0, error: str = "") -> None:
    from app.core.database import get_sync_conn, get_sync_cursor
    with get_sync_conn() as conn:
        with get_sync_cursor(conn) as cur:
            cur.execute(
                """
                UPDATE document_processing_jobs
                SET status=%s, chunks_created=%s, completed_at=NOW(),
                    error_message=%s, updated_at=NOW()
                WHERE id=%s
                """,
                (status, chunks, error or None, job_id),
            )