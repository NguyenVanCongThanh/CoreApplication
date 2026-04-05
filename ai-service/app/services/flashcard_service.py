import logging
from datetime import date, timedelta
from app.core.database import get_ai_conn

logger = logging.getLogger(__name__)

class FlashcardService:
    MIN_EASINESS = 1.3

    async def list_due_flashcards(self, student_id: int, course_id: int) -> list[dict]:
        async with get_ai_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT f.id, f.course_id, f.node_id, f.front_text, f.back_text, f.status,
                       f.source_diagnosis_id, f.created_at,
                       fr.easiness_factor, fr.interval_days, fr.repetitions,
                       fr.next_review_date, fr.last_reviewed_at
                FROM flashcards f
                JOIN flashcard_repetitions fr ON fr.flashcard_id = f.id
                WHERE f.student_id = $1 AND f.course_id = $2
                  AND fr.next_review_date <= CURRENT_DATE
                  AND f.status = 'ACTIVE'
                ORDER BY fr.next_review_date ASC, fr.easiness_factor ASC
                """,
                student_id, course_id,
            )
        return [dict(r) for r in rows]

    async def list_flashcards_by_node(self, student_id: int, course_id: int, node_id: int) -> list[dict]:
        async with get_ai_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT f.id, f.course_id, f.node_id, f.front_text, f.back_text, f.status,
                       f.source_diagnosis_id, f.created_at,
                       fr.easiness_factor, fr.interval_days, fr.repetitions,
                       fr.next_review_date, fr.last_reviewed_at
                FROM flashcards f
                LEFT JOIN flashcard_repetitions fr ON fr.flashcard_id = f.id
                WHERE f.student_id = $1 AND f.course_id = $2 AND f.node_id = $3
                ORDER BY f.created_at DESC
                """,
                student_id, course_id, node_id,
            )
            # Ensure fr rows are not null by replacing them with defaults in the app logic or DB
        return [dict(r) for r in rows]

    async def create_flashcards(self, flashcards_data: list[dict], student_id: int, course_id: int, node_id: int):
        results = []
        async with get_ai_conn() as conn:
            for item in flashcards_data:
                row = await conn.fetchrow(
                    """
                    INSERT INTO flashcards (course_id, node_id, student_id, front_text, back_text, status)
                    VALUES ($1, $2, $3, $4, $5, 'ACTIVE')
                    RETURNING id, created_at
                    """,
                    course_id, node_id, student_id, item.get("front_text", ""), item.get("back_text", "")
                )
                fc_id = row['id']
                created_at = row['created_at']
                
                await conn.execute(
                    """
                    INSERT INTO flashcard_repetitions (student_id, flashcard_id, course_id, next_review_date)
                    VALUES ($1, $2, $3, CURRENT_DATE)
                    """,
                    student_id, fc_id, course_id
                )
                results.append({
                    "id": fc_id,
                    "course_id": course_id,
                    "node_id": node_id,
                    "front_text": item.get("front_text", ""),
                    "back_text": item.get("back_text", ""),
                    "status": "ACTIVE",
                    "created_at": created_at,
                })
        return results

    def _update_sm2(self, ef, interval, reps, quality):
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ef = max(self.MIN_EASINESS, new_ef)
        if quality < 3:
            new_interval, new_reps = 1, 0
        else:
            new_reps = reps + 1
            if new_reps == 1: new_interval = 1
            elif new_reps == 2: new_interval = 6
            else: new_interval = round(interval * new_ef)
        return new_ef, new_interval, new_reps

    async def review_flashcard(self, student_id: int, flashcard_id: int, quality: int) -> dict:
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT easiness_factor, interval_days, repetitions, course_id
                FROM flashcard_repetitions
                WHERE student_id = $1 AND flashcard_id = $2
                """,
                student_id, flashcard_id,
            )
            if not row:
                raise ValueError("Flashcard repetition not found")

            ef = float(row["easiness_factor"])
            interval = int(row["interval_days"])
            reps = int(row["repetitions"])
            course_id = row["course_id"]

            new_ef, new_interval, new_reps = self._update_sm2(ef, interval, reps, quality)
            next_date = date.today() + timedelta(days=new_interval)

            await conn.execute(
                """
                UPDATE flashcard_repetitions
                SET easiness_factor = $1,
                    interval_days = $2,
                    repetitions = $3,
                    quality_last = $4,
                    next_review_date = $5,
                    last_reviewed_at = NOW(),
                    updated_at = NOW()
                WHERE student_id = $6 AND flashcard_id = $7
                """,
                new_ef, new_interval, new_reps, quality, next_date, student_id, flashcard_id
            )

        return {
            "flashcard_id": flashcard_id,
            "easiness_factor": round(new_ef, 2),
            "interval_days": new_interval,
            "repetitions": new_reps,
            "next_review_date": next_date.isoformat(),
        }

flashcard_srv = FlashcardService()
