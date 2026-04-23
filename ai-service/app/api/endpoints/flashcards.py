"""
ai-service/app/api/endpoints/flashcards.py
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.database import get_ai_conn
from app.core.llm import chat_complete_json, build_flashcard_generation_prompt
from app.core.llm_gateway import TASK_FLASHCARD_GEN
from app.services.rag_service import rag_service
from app.services.flashcard_service import flashcard_srv

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


def _verify_internal(request: Request):
    secret = request.headers.get("X-AI-Secret", "")
    if secret != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")


class GenerateFlashcardsRequest(BaseModel):
    student_id: int
    node_id: int
    course_id: int
    count: int = Field(default=3, ge=1, le=10)
    language: str = "vi"
    existing_fronts: Optional[list[str]] = None


class ReviewRequest(BaseModel):
    student_id: int
    flashcard_id: int
    quality: int = Field(..., ge=0, le=5)


@router.get("/due/student/{student_id}/course/{course_id}")
async def get_due_flashcards(student_id: int, course_id: int, request: Request):
    _verify_internal(request)
    try:
        return await flashcard_srv.list_due_flashcards(student_id, course_id)
    except Exception as e:
        logger.error(f"Failed to get due flashcards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node/{node_id}/course/{course_id}/student/{student_id}")
async def get_node_flashcards(node_id: int, course_id: int, student_id: int, request: Request):
    _verify_internal(request)
    try:
        return await flashcard_srv.list_flashcards_by_node(student_id, course_id, node_id)
    except Exception as e:
        logger.error(f"Failed to get node flashcards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review")
async def review_flashcard(body: ReviewRequest, request: Request):
    _verify_internal(request)
    try:
        return await flashcard_srv.review_flashcard(body.student_id, body.flashcard_id, body.quality)
    except Exception as e:
        logger.error(f"Failed to review flashcard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_flashcards(body: GenerateFlashcardsRequest, request: Request):
    _verify_internal(request)

    async with get_ai_conn() as conn:
        node = await conn.fetchrow(
            "SELECT id, name, name_vi, name_en FROM knowledge_nodes WHERE id = $1",
            body.node_id,
        )
    if not node:
        raise HTTPException(status_code=404, detail=f"Knowledge node {body.node_id} not found")

    node_name = node["name_vi"] if body.language == "vi" and node["name_vi"] else node["name"]

    # Get wrong answers context from AI DB only (ai_diagnoses table)
    wrong_answers_context = ""
    async with get_ai_conn() as conn:
        mistakes = await conn.fetch(
            """
            SELECT explanation AS gap
            FROM ai_diagnoses
            WHERE student_id = $1 AND node_id = $2
            AND explanation IS NOT NULL AND explanation != ''
            ORDER BY created_at DESC
            LIMIT 3
            """,
            body.student_id, body.node_id
        )
        if mistakes:
            wrong_answers_context = "\n".join(r["gap"] for r in mistakes if r["gap"])

    if not wrong_answers_context:
        wrong_answers_context = "Không có thông tin lỗi sai cụ thể. Hãy tập trung vào các khái niệm nền tảng."

    chunks = await rag_service.search_multilingual(
        query=node_name,
        course_id=body.course_id,
        node_id=body.node_id,
        top_k=3,
    )
    
    if not chunks:
        chunks = await rag_service.search_multilingual(
            query=node_name,
            course_id=body.course_id,
            top_k=2,
        )

    context_texts = [c.chunk_text for c in chunks]
    if not context_texts:
        context_texts = [f"Chủ đề chung: {node_name}"]

    try:
        messages = build_flashcard_generation_prompt(
            context_chunks=context_texts,
            node_name=node_name,
            wrong_answers_context=wrong_answers_context,
            count=body.count,
            language=body.language,
            existing_fronts=body.existing_fronts,
        )

        result = await chat_complete_json(
            messages=messages,
            model=settings.quiz_model,
            temperature=0.7,
            task=TASK_FLASHCARD_GEN,
        )

        if "flashcards" not in result:
            raise ValueError("Missing 'flashcards' key in LLM response")

        # Save to AI DB directly
        persisted_flashcards = await flashcard_srv.create_flashcards(
            result["flashcards"], 
            student_id=body.student_id, 
            course_id=body.course_id, 
            node_id=body.node_id
        )

        return {"flashcards": persisted_flashcards}

    except Exception as e:
        logger.error(f"Failed to generate flashcards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
