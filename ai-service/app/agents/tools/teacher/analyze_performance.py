"""
Teacher Tool: analyze_performance

Aggregates student performance data from the AI database for a course.
Provides class-wide analytics including per-node mastery, error rates,
and at-risk student identification.
"""
from __future__ import annotations

import logging

from app.agents.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class AnalyzePerformanceTool(BaseTool):
    name = "analyze_student_performance"
    description = (
        "Analyze student performance for a course or a specific student. "
        "Returns mastery levels per topic, error rates, and at-risk indicators. "
        "Use when the teacher asks about class performance, student progress, "
        "weak topics, or needs analytics data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "course_id": {
                "type": "integer",
                "description": "The course ID to analyze.",
            },
            "student_id": {
                "type": "integer",
                "description": (
                    "Optional. Specific student to analyze. "
                    "If omitted, returns class-wide analytics."
                ),
            },
        },
        "required": ["course_id"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        from app.services.diagnosis_service import diagnosis_service

        course_id = kwargs.get("_course_id") or kwargs["course_id"]
        student_id = kwargs.get("student_id")

        try:
            if student_id:
                # Single student heatmap
                heatmap = await diagnosis_service.get_student_heatmap(
                    student_id=student_id, course_id=course_id,
                )
                if not heatmap:
                    return ToolResult(
                        status="success",
                        data={"heatmap": [], "student_id": student_id},
                        message="Chưa có dữ liệu học tập cho học sinh này.",
                    )

                # Compute summary
                total_nodes = len(heatmap)
                tested_nodes = sum(1 for h in heatmap if h.get("total_attempts", 0) > 0)
                avg_mastery = (
                    sum(h.get("mastery_level", 0) for h in heatmap if h.get("total_attempts", 0) > 0)
                    / max(tested_nodes, 1)
                )
                weak_nodes = [
                    h for h in heatmap
                    if h.get("mastery_level", 0) < 0.5 and h.get("total_attempts", 0) > 0
                ]

                return ToolResult(
                    status="success",
                    data={
                        "student_id": student_id,
                        "total_nodes": total_nodes,
                        "tested_nodes": tested_nodes,
                        "avg_mastery": round(avg_mastery, 2),
                        "weak_nodes": [
                            {
                                "node_name": n.get("node_name", ""),
                                "mastery": round(float(n.get("mastery_level", 0)), 2),
                                "wrong_count": n.get("wrong_count", 0),
                            }
                            for n in weak_nodes[:10]
                        ],
                        "heatmap": heatmap[:20],
                    },
                    message=(
                        f"Học sinh {student_id}: mastery trung bình {avg_mastery:.0%}, "
                        f"{len(weak_nodes)} chủ đề yếu."
                    ),
                    ui_instruction={
                        "component": "PerformanceChart",
                        "props": {
                            "type": "student",
                            "student_id": student_id,
                            "heatmap": heatmap[:20],
                            "avg_mastery": round(avg_mastery, 2),
                        },
                    },
                )
            else:
                # Class-wide heatmap
                heatmap = await diagnosis_service.get_class_heatmap(course_id)
                if not heatmap:
                    return ToolResult(
                        status="success",
                        data={"heatmap": [], "course_id": course_id},
                        message="Chưa có dữ liệu học tập cho khóa học này.",
                    )

                critical_nodes = [
                    h for h in heatmap
                    if float(h.get("wrong_rate", 0)) > 40
                ]

                return ToolResult(
                    status="success",
                    data={
                        "course_id": course_id,
                        "total_nodes": len(heatmap),
                        "critical_nodes": [
                            {
                                "node_name": n.get("node_name", ""),
                                "avg_mastery": round(float(n.get("avg_mastery", 0)), 2),
                                "wrong_rate": round(float(n.get("wrong_rate", 0)), 1),
                                "student_count": n.get("student_count", 0),
                            }
                            for n in critical_nodes[:10]
                        ],
                        "heatmap": heatmap[:20],
                    },
                    message=(
                        f"Lớp có {len(critical_nodes)} chủ đề có tỉ lệ sai > 40%."
                    ),
                    ui_instruction={
                        "component": "PerformanceChart",
                        "props": {
                            "type": "class",
                            "course_id": course_id,
                            "heatmap": heatmap[:20],
                        },
                    },
                )

        except Exception as e:
            logger.error("analyze_performance failed: %s", e)
            return ToolResult(
                status="error",
                data={"error": str(e)},
                message=f"Lỗi phân tích: {e}",
            )
