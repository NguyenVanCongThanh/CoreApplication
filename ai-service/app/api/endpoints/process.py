"""
ai-service/app/api/endpoints/process.py
Document processing trigger:
POST /ai/process-document — called by Go LMS after file upload
GET  /ai/process-document/{job_id} — check job status
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_async_conn

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/process-document", tags=["Document Processing"])


class ProcessDocumentRequest(BaseModel):
    content_id: int
    course_id: int
    node_id: int | None = None
    file_url: str              # MinIO presigned URL or path
    content_type: str = "application/pdf"


class ProcessDocumentResponse(BaseModel):
    job_id: int
    status: str
    message: str


@router.post("", response_model=ProcessDocumentResponse)
async def trigger_processing(body: ProcessDocumentRequest, request: Request):
    """
    Trigger async document ingestion pipeline.
    Go LMS calls this after uploading a file to MinIO.
    Returns 202 immediately; Celery handles the heavy lifting.
    """
    _verify_internal(request)

    # Delete existing chunks for this content (re-upload scenario)
    from app.services.rag_service import rag_service
    await rag_service.delete_chunks_for_content(body.content_id)

    # Create job record
    async with get_async_conn() as conn:
        row = await conn.fetchrow(
            """INSERT INTO document_processing_jobs
                   (content_id, course_id, node_id, status)
               VALUES ($1,$2,$3,'queued')
               RETURNING id""",
            body.content_id, body.course_id, body.node_id,
        )
    job_id = row["id"]

    # Enqueue Celery task
    from app.worker.celery_app import process_document_task
    process_document_task.delay(
        job_id=job_id,
        content_id=body.content_id,
        course_id=body.course_id,
        node_id=body.node_id,
        file_url=body.file_url,
        content_type=body.content_type,
    )

    return ProcessDocumentResponse(
        job_id=job_id,
        status="queued",
        message=f"Document processing queued (job_id={job_id})",
    )


@router.get("/{job_id}")
async def get_job_status(job_id: int):
    async with get_async_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM document_processing_jobs WHERE id=$1", job_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


def _verify_internal(request: Request):
    """Lightweight secret-based auth for internal service calls."""
    secret = request.headers.get("X-AI-Secret", "")
    if secret != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized internal call")
