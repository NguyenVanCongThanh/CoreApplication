from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.database import get_ai_conn, get_lms_conn
from app.core.llm import chat_complete_json, build_quiz_generation_prompt
from app.services.rag_service import rag_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BLOOM_LEVELS = ["remember", "understand", "apply", "analyze", "evaluate", "create"]


class QuizGenerationService:

    async def generate_for_node(
        self,
        node_id: int,
        course_id: int,
        created_by: int,
        bloom_levels: list[str] | None = None,
        language: str = "vi",
        questions_per_level: int = 1,
    ) -> list[int]:
        levels = bloom_levels or BLOOM_LEVELS
        gen_ids: list[int] = []

        async with get_ai_conn() as conn:
            node = await conn.fetchrow(
                "SELECT id, name, name_vi, name_en, course_id FROM knowledge_nodes WHERE id = $1",
                node_id,
            )
        if not node:
            raise ValueError(f"Knowledge node {node_id} not found")

        node_name = node["name_vi"] if language == "vi" and node["name_vi"] else node["name"]

        async with get_ai_conn() as conn:
            existing = await conn.fetch(
                "SELECT question_text FROM ai_quiz_generations WHERE node_id = $1", node_id
            )
        existing_texts = [r["question_text"] for r in existing]

        for bloom_level in levels:
            for _ in range(questions_per_level):
                try:
                    gen_id = await self._generate_single(
                        node_id=node_id, course_id=course_id, created_by=created_by,
                        bloom_level=bloom_level, node_name=node_name,
                        language=language, existing_questions=existing_texts,
                    )
                    gen_ids.append(gen_id)
                except Exception as e:
                    logger.error("Failed to generate %s question: %s", bloom_level, e)

        return gen_ids

    async def _generate_single(
        self, node_id, course_id, created_by, bloom_level, node_name, language, existing_questions,
    ) -> int:
        chunks = await rag_service.search_multilingual(
            query=node_name, course_id=course_id, node_id=node_id, top_k=4,
        )
        if not chunks:
            chunks = await rag_service.search_multilingual(
                query=node_name, course_id=course_id, top_k=3,
            )

        context_texts  = [c.chunk_text for c in chunks]
        best_chunk_id  = chunks[0].chunk_id if chunks else None

        if not context_texts:
            raise ValueError(f"No context chunks found for node {node_id}")

        messages = build_quiz_generation_prompt(
            bloom_level=bloom_level, context_chunks=context_texts,
            node_name=node_name, language=language,
            existing_questions=existing_questions[:5],
        )
        result = await chat_complete_json(
            messages=messages, model=settings.quiz_model, temperature=0.5,
        )

        if "question_text" not in result or "answer_options" not in result:
            raise ValueError(f"Invalid LLM response structure: {list(result.keys())}")

        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ai_quiz_generations
                    (node_id, course_id, created_by, bloom_level, question_text,
                     question_type, answer_options, explanation, source_quote,
                     source_chunk_id, language, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,'DRAFT')
                RETURNING id
                """,
                node_id, course_id, created_by, bloom_level,
                result["question_text"],
                result.get("question_type", "SINGLE_CHOICE"),
                __import__("json").dumps(result.get("answer_options", []), ensure_ascii=False),
                result.get("explanation", ""), result.get("source_quote", ""),
                best_chunk_id, language,
            )
        return row["id"]

    async def list_drafts(self, course_id: int, node_id: int | None = None) -> list[dict]:
        sql = """
            SELECT aiqg.*, kn.name AS node_name
            FROM ai_quiz_generations aiqg
            LEFT JOIN knowledge_nodes kn ON kn.id = aiqg.node_id
            WHERE aiqg.course_id = $1 AND aiqg.status = 'DRAFT'
        """
        params: list = [course_id]
        if node_id:
            sql += " AND aiqg.node_id = $2"
            params.append(node_id)
        sql += " ORDER BY aiqg.bloom_level, aiqg.created_at"

        async with get_ai_conn() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def approve_question(
        self, gen_id: int, reviewer_id: int, quiz_id: int, review_note: str = ""
    ) -> int:
        import json as json_lib

        async with get_ai_conn() as conn:
            gen = await conn.fetchrow(
                "SELECT * FROM ai_quiz_generations WHERE id = $1", gen_id
            )
        if not gen:
            raise ValueError(f"Generation {gen_id} not found")

        options = gen["answer_options"] or []
        if isinstance(options, str):
            options = json_lib.loads(options)

        # Write approved question into LMS DB
        async with get_lms_conn() as conn:
            q_row = await conn.fetchrow(
                """
                INSERT INTO quiz_questions
                    (quiz_id, question_type, question_text, explanation, points,
                     order_index, settings, is_required, node_id, bloom_level, reference_chunk_id)
                SELECT $1, $2, $3, $4, 10.0,
                       COALESCE((SELECT MAX(order_index)+1 FROM quiz_questions WHERE quiz_id=$1), 1),
                       '{}', true, $5, $6, $7
                RETURNING id
                """,
                quiz_id, gen["question_type"], gen["question_text"],
                gen["explanation"], gen["node_id"], gen["bloom_level"],
                gen["source_chunk_id"],
            )
            q_id = q_row["id"]

            for i, opt in enumerate(options):
                await conn.execute(
                    """INSERT INTO quiz_answer_options
                       (question_id, option_text, is_correct, order_index)
                       VALUES ($1,$2,$3,$4)""",
                    q_id, opt.get("text", ""), bool(opt.get("is_correct")), i,
                )

        # Update generation record in AI DB
        async with get_ai_conn() as conn:
            await conn.execute(
                """UPDATE ai_quiz_generations
                   SET status='PUBLISHED', reviewed_by=$1, reviewed_at=NOW(),
                       review_note=$2, quiz_question_id=$3, updated_at=NOW()
                   WHERE id=$4""",
                reviewer_id, review_note, q_id, gen_id,
            )

        return q_id

    async def reject_question(self, gen_id: int, reviewer_id: int, review_note: str) -> None:
        async with get_ai_conn() as conn:
            await conn.execute(
                """UPDATE ai_quiz_generations
                   SET status='REJECTED', reviewed_by=$1, reviewed_at=NOW(),
                       review_note=$2, updated_at=NOW()
                   WHERE id=$3""",
                reviewer_id, review_note, gen_id,
            )


# ── SM-2 Spaced Repetition ─────────────────────────────────────────────────────

class SpacedRepetitionService:
    MIN_EASINESS = 1.3

    def update(self, ef, interval, reps, quality):
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ef = max(self.MIN_EASINESS, new_ef)
        if quality < 3:
            new_interval, new_reps = 1, 0
        else:
            new_reps = reps + 1
            if   new_reps == 1: new_interval = 1
            elif new_reps == 2: new_interval = 6
            else:               new_interval = round(interval * new_ef)
        return new_ef, new_interval, new_reps

    async def record_response(
        self, student_id, question_id, course_id, node_id, quality
    ) -> dict:
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                """SELECT easiness_factor, interval_days, repetitions
                   FROM spaced_repetitions WHERE student_id=$1 AND question_id=$2""",
                student_id, question_id,
            )
            ef       = float(row["easiness_factor"]) if row else 2.5
            interval = int(row["interval_days"])      if row else 1
            reps     = int(row["repetitions"])         if row else 0

            new_ef, new_interval, new_reps = self.update(ef, interval, reps, quality)
            next_date = date.today() + timedelta(days=new_interval)

            await conn.execute(
                """INSERT INTO spaced_repetitions
                       (student_id, question_id, node_id, course_id,
                        easiness_factor, interval_days, repetitions,
                        quality_last, next_review_date, last_reviewed_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW())
                   ON CONFLICT (student_id, question_id) DO UPDATE SET
                       easiness_factor  = $5, interval_days    = $6,
                       repetitions      = $7, quality_last     = $8,
                       next_review_date = $9, last_reviewed_at = NOW(),
                       updated_at       = NOW()""",
                student_id, question_id, node_id, course_id,
                new_ef, new_interval, new_reps, quality, next_date,
            )

            # Update student_knowledge_progress
            is_correct = 1 if quality >= 3 else 0
            is_wrong = 1 if quality < 3 else 0
            await conn.execute(
                """INSERT INTO student_knowledge_progress
                       (student_id, node_id, course_id, total_attempts, correct_count, wrong_count, mastery_level, last_tested_at)
                   VALUES ($1, $2, $3, 1, $4, $5, $6, NOW())
                   ON CONFLICT (student_id, node_id) DO UPDATE SET
                       total_attempts = student_knowledge_progress.total_attempts + 1,
                       correct_count = student_knowledge_progress.correct_count + $4,
                       wrong_count = student_knowledge_progress.wrong_count + $5,
                       mastery_level = (student_knowledge_progress.correct_count + $4)::FLOAT / (student_knowledge_progress.total_attempts + 1),
                       last_tested_at = NOW(),
                       updated_at = NOW()""",
                student_id, node_id, course_id, is_correct, is_wrong, float(is_correct),
            )

        return {
            "next_review_date": next_date.isoformat(),
            "interval_days":    new_interval,
            "easiness_factor":  round(new_ef, 2),
            "repetitions":      new_reps,
        }

    async def get_due_reviews(self, student_id, course_id, limit=20) -> list[dict]:
        # question_text lives in LMS DB — we join across services at app layer
        async with get_ai_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT sr.question_id, sr.node_id, sr.next_review_date,
                       sr.interval_days, sr.repetitions, kn.name AS node_name
                FROM spaced_repetitions sr
                LEFT JOIN knowledge_nodes kn ON kn.id = sr.node_id
                WHERE sr.student_id = $1 AND sr.course_id = $2
                  AND sr.next_review_date <= CURRENT_DATE
                ORDER BY sr.next_review_date ASC, sr.easiness_factor ASC
                LIMIT $3
                """,
                student_id, course_id, limit,
            )

        if not rows:
            return []

        # Enrich with question text from LMS DB
        question_ids = [r["question_id"] for r in rows if r["question_id"]]
        question_map: dict[int, dict] = {}
        if question_ids:
            async with get_lms_conn() as conn:
                qq = await conn.fetch(
                    "SELECT id, question_text, question_type FROM quiz_questions WHERE id = ANY($1)",
                    question_ids,
                )
            question_map = {r["id"]: dict(r) for r in qq}

        result = []
        for r in rows:
            entry = dict(r)
            q = question_map.get(r["question_id"], {})
            entry["question_text"] = q.get("question_text", "")
            entry["question_type"] = q.get("question_type", "")
            result.append(entry)

        return result

    async def get_review_stats(self, student_id, course_id) -> dict:
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE next_review_date <= CURRENT_DATE) AS due_today,
                    COUNT(*) FILTER (WHERE next_review_date > CURRENT_DATE)  AS upcoming,
                    COUNT(*)                                                   AS total_tracked,
                    AVG(easiness_factor)                                       AS avg_easiness,
                    AVG(repetitions)                                           AS avg_repetitions
                FROM spaced_repetitions
                WHERE student_id = $1 AND course_id = $2
                """,
                student_id, course_id,
            )
        return dict(row) if row else {}


quiz_gen_service = QuizGenerationService()
sr_service       = SpacedRepetitionService()