from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_ai_conn

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter(prefix="/process-document", tags=["Document Processing"])


class ProcessDocumentRequest(BaseModel):
    content_id: int
    course_id: int
    node_id: int | None = None
    file_url: str
    content_type: str = "application/pdf"


class ProcessDocumentResponse(BaseModel):
    job_id: int
    status: str
    message: str


@router.post("", response_model=ProcessDocumentResponse)
async def trigger_processing(body: ProcessDocumentRequest, request: Request):
    _verify(request)

    from app.services.rag_service import rag_service
    await rag_service.delete_chunks_for_content(body.content_id)

    async with get_ai_conn() as conn:
        row = await conn.fetchrow(
            """INSERT INTO document_processing_jobs
                   (content_id, course_id, node_id, status)
               VALUES ($1,$2,$3,'queued')
               RETURNING id""",
            body.content_id, body.course_id, body.node_id,
        )
    job_id = row["id"]

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
    async with get_ai_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM document_processing_jobs WHERE id=$1", job_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


def _verify(request: Request):
    if request.headers.get("X-AI-Secret", "") != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized internal call")