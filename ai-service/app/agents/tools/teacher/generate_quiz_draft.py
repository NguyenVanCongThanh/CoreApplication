"""
Teacher Tool: generate_quiz_draft

Wraps quiz_service.generate_for_node() to create quiz questions
as DRAFTs. The teacher must approve them via the HITL widget
before they are published to the LMS.
"""
from __future__ import annotations

import logging

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class GenerateQuizDraftTool(BaseTool):
    name = "generate_quiz_draft"
    description = (
        "Generate draft quiz questions for a knowledge node in a course. "
        "Questions are saved as DRAFT status and require teacher approval "
        "before being published. Use this when the teacher asks to create "
        "quiz questions, test questions, or assessments for a topic."
    )
    parameters = {
        "type": "object",
        "properties": {
            "course_id": {
                "type": "integer",
                "description": "The course ID to generate questions for.",
            },
            "node_id": {
                "type": "integer",
                "description": "The knowledge node ID (topic) to generate questions about.",
            },
            "bloom_levels": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["remember", "understand", "apply",
                             "analyze", "evaluate", "create"],
                },
                "description": (
                    "Bloom taxonomy levels for question difficulty. "
                    "Defaults to all levels if not specified."
                ),
            },
            "num_questions_per_level": {
                "type": "integer",
                "description": "Number of questions per Bloom level. Default: 1.",
                "default": 1,
            },
            "language": {
                "type": "string",
                "enum": ["vi", "en"],
                "description": "Language for generated questions. Default: vi.",
                "default": "vi",
            },
        },
        "required": ["course_id", "node_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        from app.services.quiz_service import quiz_gen_service

        course_id = kwargs["course_id"]
        node_id = kwargs["node_id"]
        bloom_levels = kwargs.get("bloom_levels")
        num_per_level = kwargs.get("num_questions_per_level", 1)
        language = kwargs.get("language", "vi")
        created_by = kwargs.get("_user_id", 0)  # injected by executor

        try:
            gen_ids = await quiz_gen_service.generate_for_node(
                node_id=node_id,
                course_id=course_id,
                created_by=created_by,
                bloom_levels=bloom_levels,
                language=language,
                questions_per_level=num_per_level,
            )

            # Fetch the generated drafts for preview
            drafts = await quiz_gen_service.list_drafts(
                course_id=course_id, node_id=node_id,
            )
            # Only return the newly created ones
            new_drafts = [d for d in drafts if d.get("id") in gen_ids]

            preview_data = []
            for d in new_drafts:
                preview_data.append({
                    "gen_id": d["id"],
                    "bloom_level": d.get("bloom_level", ""),
                    "question_text": d.get("question_text", ""),
                    "question_type": d.get("question_type", "SINGLE_CHOICE"),
                    "answer_options": d.get("answer_options", []),
                    "explanation": d.get("explanation", ""),
                    "node_name": d.get("node_name", ""),
                })

            return ToolResult(
                status="pending_human_approval",
                data={
                    "generated_count": len(gen_ids),
                    "gen_ids": gen_ids,
                    "drafts": preview_data,
                },
                message=(
                    f"Đã tạo {len(gen_ids)} câu hỏi nháp. "
                    f"Vui lòng xem lại và phê duyệt."
                    if language == "vi" else
                    f"Generated {len(gen_ids)} draft questions. "
                    f"Please review and approve."
                ),
                ui_instruction={
                    "component": "QuizDraftPreview",
                    "props": {
                        "drafts": preview_data,
                        "course_id": course_id,
                        "node_id": node_id,
                    },
                },
            )

        except ValueError as e:
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=str(e),
            )
        except Exception as e:
            logger.error("generate_quiz_draft failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi khi tạo câu hỏi: {e}",
            )
