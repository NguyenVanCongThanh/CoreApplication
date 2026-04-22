"""
Teacher Tool: recommend_review

Identifies students with spaced repetition items due for review
and topics with declining mastery across the class. Helps teachers
know who needs attention and what to revisit.
"""
from __future__ import annotations

import logging

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class RecommendReviewTool(BaseTool):
    name = "recommend_review"
    description = (
        "Find students who have review items due and topics that need "
        "revisiting. Returns a list of overdue reviews and topics with "
        "declining mastery. Use when the teacher asks who needs review, "
        "which topics to revisit, or wants spaced repetition data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "course_id": {
                "type": "integer",
                "description": "The course ID.",
            },
        },
        "required": ["course_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        from app.core.database import get_ai_conn

        course_id = kwargs.get("_course_id") or kwargs["course_id"]

        try:
            async with get_ai_conn() as conn:
                # Find students with the most overdue reviews
                overdue = await conn.fetch(
                    """SELECT sr.student_id,
                              COUNT(*) AS due_count,
                              MIN(sr.next_review_date) AS earliest_due
                       FROM spaced_repetitions sr
                       WHERE sr.course_id = $1
                         AND sr.next_review_date <= CURRENT_DATE
                       GROUP BY sr.student_id
                       ORDER BY due_count DESC
                       LIMIT 10""",
                    course_id,
                )

                # Find topics with lowest average mastery
                weak_topics = await conn.fetch(
                    """SELECT kn.name, kn.name_vi,
                              AVG(skp.mastery_level) AS avg_mastery,
                              COUNT(DISTINCT skp.student_id) AS affected_students,
                              SUM(skp.wrong_count) AS total_errors
                       FROM student_knowledge_progress skp
                       JOIN knowledge_nodes kn ON kn.id = skp.node_id
                       WHERE skp.course_id = $1
                         AND skp.mastery_level < 0.6
                       GROUP BY kn.id, kn.name, kn.name_vi
                       HAVING COUNT(DISTINCT skp.student_id) >= 1
                       ORDER BY avg_mastery ASC
                       LIMIT 5""",
                    course_id,
                )

            overdue_data = [
                {
                    "student_id": r["student_id"],
                    "due_count": r["due_count"],
                    "earliest_due": str(r["earliest_due"]),
                }
                for r in overdue
            ]

            weak_data = [
                {
                    "name": r.get("name_vi") or r["name"],
                    "avg_mastery": round(float(r["avg_mastery"]), 2),
                    "affected_students": r["affected_students"],
                    "total_errors": r["total_errors"],
                }
                for r in weak_topics
            ]

            total_overdue = sum(r["due_count"] for r in overdue_data)

            return ToolResult(
                status="success",
                data={
                    "overdue_students": overdue_data,
                    "weak_topics": weak_data,
                    "total_overdue_items": total_overdue,
                },
                message=(
                    f"{len(overdue_data)} học sinh có bài ôn tập quá hạn "
                    f"(tổng {total_overdue} mục). "
                    f"{len(weak_data)} chủ đề có mastery trung bình < 60%."
                ),
            )

        except Exception as e:
            logger.error("recommend_review failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi: {e}",
            )
