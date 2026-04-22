"""
Teacher Tool: list_knowledge_nodes

Lists knowledge nodes (topics) for a course so the teacher can
reference them when using other tools (e.g., generate_quiz_draft).
"""
from __future__ import annotations

import logging

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ListKnowledgeNodesTool(BaseTool):
    name = "list_knowledge_nodes"
    description = (
        "List knowledge nodes (topics) available in a course. Returns "
        "node IDs and names. Use this FIRST when the teacher references "
        "a topic by name and you need the node_id for other tools."
    )
    parameters = {
        "type": "object",
        "properties": {
            "course_id": {
                "type": "integer",
                "description": "The course ID.",
            },
            "search": {
                "type": "string",
                "description": "Optional search term to filter nodes by name.",
            },
        },
        "required": ["course_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        from app.core.database import get_ai_conn

        # Prefer session-injected course_id over LLM-generated value
        session_course_id = kwargs.get("_course_id")
        llm_course_id = kwargs.get("course_id")
        course_id = session_course_id or llm_course_id
        search = kwargs.get("search", "")

        if not course_id:
            return ToolResult(
                status="error",
                data={"error": "missing_course_id"},
                message=(
                    "Không xác định được khóa học. "
                    "Hãy hỏi giáo viên đang muốn làm việc với khóa học nào."
                ),
            )

        try:
            async with get_ai_conn() as conn:
                if search:
                    rows = await conn.fetch(
                        """SELECT id, name, name_vi, description, level, order_index
                           FROM knowledge_nodes
                           WHERE course_id = $1
                             AND (name ILIKE $2 OR name_vi ILIKE $2
                                  OR description ILIKE $2)
                           ORDER BY level, order_index
                           LIMIT 20""",
                        course_id, f"%{search}%",
                    )
                else:
                    rows = await conn.fetch(
                        """SELECT id, name, name_vi, description, level, order_index
                           FROM knowledge_nodes
                           WHERE course_id = $1
                           ORDER BY level, order_index
                           LIMIT 30""",
                        course_id,
                    )

            nodes = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "name_vi": r.get("name_vi", ""),
                    "description": (r.get("description") or "")[:100],
                    "level": r["level"],
                }
                for r in rows
            ]

            # If 0 nodes found AND course_id came from LLM (not session),
            # check which courses actually have nodes to guide the LLM.
            if len(nodes) == 0 and not session_course_id:
                async with get_ai_conn() as conn:
                    available = await conn.fetch(
                        """SELECT course_id, COUNT(*) as cnt
                           FROM knowledge_nodes
                           GROUP BY course_id
                           ORDER BY course_id
                           LIMIT 10"""
                    )
                if available:
                    hint_parts = [
                        f"course_id={r['course_id']} ({r['cnt']} nodes)"
                        for r in available
                    ]
                    return ToolResult(
                        status="success",
                        data={"nodes": [], "count": 0, "available_courses": [
                            {"course_id": r["course_id"], "node_count": r["cnt"]}
                            for r in available
                        ]},
                        message=(
                            f"Không tìm thấy chủ đề nào trong course_id={course_id}. "
                            f"Các khóa học có dữ liệu đã index: {', '.join(hint_parts)}. "
                            "Hãy hỏi giáo viên để xác nhận đúng khóa học."
                        ),
                    )

            return ToolResult(
                status="success",
                data={"nodes": nodes, "count": len(nodes)},
                message=f"Tìm thấy {len(nodes)} chủ đề trong khóa học.",
            )

        except Exception as e:
            logger.error("list_knowledge_nodes failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi: {e}",
            )
