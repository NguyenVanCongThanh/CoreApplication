"""
ai-service/app/agents/core/scope_resolver.py

Course Scope Resolver — answers "which course is the user talking about?"

The agent is GLOBAL: a teacher manages many courses, a student is enrolled
in many. Most user messages do NOT name a course explicitly, so we must
infer scope from a combination of:

    1. The list of active courses for this user (single source of truth).
    2. The MTM session anchor (current_course_id from a prior turn).
    3. The course_id explicitly attached to this turn (e.g. the frontend
       opened a course-scoped chat panel).
    4. Substring matches between the user's message and course titles.
    5. Deictic / global keywords ("cái này", "this course", "tất cả khoá").
    6. (Last resort) a fast LLM extraction call.

Output is a `CourseScope` object the ReAct loop uses to:
    - bias retrieval (context_builder) toward one or many courses
    - inject the focused course_id into tool calls
    - trigger a SCOPE clarification when the answer is genuinely ambiguous

Cheap path first (zero LLM), LLM only as a fallback. Resolver MUST be
deterministic and never raise — fall back to "ambiguous" on any error.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from app.agents.memory.active_courses import (
    find_course_by_title,
    list_course_titles,
)
from app.core.config import get_settings
from app.core.llm import chat_complete_json
from app.core.llm_gateway import TASK_AGENT_ROUTER

logger = logging.getLogger(__name__)
settings = get_settings()


ScopeMode = Literal["single", "multi", "all", "none", "ambiguous"]


@dataclass(slots=True)
class CourseScope:
    """Resolved view of which course(s) the current turn applies to."""

    mode: ScopeMode
    focus_course_id: Optional[int] = None
    candidate_course_ids: list[int] = field(default_factory=list)
    confidence: float = 1.0
    reason: str = ""
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "focus_course_id": self.focus_course_id,
            "candidate_course_ids": self.candidate_course_ids,
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
            "needs_clarification": self.needs_clarification,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Lightweight cue lexicons (kept small + obvious; the LLM handles edge cases)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Words that imply the user is referring to a previously-anchored course.
_DEICTIC_PATTERNS = (
    r"\bcái này\b", r"\bvấn đề này\b", r"\bchủ đề này\b",
    r"\bbài này\b", r"\bchương này\b", r"\bkhoá này\b", r"\bkhóa này\b",
    r"\bmôn này\b", r"\bthis (course|topic|lesson|chapter|quiz|one)\b",
    r"\bthat (course|topic|lesson|chapter|quiz|one)\b",
    r"\bở đây\b",
)
_DEICTIC_RE = re.compile("|".join(_DEICTIC_PATTERNS), re.IGNORECASE)

# Words that signal the user wants action ACROSS all their courses.
_GLOBAL_PATTERNS = (
    r"\btất cả (các )?khoá học\b", r"\btất cả (các )?khóa học\b",
    r"\bmọi (khoá|khóa) học\b",
    r"\bcross[- ]course\b", r"\ball (my )?courses\b", r"\bevery course\b",
    r"\boverall\b", r"\btoàn bộ\b",
)
_GLOBAL_RE = re.compile("|".join(_GLOBAL_PATTERNS), re.IGNORECASE)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def resolve_course_scope(
    user_message: str,
    active_courses: dict,
    mtm_ctx: Optional[dict] = None,
    explicit_course_id: Optional[int] = None,
) -> CourseScope:
    """
    Decide which course(s) the current message applies to.

    Order of decisions (most cheap → least cheap):
        0. No active courses → mode="none".
        1. Only one active course → mode="single" auto-resolve.
        2. Explicit "across all courses" cue → mode="all".
        3. Explicit course_id from the FE that matches an active course → "single".
        4. Deictic reference + MTM anchor present → "single" (reuse anchor).
        5. Exactly one course title substring-matches the message → "single".
        6. LLM extraction fallback.
        7. Otherwise → "ambiguous" with a grounded clarification question.

    The resolver NEVER raises — failures degrade to "ambiguous".
    """
    courses = (active_courses or {}).get("courses") or []
    msg = (user_message or "").strip()

    # Step 0 — user has no active courses.
    if not courses:
        return CourseScope(
            mode="none",
            confidence=1.0,
            reason="user has no active courses",
        )

    # Step 1 — only one course → easy.
    if len(courses) == 1:
        c = courses[0]
        return CourseScope(
            mode="single",
            focus_course_id=c.get("id"),
            confidence=1.0,
            reason="user has exactly one active course",
        )

    msg_lower = msg.lower()

    # Step 2 — global keyword wins.
    if _GLOBAL_RE.search(msg_lower):
        ids = [c.get("id") for c in courses if c.get("id") is not None]
        return CourseScope(
            mode="all",
            candidate_course_ids=ids,
            confidence=0.9,
            reason="message references all/multiple courses explicitly",
        )

    # Step 3 — FE-provided course_id is the strongest anchor IF it matches.
    if explicit_course_id is not None:
        if any(c.get("id") == explicit_course_id for c in courses):
            return CourseScope(
                mode="single",
                focus_course_id=explicit_course_id,
                confidence=0.95,
                reason="explicit course_id from frontend",
            )
        # Else: FE sent a course the user has no access to — ignore it.

    # Step 4 — deictic reference + MTM anchor → reuse last-focused course.
    anchor_id = _read_anchor_course_id(mtm_ctx)
    if _DEICTIC_RE.search(msg) and anchor_id is not None:
        if any(c.get("id") == anchor_id for c in courses):
            return CourseScope(
                mode="single",
                focus_course_id=anchor_id,
                confidence=0.85,
                reason="deictic reference resolved against MTM anchor",
            )

    # Step 5 — exact substring match against course titles.
    matched = find_course_by_title(active_courses, msg, min_len=3)
    if matched is not None:
        return CourseScope(
            mode="single",
            focus_course_id=matched.get("id"),
            confidence=0.85,
            reason=f"course title substring match: {matched.get('title')!r}",
        )

    # Step 6 — LLM fallback for entity extraction.
    try:
        llm_scope = await _llm_extract_scope(
            user_message=msg,
            courses=courses,
            anchor_id=anchor_id,
        )
        if llm_scope is not None:
            return llm_scope
    except Exception as exc:  # noqa: BLE001 — never break the turn
        logger.warning("scope LLM extract failed: %s", exc)

    # Step 7 — genuinely ambiguous → ask the user, with grounded options.
    titles = list_course_titles(active_courses)
    options = [
        {"label": titles[i], "value": str(c.get("id"))}
        for i, c in enumerate(courses)
        if c.get("id") is not None
    ]
    return CourseScope(
        mode="ambiguous",
        candidate_course_ids=[c.get("id") for c in courses if c.get("id")],
        confidence=0.4,
        reason="multi-course user, message did not name a specific course",
        needs_clarification=True,
        clarification_question=_default_scope_question(active_courses),
        clarification_options=options,
    )


def apply_scope_to_course_id(
    scope: CourseScope,
    fallback_course_id: Optional[int] = None,
) -> Optional[int]:
    """
    Translate a `CourseScope` into the concrete `course_id` we pass into
    tools and into the system_memory retrieval slot.

    "single" → the focused course.
    "all" / "multi" / "none" / "ambiguous" → None (cross-course / unscoped).
    Falls back to the caller's hint only if the scope didn't pin anything.
    """
    if scope.mode == "single" and scope.focus_course_id is not None:
        return scope.focus_course_id
    return fallback_course_id


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Internals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _read_anchor_course_id(mtm_ctx: Optional[dict]) -> Optional[int]:
    if not mtm_ctx:
        return None
    facts = mtm_ctx.get("key_facts") if isinstance(mtm_ctx, dict) else None
    if not isinstance(facts, dict):
        return None
    val = facts.get("current_course_id")
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _default_scope_question(active_courses: dict) -> str:
    n = len(active_courses.get("courses") or [])
    if (active_courses.get("agent_type") or "") == "teacher":
        return (
            f"Bạn muốn tôi làm việc với khoá học nào trong {n} khoá bạn "
            "đang dạy?"
        )
    return (
        f"Bạn muốn tôi tập trung vào khoá học nào trong {n} khoá bạn đang "
        "học?"
    )


_LLM_PROMPT = """\
You are a scope extractor. The user is talking to an agent that manages \
MANY courses for them. Your job: figure out which course(s) the user \
means in this single message.

The user's active courses (these are the ONLY valid course_ids):
{course_list}

Currently focused course_id from prior turns (may be null): {anchor}

Rules:
- Reply with STRICT JSON only. No prose.
- "matched_course_ids" must be a subset of the active course_ids above.
  Never invent an id.
- Use "wants_all" = true ONLY if the user explicitly asks for cross-course \
  / "all my courses" behaviour.
- Use "references_anchor" = true if the user uses deictic words \
  (this/that/cái này/khoá này) AND the anchor is set.
- Set confidence between 0.0 and 1.0.

Output schema:
{{
  "matched_course_ids": [int, ...],
  "references_anchor": true|false,
  "wants_all": true|false,
  "confidence": 0.0-1.0,
  "reason": "short string"
}}
"""


async def _llm_extract_scope(
    user_message: str,
    courses: list[dict],
    anchor_id: Optional[int],
) -> Optional[CourseScope]:
    """
    Ask the fast model to map the user's message to one or more course_ids.
    Returns None when the model gives no usable signal (caller falls back
    to "ambiguous").
    """
    course_list = "\n".join(
        f"  - id={c.get('id')} \"{c.get('title', '')}\""
        for c in courses if c.get("id") is not None
    )
    prompt = _LLM_PROMPT.format(
        course_list=course_list or "  (none)",
        anchor=anchor_id if anchor_id is not None else "null",
    )

    raw = await chat_complete_json(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message[:500]},
        ],
        model=settings.chat_model,
        temperature=0.0,
        max_tokens=200,
        task=TASK_AGENT_ROUTER,
    )
    if not isinstance(raw, dict):
        return None

    valid_ids = {c.get("id") for c in courses if c.get("id") is not None}
    matched_raw = raw.get("matched_course_ids") or []
    matched: list[int] = []
    if isinstance(matched_raw, list):
        for v in matched_raw:
            try:
                iv = int(v)
            except (TypeError, ValueError):
                continue
            if iv in valid_ids:
                matched.append(iv)

    references_anchor = bool(raw.get("references_anchor"))
    wants_all = bool(raw.get("wants_all"))
    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    reason = str(raw.get("reason") or "llm extraction")

    # Resolve.
    if wants_all:
        return CourseScope(
            mode="all",
            candidate_course_ids=sorted(valid_ids),
            confidence=max(confidence, 0.7),
            reason=f"LLM: {reason}",
        )

    if references_anchor and anchor_id is not None and anchor_id in valid_ids:
        return CourseScope(
            mode="single",
            focus_course_id=anchor_id,
            confidence=max(confidence, 0.7),
            reason=f"LLM(anchor): {reason}",
        )

    if len(matched) == 1:
        return CourseScope(
            mode="single",
            focus_course_id=matched[0],
            confidence=max(confidence, 0.7),
            reason=f"LLM(single): {reason}",
        )

    if len(matched) > 1:
        return CourseScope(
            mode="multi",
            candidate_course_ids=matched,
            confidence=confidence,
            reason=f"LLM(multi): {reason}",
            needs_clarification=True,
            clarification_question=(
                "Bạn muốn tôi tập trung vào khoá nào trong số này?"
            ),
            clarification_options=[
                {
                    "label": next(
                        (c.get("title") for c in courses
                         if c.get("id") == cid),
                        f"Khoá học #{cid}",
                    ),
                    "value": str(cid),
                }
                for cid in matched
            ],
        )

    # No matches and no anchor reference — let the caller fall through to
    # the default "ambiguous" branch with full course list as options.
    return None