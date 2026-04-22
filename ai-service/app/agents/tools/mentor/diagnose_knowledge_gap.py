"""
Mentor Tool: diagnose_knowledge_gap

Analyzes the student's learning data to identify knowledge gaps,
weak concepts, and prerequisite chains that need attention.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class DiagnoseKnowledgeGapTool(BaseTool):
    name = "diagnose_knowledge_gap"
    description = (
        "Diagnose knowledge gaps for a student in a course. Returns weak "
        "concepts, prerequisite chains, and recent error patterns. Use "
        "when the student asks what they need to improve, report struggles, "
        "or when you want to understand their learning state."
    )
    parameters = {
        "type": "object",
        "properties": {
            "course_id": {
                "type": "integer",
                "description": "The course to analyze.",
            },
            "topic": {
                "type": "string",
                "description": (
                    "Optional. Specific topic to focus on. "
                    "If omitted, analyzes all topics."
                ),
            },
        },
        "required": ["course_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        from app.agents.memory.personalize_memory import personalize_memory
        from app.core.config import get_settings

        course_id = kwargs.get("_course_id") or kwargs["course_id"]
        topic = kwargs.get("topic")
        student_id = kwargs.get("_user_id", 0)
        settings = get_settings()

        try:
            # 1. Get weaknesses
            weaknesses = await personalize_memory.get_weaknesses(
                user_id=student_id, course_id=course_id, limit=10,
            )

            # 2. Get recent errors
            recent_errors = await personalize_memory.get_recent_errors(
                user_id=student_id, limit=5,
            )

            # 3. Get prerequisite path for weak nodes (if Neo4j available)
            prereq_info = []
            if weaknesses and settings.neo4j_enabled:
                try:
                    from app.services.neo4j_service import neo4j_service
                    for w in weaknesses[:3]:
                        neighbors = await neo4j_service.get_node_neighbors(
                            node_id=w["node_id"], max_depth=1, max_nodes=5,
                        )
                        if neighbors.get("neighbors"):
                            prereq_info.append({
                                "weak_node": w["name"],
                                "related_concepts": [
                                    n.get("name", "")
                                    for n in neighbors["neighbors"][:3]
                                ],
                            })
                except Exception as exc:
                    logger.warning("Neo4j prereq lookup failed: %s", exc)

            # 4. Build gap analysis
            gap_analysis = {
                "weaknesses": weaknesses,
                "recent_errors": recent_errors,
                "prerequisite_chains": prereq_info,
                "total_weak_concepts": len(weaknesses),
            }

            if not weaknesses and not recent_errors:
                return ToolResult(
                    status="success",
                    data=gap_analysis,
                    message=(
                        "Chưa có đủ dữ liệu để phân tích. "
                        "Hãy làm thêm bài kiểm tra để hệ thống có dữ liệu."
                    ),
                    ui_instruction={
                        "component": "KnowledgeGapMap",
                        "props": {"gaps": [], "message": "No data yet"},
                    },
                )

            return ToolResult(
                status="success",
                data=gap_analysis,
                message=(
                    f"Phát hiện {len(weaknesses)} chủ đề yếu. "
                    + (f"Lỗi gần đây: {recent_errors[0].get('gap_type', '')}"
                       if recent_errors else "")
                ),
                ui_instruction={
                    "component": "KnowledgeGapMap",
                    "props": {
                        "gaps": [
                            {
                                "name": w["name"],
                                "mastery": w["mastery_level"],
                                "wrong_count": w.get("wrong_count", 0),
                            }
                            for w in weaknesses[:10]
                        ],
                        "prerequisites": prereq_info,
                    },
                },
            )

        except Exception as e:
            logger.error("diagnose_knowledge_gap failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi phân tích: {e}",
            )
