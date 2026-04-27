"""
ai-service/app/agents/memory/teacher_anchor.py

DEPRECATED compatibility shim.

The teacher anchor was the original "ground-truth course list" mechanism.
It has been generalised into `active_courses.py`, which works for both
teacher and mentor agents.

This module is kept ONLY to preserve any external imports of
`load_teacher_anchor` / `format_teacher_anchor_for_prompt` /
`invalidate_teacher_anchor`. New code must use `active_courses.py`.
"""
from __future__ import annotations

from typing import Any

from app.agents.memory.active_courses import (
    format_active_courses_for_prompt,
    invalidate_active_courses,
    load_active_courses,
)
 
 
async def load_teacher_anchor(user_id: int) -> dict[str, Any]:
    """Backward-compat wrapper around `load_active_courses`."""
    return await load_active_courses(user_id, "teacher", include_nodes=True)
 
 
def invalidate_teacher_anchor(user_id: int) -> None:
    """Backward-compat wrapper. Drops both teacher + mentor caches."""
    invalidate_active_courses(user_id)


def format_teacher_anchor_for_prompt(anchor: dict) -> str:
    """Backward-compat wrapper around `format_active_courses_for_prompt`."""
    return format_active_courses_for_prompt(anchor)