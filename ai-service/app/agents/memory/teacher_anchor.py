"""
ai-service/app/agents/memory/teacher_anchor.py
 
Teacher ground-truth anchor.
 
For every turn of a TEACHER session, we inject the real list of
(course_id, course_title, [node_id, node_name, level]) into the system
prompt. The LLM then has no reason to fabricate numeric IDs — it can
simply reference the ones it sees.
 
We cache per user_id for a short TTL to avoid hammering the LMS and
Postgres on every turn. The cache is invalidated manually when a course
or knowledge node is mutated (see `invalidate_teacher_anchor`).
"""
from __future__ import annotations
 
import logging
import time
from typing import Any
 
import httpx
 
from app.core.config import get_settings
from app.core.database import get_ai_conn
 
logger = logging.getLogger(__name__)
settings = get_settings()
 
# user_id -> (expires_at_monotonic, data)
_CACHE: dict[int, tuple[float, dict]] = {}
_TTL_SECONDS = 60.0
 
# Keep the prompt block small: cap total nodes across all courses.
_MAX_NODES_PER_COURSE = 25
_MAX_COURSES = 8
 
 
async def load_teacher_anchor(user_id: int) -> dict[str, Any]:
    """
    Return the teacher's real courses + knowledge nodes.
 
    Shape:
        {
            "courses": [
                {
                    "id": 1,
                    "title": "Multi Agent System",
                    "status": "PUBLISHED",
                    "nodes": [
                        {"id": 1, "name": "Giới thiệu MAS", "level": 0},
                        ...
                    ],
                },
                ...
            ]
        }
 
    Cached for ~60s per user. Never raises — returns an empty structure
    on any failure.
    """
    if not user_id:
        return {"courses": []}
 
    now = time.monotonic()
    cached = _CACHE.get(user_id)
    if cached and cached[0] > now:
        return cached[1]
 
    courses: list[dict] = []
    try:
        courses = await _fetch_teacher_courses(user_id)
        courses = courses[:_MAX_COURSES]
        for c in courses:
            c["nodes"] = await _fetch_course_nodes(c["id"])
    except Exception as exc:  # noqa: BLE001 — anchor must never break the turn
        logger.warning(
            "teacher_anchor load failed for user=%s: %s", user_id, exc,
        )
        courses = []
 
    data = {"courses": courses}
    _CACHE[user_id] = (now + _TTL_SECONDS, data)
    return data
 
 
def invalidate_teacher_anchor(user_id: int) -> None:
    """Drop the cached anchor (e.g. after creating a course / section)."""
    _CACHE.pop(user_id, None)
 
 
async def _fetch_teacher_courses(user_id: int) -> list[dict]:
    lms_base = settings.lms_service_url.rstrip("/")
    headers = {
        "X-API-Secret": settings.ai_service_secret,
        "X-User-Id": str(user_id),
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            f"{lms_base}/api/v1/courses/my", headers=headers,
        )
        if resp.status_code != 200:
            return []
        try:
            payload = resp.json()
        except Exception:
            return []
 
    if isinstance(payload, dict):
        payload = payload.get("data", [])
    if not isinstance(payload, list):
        return []
 
    out: list[dict] = []
    for c in payload:
        if not isinstance(c, dict) or c.get("id") is None:
            continue
        out.append({
            "id": c.get("id"),
            "title": c.get("title") or "",
            "status": c.get("status"),
        })
    return out
 
 
async def _fetch_course_nodes(course_id: int) -> list[dict]:
    try:
        async with get_ai_conn() as conn:
            rows = await conn.fetch(
                """SELECT id, name, name_vi, level
                   FROM knowledge_nodes
                   WHERE course_id = $1
                   ORDER BY level, order_index
                   LIMIT $2""",
                course_id, _MAX_NODES_PER_COURSE,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "teacher_anchor node fetch failed for course=%s: %s",
            course_id, exc,
        )
        return []
 
    nodes: list[dict] = []
    for r in rows:
        name = r.get("name_vi") or r["name"] or ""
        nodes.append({
            "id": r["id"],
            "name": name,
            "level": r["level"],
        })
    return nodes
 
 
def format_teacher_anchor_for_prompt(anchor: dict) -> str:
    """
    Render the anchor as a ground-truth block for the system prompt.
 
    Returns an empty string if the teacher has no courses — the prompt
    template will fall back to a default instructional sentence.
    """
    courses = anchor.get("courses") or []
    if not courses:
        return ""
 
    lines = [
        "AVAILABLE COURSES AND KNOWLEDGE NODES",
        "(These are the ONLY valid IDs. Do NOT invent any other "
        "course_id or node_id.)",
    ]
    for c in courses:
        status = f" [{c['status']}]" if c.get("status") else ""
        lines.append(
            f"- course_id={c['id']} \"{c.get('title', '')}\"{status}"
        )
        nodes = c.get("nodes") or []
        if not nodes:
            lines.append(
                "    (no indexed knowledge nodes — the teacher must "
                "index course documents before a quiz can be generated)"
            )
            continue
        for n in nodes:
            level = (
                f" (level {n['level']})" if n.get("level") is not None else ""
            )
            lines.append(
                f"    node_id={n['id']}: {n['name']}{level}"
            )
    return "\n".join(lines)