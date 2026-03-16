"""
ai-service/app/api/endpoints/diagnose.py
Phase 1 endpoints:
POST /ai/diagnose   — analyze a wrong answer
GET  /ai/heatmap/class/{course_id}   — class-wide knowledge heatmap
GET  /ai/heatmap/student/{student_id}/course/{course_id}
POST /ai/knowledge-nodes   — create knowledge node
GET  /ai/knowledge-nodes/course/{course_id}  — get node tree
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_async_conn
from app.services.diagnosis_service import diagnosis_service

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/diagnose", tags=["Phase 1 — Diagnosis"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class DiagnoseRequest(BaseModel):
    student_id: int
    attempt_id: int
    question_id: int
    wrong_answer: str
    course_id: int


class DiagnoseResponse(BaseModel):
    explanation: str
    gap_type: str
    knowledge_gap: str
    study_suggestion: str
    confidence: float
    source_chunk_id: Optional[int]
    deep_link: Optional[dict]
    language: str


class KnowledgeNodeCreate(BaseModel):
    course_id: int
    name: str
    name_vi: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    order_index: int = 0


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=DiagnoseResponse)
async def diagnose_error(body: DiagnoseRequest, request: Request):
    """
    Phase 1: AI Error Diagnosis.
    Go LMS calls this after student submits a wrong answer.
    Returns LLM explanation grounded in course materials + deep link.
    """
    _verify_internal(request)

    try:
        result = await diagnosis_service.diagnose(
            student_id=body.student_id,
            attempt_id=body.attempt_id,
            question_id=body.question_id,
            wrong_answer=body.wrong_answer,
            course_id=body.course_id,
        )
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return DiagnoseResponse(
        explanation=result.explanation,
        gap_type=result.gap_type,
        knowledge_gap=result.knowledge_gap,
        study_suggestion=result.study_suggestion,
        confidence=result.confidence,
        source_chunk_id=result.source_chunk_id,
        deep_link=result.deep_link,
        language=result.language,
    )


@router.get("/heatmap/class/{course_id}")
async def class_heatmap(course_id: int, request: Request):
    """
    Class-wide weakness heatmap.
    Returns knowledge nodes sorted by wrong-rate (highest first).
    """
    _verify_internal(request)
    return await diagnosis_service.get_class_heatmap(course_id)


@router.get("/heatmap/student/{student_id}/course/{course_id}")
async def student_heatmap(student_id: int, course_id: int, request: Request):
    """Per-student knowledge mastery map."""
    _verify_internal(request)
    return await diagnosis_service.get_student_heatmap(student_id, course_id)


# ── Knowledge Nodes Management ────────────────────────────────────────────────

nodes_router = APIRouter(prefix="/knowledge-nodes", tags=["Knowledge Nodes"])


@nodes_router.post("")
async def create_node(body: KnowledgeNodeCreate, request: Request):
    _verify_internal(request)
    async with get_async_conn() as conn:
        # Calculate level from parent
        level = 0
        if body.parent_id:
            row = await conn.fetchrow(
                "SELECT level FROM knowledge_nodes WHERE id=$1", body.parent_id
            )
            level = (row["level"] + 1) if row else 0

        row = await conn.fetchrow(
            """INSERT INTO knowledge_nodes
                   (course_id, parent_id, name, name_vi, name_en,
                    description, level, order_index)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
               RETURNING *""",
            body.course_id, body.parent_id, body.name,
            body.name_vi, body.name_en, body.description,
            level, body.order_index,
        )
    return dict(row)


@nodes_router.get("/course/{course_id}")
async def list_nodes(course_id: int, request: Request):
    """
    Returns knowledge node tree for a course.
    Frontend can build a visual tree from parent_id.
    """
    _verify_internal(request)
    async with get_async_conn() as conn:
        rows = await conn.fetch(
            """SELECT kn.*,
                      COUNT(DISTINCT dc.id) AS chunk_count
               FROM knowledge_nodes kn
               LEFT JOIN document_chunks dc ON dc.node_id = kn.id
               WHERE kn.course_id = $1
               GROUP BY kn.id
               ORDER BY kn.level, kn.order_index""",
            course_id,
        )
    return [dict(r) for r in rows]


@nodes_router.patch("/{node_id}")
async def update_node(node_id: int, body: dict, request: Request):
    _verify_internal(request)
    allowed = {"name", "name_vi", "name_en", "description", "order_index", "parent_id"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    fields = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())

    async with get_async_conn() as conn:
        await conn.execute(
            f"UPDATE knowledge_nodes SET {fields}, updated_at=NOW() WHERE id=$1",
            node_id, *values,
        )
    return {"ok": True}


def _verify_internal(request: Request):
    secret = request.headers.get("X-AI-Secret", "")
    if secret != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")
