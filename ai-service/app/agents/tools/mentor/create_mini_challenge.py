"""
Mentor Tool: create_mini_challenge

Creates a short interactive quiz question directly from LLM.
NOT saved to the main quiz database — this is ephemeral,
used for real-time learning interaction within the chat.
"""
from __future__ import annotations

import logging

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class CreateMiniChallengeTool(BaseTool):
    name = "create_mini_challenge"
    description = (
        "Create a short interactive quiz question for the student to "
        "practice a concept. The question is NOT saved to the database — "
        "it's ephemeral and used for in-chat learning. Use when guiding "
        "students through a topic and you want to test their understanding "
        "with a quick exercise."
    )
    parameters = {
        "type": "object",
        "properties": {
            "concept": {
                "type": "string",
                "description": "The specific concept to test.",
            },
            "question_type": {
                "type": "string",
                "enum": ["multiple_choice", "fill_in_blank", "true_false",
                         "short_answer"],
                "description": "Type of question. Default: multiple_choice.",
                "default": "multiple_choice",
            },
            "difficulty": {
                "type": "string",
                "enum": ["easy", "medium", "hard"],
                "description": "Difficulty level.",
                "default": "medium",
            },
            "language": {
                "type": "string",
                "enum": ["vi", "en"],
                "default": "vi",
            },
            "course_id": {
                "type": "integer",
                "description": "Optional course ID for RAG context.",
            },
        },
        "required": ["concept"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        from app.core.llm import chat_complete_json
        from app.core.llm_gateway import TASK_QUIZ_GEN

        concept = kwargs["concept"]
        q_type = kwargs.get("question_type", "multiple_choice")
        difficulty = kwargs.get("difficulty", "medium")
        language = kwargs.get("language", "vi")
        course_id = kwargs.get("course_id")

        try:
            # Optional: get RAG context for better questions
            context = ""
            if course_id:
                from app.services.rag_service import rag_service
                chunks = await rag_service.search_multilingual(
                    query=concept, course_id=course_id, top_k=2,
                )
                if chunks:
                    context = "\n".join(c.chunk_text for c in chunks)

            lang_note = "Viết bằng tiếng Việt." if language == "vi" else "Write in English."

            type_instructions = {
                "multiple_choice": (
                    "Create a multiple-choice question with exactly 4 options (A, B, C, D). "
                    "Only one option should be correct."
                ),
                "fill_in_blank": (
                    "Create a fill-in-the-blank question. Use ___ to mark the blank. "
                    "Provide the correct answer."
                ),
                "true_false": (
                    "Create a true/false statement. Include a brief explanation."
                ),
                "short_answer": (
                    "Create a short-answer question that can be answered in 1-2 sentences."
                ),
            }

            system_prompt = (
                f"You are a quiz creator for educational purposes. {lang_note}\n"
                f"Difficulty: {difficulty}\n"
                f"{type_instructions.get(q_type, type_instructions['multiple_choice'])}\n\n"
                f"Output JSON:\n"
                f'{{"question": "string",'
                f' "options": ["A. ...", "B. ...", "C. ...", "D. ..."],'
                f' "correct_answer": "A",'
                f' "explanation": "string",'
                f' "hint": "string"}}\n\n'
                f"For fill_in_blank, omit 'options' and set correct_answer to the answer.\n"
                f"For true_false, options should be ['Đúng/True', 'Sai/False'].\n"
                f"For short_answer, omit 'options'.\n\n"
                + (f"CONTEXT:\n{context}" if context else "")
            )

            result = await chat_complete_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create a {difficulty} {q_type} question about: {concept}"},
                ],
                temperature=0.7,
                max_tokens=512,
                task=TASK_QUIZ_GEN,
            )

            return ToolResult(
                status="success",
                data={
                    "challenge": result,
                    "concept": concept,
                    "question_type": q_type,
                    "difficulty": difficulty,
                },
                message=f"Đây là một bài tập nhỏ về '{concept}'!",
                ui_instruction={
                    "component": "MiniChallengeWidget",
                    "props": {
                        "question": result.get("question", ""),
                        "options": result.get("options", []),
                        "correct_answer": result.get("correct_answer", ""),
                        "explanation": result.get("explanation", ""),
                        "hint": result.get("hint", ""),
                        "question_type": q_type,
                    },
                },
            )

        except Exception as e:
            logger.error("create_mini_challenge failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi tạo bài tập: {e}",
            )
