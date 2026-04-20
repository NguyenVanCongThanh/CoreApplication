"""
Teacher Tool: generate_content_draft

Uses LLM to generate text-based content drafts (outlines, summaries,
slide structures) based on course materials. The output is a DRAFT
that the teacher reviews before publishing.
"""
from __future__ import annotations

import logging
import httpx
from app.agents.tools.base_tool import BaseTool, ToolResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GenerateContentDraftTool(BaseTool):
    name = "generate_content_draft"
    description = (
        "Generate a text-based content draft such as a lesson outline, "
        "summary, or slide structure for a topic. The draft is based on "
        "existing course materials retrieved via RAG. It also suggests "
        "the best course section to save this content to."
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
        from app.core.llm import chat_complete_json
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

            # 2. Fetch existing sections to provide as options
            sections = []
            lms_base = settings.lms_service_url.rstrip("/")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{lms_base}/api/v1/courses/{course_id}/sections",
                    headers={"X-AI-Secret": settings.ai_service_secret},
                )
                if resp.status_code == 200:
                    sections = resp.json().get("data") or []

            # 3. Build prompt
            type_instructions = {
                "outline": "Create a detailed lesson outline with main topics, subtopics, and key points.",
                "summary": "Write a comprehensive summary of the topic.",
                "slide_structure": "Create a slide deck structure with slide titles, bullet points, and speaker notes.",
                "lesson_plan": "Create a lesson plan with objectives, activities, timing, and assessment methods.",
                "explanation": "Write a clear, detailed explanation suitable for students.",
            }
            instruction = type_instructions.get(content_type, type_instructions["outline"])

            lang_note = "Viết bằng tiếng Việt." if language == "vi" else "Write in English."

            section_list_str = "\n".join([f"- ID {s['id']}: {s['title']}" for s in sections])

            system_prompt = (
                f"You are an expert educational content creator. {lang_note}\n"
                f"Task: {instruction}\n"
                f"Topic: {topic}\n\n"
                f"Base your content on the following course materials if available.\n"
                f"COURSE MATERIALS:\n{context if context else '(No materials found)'}\n\n"
                f"Also, look at these existing course sections and suggest which one is best to put this content in:\n"
                f"{section_list_str if sections else '(No existing sections found)'}\n\n"
                f"Return your response as a JSON object with keys: "
                f"'draft' (markdown string) and 'suggested_section_id' (integer or null)."
            )

            result = await chat_complete_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate a {content_type} about: {topic}"},
                ],
                temperature=0.5,
                max_tokens=2048,
            )

            draft_text = result.get("draft", "")
            suggested_sid = result.get("suggested_section_id")

            return ToolResult(
                status="success",
                data={
                    "content_type": content_type,
                    "topic": topic,
                    "draft": draft_text,
                    "suggested_section_id": suggested_sid,
                },
                message=f"Đã tạo {content_type} cho chủ đề '{topic}'.",
                ui_instruction={
                    "component": "ContentDraftPreview",
                    "props": {
                        "content_type": content_type,
                        "topic": topic,
                        "draft": draft_text,
                        "course_id": course_id,
                        "suggested_section_id": suggested_sid,
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
