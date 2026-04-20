"""
Teacher Tool: generate_content_draft

Uses LLM to generate text-based content drafts (outlines, summaries,
slide structures) based on course materials. The output is a DRAFT
that the teacher reviews before publishing.

This tool does NOT create content in LMS — it generates text for the
teacher to copy/paste or further develop. Creating LMS content requires
the teacher to use the LMS UI directly.
"""
from __future__ import annotations

import logging

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class GenerateContentDraftTool(BaseTool):
    name = "generate_content_draft"
    description = (
        "Generate a text-based content draft such as a lesson outline, "
        "summary, or slide structure for a topic. The draft is based on "
        "existing course materials retrieved via RAG. Use when the teacher "
        "asks to create content, write a lesson plan, summarize materials, "
        "or prepare slides for a topic."
    )
    parameters = {
        "type": "object",
        "properties": {
            "course_id": {
                "type": "integer",
                "description": "The course ID.",
            },
            "topic": {
                "type": "string",
                "description": "The topic or concept to generate content about.",
            },
            "content_type": {
                "type": "string",
                "enum": ["outline", "summary", "slide_structure",
                         "lesson_plan", "explanation"],
                "description": "Type of content to generate.",
                "default": "outline",
            },
            "language": {
                "type": "string",
                "enum": ["vi", "en"],
                "default": "vi",
            },
        },
        "required": ["course_id", "topic"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        from app.core.llm import chat_complete
        from app.services.rag_service import rag_service

        course_id = kwargs["course_id"]
        topic = kwargs["topic"]
        content_type = kwargs.get("content_type", "outline")
        language = kwargs.get("language", "vi")

        try:
            # 1. RAG retrieve relevant materials
            chunks = await rag_service.search_multilingual(
                query=topic, course_id=course_id, top_k=5,
            )
            context = "\n---\n".join(c.chunk_text for c in chunks) if chunks else ""

            # 2. Build prompt based on content_type
            type_instructions = {
                "outline": "Create a detailed lesson outline with main topics, subtopics, and key points.",
                "summary": "Write a comprehensive summary of the topic.",
                "slide_structure": "Create a slide deck structure with slide titles, bullet points, and speaker notes.",
                "lesson_plan": "Create a lesson plan with objectives, activities, timing, and assessment methods.",
                "explanation": "Write a clear, detailed explanation suitable for students.",
            }
            instruction = type_instructions.get(content_type, type_instructions["outline"])

            lang_note = (
                "Viết bằng tiếng Việt." if language == "vi"
                else "Write in English."
            )

            system_prompt = (
                f"You are an expert educational content creator. {lang_note}\n"
                f"Task: {instruction}\n"
                f"Topic: {topic}\n\n"
                f"Base your content on the following course materials if available. "
                f"If the materials are insufficient, use your general knowledge "
                f"but clearly mark such sections.\n\n"
                f"COURSE MATERIALS:\n{context if context else '(No materials found)'}"
            )

            result = await chat_complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate a {content_type} about: {topic}"},
                ],
                temperature=0.5,
                max_tokens=2048,
            )

            return ToolResult(
                status="success",
                data={
                    "content_type": content_type,
                    "topic": topic,
                    "draft": result,
                    "source_chunks": len(chunks),
                },
                message=f"Đã tạo {content_type} cho chủ đề '{topic}'.",
                ui_instruction={
                    "component": "ContentDraftPreview",
                    "props": {
                        "content_type": content_type,
                        "topic": topic,
                        "draft": result,
                        "course_id": course_id,
                    },
                },
            )

        except Exception as e:
            logger.error("generate_content_draft failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi khi tạo nội dung: {e}",
            )
