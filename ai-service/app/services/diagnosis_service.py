from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.database import get_ai_conn
from app.core.llm import chat_complete_json, build_diagnosis_prompt
from app.services.rag_service import rag_service, RetrievedChunk
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class DiagnosisResult:
    explanation: str
    gap_type: str
    knowledge_gap: str
    study_suggestion: str
    confidence: float
    source_chunk_id: int | None
    suggested_documents: list[dict]
    language: str


class DiagnosisService:

    async def diagnose(
        self,
        student_id: int,
        attempt_id: int,
        question_id: int,
        wrong_answer: str,
        course_id: int,
    ) -> DiagnosisResult:
        # ── 1. Load question from LMS DB ──────────────────────────────────────
        async with get_lms_conn() as conn:
            q_row = await conn.fetchrow(
                """SELECT qq.question_text, qq.node_id, qq.explanation, qq.question_type
                   FROM quiz_questions qq WHERE qq.id = $1""",
                question_id,
            )
            options_rows = await conn.fetch(
                """SELECT option_text, is_correct
                   FROM quiz_answer_options WHERE question_id = $1 ORDER BY order_index""",
                question_id,
            )

        if not q_row:
            raise ValueError(f"Question {question_id} not found")

        question_text   = q_row["question_text"]
        correct_answer  = " | ".join(r["option_text"] for r in options_rows if r["is_correct"])
        distractor_opts = [r["option_text"] for r in options_rows if not r["is_correct"]]
        node_id         = q_row["node_id"]

        # ── 2. Detect language ────────────────────────────────────────────────
        from app.services.chunker import detect_language
        language = detect_language(question_text)

        # ── 3. Cross-lingual RAG (reads AI DB via rag_service) ────────────────
        chunks: list[RetrievedChunk] = await rag_service.search_for_question(
            question_id=question_id,
            course_id=course_id,
            top_k=settings.top_k_chunks,
        )
        if not chunks:
            query = f"{question_text} {wrong_answer}"
            chunks = await rag_service.search_multilingual(
                query=query, course_id=course_id, top_k=settings.top_k_chunks,
            )

        # ── 4. Build prompt + call LLM ────────────────────────────────────────
        context_texts = [c.chunk_text for c in chunks] if chunks else []
        if not context_texts and correct_answer:
            context_texts = [f"Đáp án đúng: {correct_answer}"]

        messages = build_diagnosis_prompt(
            question_text=question_text,
            wrong_answer=wrong_answer,
            correct_answer=correct_answer,
            distractor_options=distractor_opts,
            context_chunks=context_texts,
            language=language,
        )

        try:
            llm_result = await chat_complete_json(messages=messages)
        except Exception as e:
            logger.error("LLM diagnosis failed: %s", e)
            llm_result = {
                "explanation":     "Không thể phân tích lỗi lúc này." if language == "vi" else "Unable to analyze error at this time.",
                "gap_type":        "other",
                "knowledge_gap":   "",
                "study_suggestion":"Xem lại tài liệu liên quan." if language == "vi" else "Review related materials.",
                "confidence":      0.5,
            }

        # ── 5. Build suggested documents ──────────────────────────────────────
        indices = llm_result.get("relevant_source_indices", [])
        if not isinstance(indices, list):
            indices = []

        suggested_documents = []
        seen_content_ids: set[int] = set()

        for idx in indices:
            if isinstance(idx, int) and 1 <= idx <= len(chunks):
                chunk = chunks[idx - 1]
                if chunk.content_id and chunk.content_id not in seen_content_ids:
                    link = self._build_deep_link(chunk)
                    snip = chunk.chunk_text[:150]
                    if len(chunk.chunk_text) > 150:
                        snip += "..."
                    link["snippet"]        = snip
                    link["chunk_language"] = chunk.language
                    suggested_documents.append(link)
                    seen_content_ids.add(chunk.content_id)

        if not suggested_documents and chunks:
            chunk = chunks[0]
            if chunk.content_id:
                link = self._build_deep_link(chunk)
                link["snippet"]        = chunk.chunk_text[:150] + ("..." if len(chunk.chunk_text) > 150 else "")
                link["chunk_language"] = chunk.language
                suggested_documents.append(link)

        best_chunk = (
            chunks[indices[0] - 1]
            if indices and isinstance(indices[0], int) and 1 <= indices[0] <= len(chunks)
            else (chunks[0] if chunks else None)
        )

        # ── 6. Persist diagnosis to AI DB ─────────────────────────────────────
        await self._save_diagnosis(
            student_id=student_id, attempt_id=attempt_id,
            question_id=question_id, node_id=node_id,
            wrong_answer=wrong_answer, correct_answer=correct_answer,
            llm_result=llm_result,
            source_chunk_id=best_chunk.chunk_id if best_chunk else None,
            language=language,
        )

        return DiagnosisResult(
            explanation=llm_result.get("explanation", ""),
            gap_type=llm_result.get("gap_type", "other"),
            knowledge_gap=llm_result.get("knowledge_gap", ""),
            study_suggestion=llm_result.get("study_suggestion", ""),
            confidence=float(llm_result.get("confidence", 0.7)),
            source_chunk_id=best_chunk.chunk_id if best_chunk else None,
            suggested_documents=suggested_documents,
            language=language,
        )

    def _build_deep_link(self, chunk: RetrievedChunk) -> dict:
        link: dict = {"content_id": chunk.content_id, "source_type": chunk.source_type}
        if chunk.source_type == "document" and chunk.page_number:
            link["page_number"]  = chunk.page_number
            link["url_fragment"] = f"#page={chunk.page_number}"
        elif chunk.source_type == "video" and chunk.start_time_sec is not None:
            link["start_time_sec"] = chunk.start_time_sec
            link["end_time_sec"]   = chunk.end_time_sec
            link["url_fragment"]   = f"#t={chunk.start_time_sec}"
        return link

    async def _save_diagnosis(
        self, student_id, attempt_id, question_id, node_id,
        wrong_answer, correct_answer, llm_result, source_chunk_id, language,
    ) -> int:
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ai_diagnoses
                    (student_id, attempt_id, question_id, node_id,
                     wrong_answer, correct_answer, explanation,
                     gap_type, confidence, source_chunk_id, language)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                RETURNING id
                """,
                student_id, attempt_id, question_id, node_id,
                wrong_answer, correct_answer,
                llm_result.get("explanation", ""),
                llm_result.get("gap_type", "other"),
                float(llm_result.get("confidence", 0.7)),
                source_chunk_id, language,
            )
        return row["id"]

    # ── Heatmaps ──────────────────────────────────────────────────────────────

    async def get_class_heatmap(self, course_id: int) -> list[dict]:
        async with get_ai_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    kn.id          AS node_id,
                    kn.name        AS node_name,
                    kn.name_vi,
                    kn.name_en,
                    COUNT(DISTINCT skp.student_id)                               AS student_count,
                    AVG(skp.mastery_level)                                       AS avg_mastery,
                    SUM(skp.wrong_count)                                         AS total_wrong,
                    SUM(skp.total_attempts)                                      AS total_attempts,
                    CASE WHEN SUM(skp.total_attempts) > 0
                         THEN SUM(skp.wrong_count)::FLOAT / SUM(skp.total_attempts) * 100
                         ELSE 0 END                                              AS wrong_rate
                FROM knowledge_nodes kn
                LEFT JOIN student_knowledge_progress skp ON skp.node_id = kn.id
                WHERE kn.course_id = $1
                GROUP BY kn.id, kn.name, kn.name_vi, kn.name_en
                ORDER BY wrong_rate DESC
                """,
                course_id,
            )
        return [dict(r) for r in rows]

    async def get_student_heatmap(self, student_id: int, course_id: int) -> list[dict]:
        async with get_ai_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    kn.id         AS node_id,
                    kn.name       AS node_name,
                    kn.name_vi,
                    kn.parent_id,
                    COALESCE(skp.mastery_level, 0)   AS mastery_level,
                    COALESCE(skp.total_attempts, 0)  AS total_attempts,
                    COALESCE(skp.wrong_count, 0)     AS wrong_count,
                    skp.last_tested_at,
                    (SELECT COUNT(*) FROM flashcards f WHERE f.node_id = kn.id AND f.student_id = $1) AS flashcard_count
                FROM knowledge_nodes kn
                LEFT JOIN student_knowledge_progress skp
                    ON skp.node_id = kn.id AND skp.student_id = $1
                WHERE kn.course_id = $2
                ORDER BY kn.level, kn.order_index
                """,
                student_id, course_id,
            )
        return [dict(r) for r in rows]


diagnosis_service = DiagnosisService()