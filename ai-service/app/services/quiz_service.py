"""
ai-service/app/services/quiz_service.py
Phase 2: AI Smart Quiz + Spaced Repetition
- Generate quizzes using Bloom's Taxonomy (6 levels)
- Source-cited answers (grounded in RAG chunks)
- SM-2 Spaced Repetition Engine
- Instructor review workflow
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.database import get_async_conn
from app.core.llm import chat_complete_json, build_quiz_generation_prompt
from app.services.rag_service import rag_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BLOOM_LEVELS = ["remember", "understand", "apply", "analyze", "evaluate", "create"]


@dataclass
class GeneratedQuestion:
    question_text: str
    bloom_level: str
    question_type: str
    answer_options: list[dict]   # [{text, is_correct, explanation}]
    explanation: str
    source_quote: str
    source_chunk_id: int | None
    language: str


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
        """
        Generate quiz questions for a knowledge node.
        Returns list of ai_quiz_generations IDs (status=DRAFT).
        """
        levels = bloom_levels or BLOOM_LEVELS
        gen_ids: list[int] = []

        # ── Load node info ────────────────────────────────────────────────────
        async with get_async_conn() as conn:
            node = await conn.fetchrow(
                "SELECT id, name, name_vi, name_en, course_id FROM knowledge_nodes WHERE id = $1",
                node_id,
            )
        if not node:
            raise ValueError(f"Knowledge node {node_id} not found")

        node_name = node["name_vi"] if language == "vi" and node["name_vi"] else node["name"]

        # ── Get existing questions for deduplication ───────────────────────────
        async with get_async_conn() as conn:
            existing = await conn.fetch(
                "SELECT question_text FROM ai_quiz_generations WHERE node_id = $1",
                node_id,
            )
        existing_texts = [r["question_text"] for r in existing]

        for bloom_level in levels:
            for _ in range(questions_per_level):
                try:
                    gen_id = await self._generate_single(
                        node_id=node_id,
                        course_id=course_id,
                        created_by=created_by,
                        bloom_level=bloom_level,
                        node_name=node_name,
                        language=language,
                        existing_questions=existing_texts,
                    )
                    gen_ids.append(gen_id)
                    logger.info(f"Generated question id={gen_id} bloom={bloom_level}")
                except Exception as e:
                    logger.error(f"Failed to generate {bloom_level} question: {e}")

        return gen_ids

    async def _generate_single(
        self,
        node_id: int,
        course_id: int,
        created_by: int,
        bloom_level: str,
        node_name: str,
        language: str,
        existing_questions: list[str],
    ) -> int:
        """Generate one question and store as DRAFT."""
        # RAG: get relevant chunks for this node
        chunks = await rag_service.search(
            query=node_name,
            course_id=course_id,
            node_id=node_id,
            top_k=4,
        )

        # Fallback: broader search without node filter
        if not chunks:
            chunks = await rag_service.search(
                query=node_name,
                course_id=course_id,
                top_k=3,
            )

        context_texts = [c.chunk_text for c in chunks]
        best_chunk_id = chunks[0].chunk_id if chunks else None

        if not context_texts:
            raise ValueError(f"No context chunks found for node {node_id}")

        messages = build_quiz_generation_prompt(
            bloom_level=bloom_level,
            context_chunks=context_texts,
            node_name=node_name,
            language=language,
            existing_questions=existing_questions[:5],
        )

        result = await chat_complete_json(
            messages=messages,
            model=settings.quiz_model,
            temperature=0.5,
        )

        # Validate result structure
        if "question_text" not in result or "answer_options" not in result:
            raise ValueError(f"Invalid LLM response structure: {list(result.keys())}")

        # Persist as DRAFT
        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ai_quiz_generations
                    (node_id, course_id, created_by, bloom_level,
                     question_text, question_type, answer_options,
                     explanation, source_quote, source_chunk_id, language, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,'DRAFT')
                RETURNING id
                """,
                node_id, course_id, created_by, bloom_level,
                result["question_text"],
                result.get("question_type", "SINGLE_CHOICE"),
                __import__("json").dumps(result.get("answer_options", []), ensure_ascii=False),
                result.get("explanation", ""),
                result.get("source_quote", ""),
                best_chunk_id,
                language,
            )
        return row["id"]

    async def list_drafts(self, course_id: int, node_id: int | None = None) -> list[dict]:
        """List all DRAFT AI-generated questions for instructor review."""
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

        async with get_async_conn() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def approve_question(
        self,
        gen_id: int,
        reviewer_id: int,
        quiz_id: int,
        review_note: str = "",
    ) -> int:
        """
        Approve a DRAFT → publish to actual quiz_questions table.
        Returns new quiz_question_id.
        """
        import json as json_lib

        async with get_async_conn() as conn:
            gen = await conn.fetchrow(
                "SELECT * FROM ai_quiz_generations WHERE id = $1", gen_id
            )
            if not gen:
                raise ValueError(f"Generation {gen_id} not found")

            # Parse options from JSONB
            options = gen["answer_options"] or []
            if isinstance(options, str):
                options = json_lib.loads(options)

            # Insert into quiz_questions
            q_row = await conn.fetchrow(
                """
                INSERT INTO quiz_questions
                    (quiz_id, question_type, question_text, explanation,
                     points, order_index, settings, is_required,
                     node_id, bloom_level, reference_chunk_id)
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

            # Insert answer options
            for i, opt in enumerate(options):
                await conn.execute(
                    """INSERT INTO quiz_answer_options
                       (question_id, option_text, is_correct, order_index)
                       VALUES ($1,$2,$3,$4)""",
                    q_id, opt.get("text", ""), bool(opt.get("is_correct")), i,
                )

            # Mark generation as PUBLISHED
            await conn.execute(
                """UPDATE ai_quiz_generations
                   SET status='PUBLISHED', reviewed_by=$1, reviewed_at=NOW(),
                       review_note=$2, quiz_question_id=$3, updated_at=NOW()
                   WHERE id=$4""",
                reviewer_id, review_note, q_id, gen_id,
            )

        return q_id

    async def reject_question(
        self, gen_id: int, reviewer_id: int, review_note: str
    ) -> None:
        async with get_async_conn() as conn:
            await conn.execute(
                """UPDATE ai_quiz_generations
                   SET status='REJECTED', reviewed_by=$1, reviewed_at=NOW(),
                       review_note=$2, updated_at=NOW()
                   WHERE id=$3""",
                reviewer_id, review_note, gen_id,
            )


# ── SM-2 Spaced Repetition Engine ────────────────────────────────────────────

class SpacedRepetitionService:
    """
    Implements the SM-2 algorithm for intelligent review scheduling.
    Quality ratings:
      5 — perfect response
      4 — correct with slight hesitation
      3 — correct with difficulty
      2 — incorrect but close (easy recall on re-show)
      1 — incorrect, hard to recall
      0 — total blackout
    """

    MIN_EASINESS = 1.3

    def update(self, ef: float, interval: int, reps: int, quality: int) -> tuple[float, int, int]:
        """
        Core SM-2 update. Returns (new_ef, new_interval, new_reps).
        """
        # Update easiness factor
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ef = max(self.MIN_EASINESS, new_ef)

        if quality < 3:
            # Incorrect: reset to beginning
            new_interval = 1
            new_reps = 0
        else:
            new_reps = reps + 1
            if new_reps == 1:
                new_interval = 1
            elif new_reps == 2:
                new_interval = 6
            else:
                new_interval = round(interval * new_ef)

        return new_ef, new_interval, new_reps

    async def record_response(
        self,
        student_id: int,
        question_id: int,
        course_id: int,
        node_id: int | None,
        quality: int,  # 0-5
    ) -> dict:
        """Record a student response and update their SR schedule."""
        async with get_async_conn() as conn:
            # Get current SR record or defaults
            row = await conn.fetchrow(
                """SELECT easiness_factor, interval_days, repetitions
                   FROM spaced_repetitions
                   WHERE student_id=$1 AND question_id=$2""",
                student_id, question_id,
            )

            ef = float(row["easiness_factor"]) if row else 2.5
            interval = int(row["interval_days"]) if row else 1
            reps = int(row["repetitions"]) if row else 0

            new_ef, new_interval, new_reps = self.update(ef, interval, reps, quality)
            next_date = date.today() + timedelta(days=new_interval)

            await conn.execute(
                """INSERT INTO spaced_repetitions
                       (student_id, question_id, node_id, course_id,
                        easiness_factor, interval_days, repetitions,
                        quality_last, next_review_date, last_reviewed_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW())
                   ON CONFLICT (student_id, question_id) DO UPDATE SET
                       easiness_factor  = $5,
                       interval_days    = $6,
                       repetitions      = $7,
                       quality_last     = $8,
                       next_review_date = $9,
                       last_reviewed_at = NOW(),
                       updated_at       = NOW()""",
                student_id, question_id, node_id, course_id,
                new_ef, new_interval, new_reps, quality, next_date,
            )

        return {
            "next_review_date": next_date.isoformat(),
            "interval_days": new_interval,
            "easiness_factor": round(new_ef, 2),
            "repetitions": new_reps,
        }

    async def get_due_reviews(
        self, student_id: int, course_id: int, limit: int = 20
    ) -> list[dict]:
        """Get questions due for review today (for 5-min warm-up session)."""
        async with get_async_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT sr.question_id, sr.node_id, sr.next_review_date,
                       sr.interval_days, sr.repetitions,
                       qq.question_text, qq.question_type,
                       kn.name AS node_name
                FROM spaced_repetitions sr
                JOIN quiz_questions qq ON qq.id = sr.question_id
                LEFT JOIN knowledge_nodes kn ON kn.id = sr.node_id
                WHERE sr.student_id = $1
                  AND sr.course_id  = $2
                  AND sr.next_review_date <= CURRENT_DATE
                ORDER BY sr.next_review_date ASC, sr.easiness_factor ASC
                LIMIT $3
                """,
                student_id, course_id, limit,
            )
        return [dict(r) for r in rows]

    async def get_review_stats(self, student_id: int, course_id: int) -> dict:
        """Summary stats for student review dashboard."""
        async with get_async_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE next_review_date <= CURRENT_DATE)  AS due_today,
                    COUNT(*) FILTER (WHERE next_review_date > CURRENT_DATE)   AS upcoming,
                    COUNT(*)                                                    AS total_tracked,
                    AVG(easiness_factor)                                        AS avg_easiness,
                    AVG(repetitions)                                            AS avg_repetitions
                FROM spaced_repetitions
                WHERE student_id = $1 AND course_id = $2
                """,
                student_id, course_id,
            )
        return dict(row) if row else {}


quiz_gen_service = QuizGenerationService()
sr_service = SpacedRepetitionService()
