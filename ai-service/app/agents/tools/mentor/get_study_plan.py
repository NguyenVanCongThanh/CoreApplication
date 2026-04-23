"""
Mentor Tool: get_study_plan

Builds a personalized study plan based on the student's
spaced repetition schedule, knowledge gaps, and course structure.
"""
from __future__ import annotations

import logging

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class GetStudyPlanTool(BaseTool):
    name = "get_study_plan"
    description = (
        "Get a personalized study plan for the student. Combines spaced "
        "repetition due items, knowledge gaps, and course structure to "
        "recommend what to study next. Use when the student asks 'what "
        "should I study?', 'what do I need to review?', or wants a "
        "learning roadmap."
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
        from app.agents.memory.personalize_memory import personalize_memory
        from app.services.quiz_service import sr_service

        course_id = kwargs.get("_course_id") or kwargs["course_id"]
        student_id = kwargs.get("_user_id", 0)

        try:
            # 1. Due reviews (highest priority)
            due_reviews = await sr_service.get_due_reviews(
                student_id=student_id,
                course_id=course_id,
                limit=10,
            )

            # 2. Review stats
            review_stats = await sr_service.get_review_stats(
                student_id=student_id,
                course_id=course_id,
            )

            # 3. Weak areas
            weaknesses = await personalize_memory.get_weaknesses(
                user_id=student_id, course_id=course_id, limit=5,
            )

            # 4. Strengths (for positive reinforcement)
            strengths = await personalize_memory.get_strengths(
                user_id=student_id, course_id=course_id, limit=3,
            )

            # 5. Build study plan
            plan_items = []

            # Priority 1: Overdue reviews
            if due_reviews:
                plan_items.append({
                    "priority": 1,
                    "type": "review",
                    "title": "Ôn tập các câu hỏi quá hạn",
                    "description": f"{len(due_reviews)} câu hỏi cần ôn tập hôm nay",
                    "items": [
                        {
                            "question_id": r.get("question_id"),
                            "node_name": r.get("node_name", ""),
                            "overdue_days": str(r.get("next_review_date", "")),
                        }
                        for r in due_reviews[:5]
                    ],
                })

            # Priority 2: Weak concepts
            if weaknesses:
                plan_items.append({
                    "priority": 2,
                    "type": "study",
                    "title": "Củng cố kiến thức yếu",
                    "description": f"{len(weaknesses)} chủ đề cần ôn tập thêm",
                    "items": [
                        {
                            "node_name": w["name"],
                            "mastery": w["mastery_level"],
                            "suggestion": (
                                "Cần ôn kỹ" if w["mastery_level"] < 0.3
                                else "Cần luyện thêm"
                            ),
                        }
                        for w in weaknesses
                    ],
                })

            # Priority 3: Positive feedback
            if strengths:
                plan_items.append({
                    "priority": 3,
                    "type": "strength",
                    "title": "Điểm mạnh của bạn",
                    "description": "Giữ vững phong độ!",
                    "items": [
                        {"node_name": s["name"], "mastery": s["mastery_level"]}
                        for s in strengths
                    ],
                })

            # Summary
            due_today = int(review_stats.get("due_today", 0)) if review_stats else 0
            total_tracked = int(review_stats.get("total_tracked", 0)) if review_stats else 0

            return ToolResult(
                status="success",
                data={
                    "plan": plan_items,
                    "review_stats": {
                        "due_today": due_today,
                        "total_tracked": total_tracked,
                    },
                },
                message=(
                    f"Kế hoạch hôm nay: {due_today} bài ôn tập, "
                    f"{len(weaknesses)} chủ đề cần cải thiện."
                ),
                ui_instruction={
                    "component": "StudyPlanWidget",
                    "props": {
                        "plan": plan_items,
                        "due_today": due_today,
                    },
                },
            )

        except Exception as e:
            logger.error("get_study_plan failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi tạo kế hoạch: {e}",
            )
