"""
ai-service/app/api/endpoints/flashcards.py
POST /ai/flashcards/generate - generates targeted flashcards for a specific knowledge node using LLM
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.database import get_async_conn
from app.core.llm import chat_complete_json, build_flashcard_generation_prompt
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])

class GenerateFlashcardsRequest(BaseModel):
    student_id: int
    node_id: int
    course_id: int
    count: int = Field(default=3, ge=1, le=10)
    language: str = "vi"
    existing_fronts: Optional[list[str]] = None


@router.post("/generate")
async def generate_flashcards(body: GenerateFlashcardsRequest, request: Request):
    """
    Generate targeted flashcards for a student on a specific node,
    incorporating their recent mistakes.
    """
    # Simple internal auth
    secret = request.headers.get("X-AI-Secret", "")
    if secret != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # 1. Load node info
    async with get_async_conn() as conn:
        node = await conn.fetchrow(
            "SELECT id, name, name_vi, name_en FROM knowledge_nodes WHERE id = $1",
            body.node_id,
        )
    if not node:
        raise HTTPException(status_code=404, detail=f"Knowledge node {body.node_id} not found")

    node_name = node["name_vi"] if body.language == "vi" and node["name_vi"] else node["name"]

    # 2. Get student's recent mistakes for this node to focus the flashcards
    wrong_answers_context = ""
    async with get_async_conn() as conn:
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
            wrong_answers_context = "\n".join(
                r["gap"] for r in mistakes if r["gap"]
            )
        
        # If no explicit AI gap generated, fetch raw wrong answers
        if not wrong_answers_context:
            wrong_answers = await conn.fetch(
                """
                SELECT qq.question_text, qsa.answer_data->>'selected_option_text' as student_answer
                FROM quiz_student_answers qsa
                JOIN quiz_questions qq ON qq.id = qsa.question_id
                JOIN quiz_attempts qa ON qa.id = qsa.attempt_id
                WHERE qa.student_id = $1 AND qq.node_id = $2 AND qsa.is_correct = false
                LIMIT 5
                """,
                body.student_id, body.node_id
            )
            if wrong_answers:
                wrong_answers_context = "\n".join(
                    f"- Câu hỏi: {r['question_text']}\n  Sai lầm: {r['student_answer']}"
                    for r in wrong_answers
                )
            else:
                wrong_answers_context = "Không có thông tin lỗi sai cụ thể. Hãy tập trung vào các khái niệm nền tảng."

    # 3. Fetch RAG context
    chunks = await rag_service.search(
        query=node_name,
        course_id=body.course_id,
        node_id=body.node_id,
        top_k=3,
    )
    
    if not chunks:
        chunks = await rag_service.search(
            query=node_name,
            course_id=body.course_id,
            top_k=2,
        )

    context_texts = [c.chunk_text for c in chunks]
    if not context_texts:
        # Fallback if really no content
        context_texts = [f"Chủ đề chung: {node_name}"]

    # 4. Generate via LLM
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
        )

        if "flashcards" not in result:
            raise ValueError("Missing 'flashcards' key in LLM response")

        return {"flashcards": result["flashcards"]}

    except Exception as e:
        logger.error(f"Failed to generate flashcards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
