"""
ai-service/app/agents/core/clarification.py

Clarification Gate — prevents hallucination on ambiguous requests.

When a user asks for an action (e.g., "create quiz") but critical
parameters are missing or ambiguous, the Clarification Gate intercepts
BEFORE the ReAct loop enters tool execution.

The gate uses a fast LLM call to:
  1. Check if the request has enough information to execute
  2. If not, generate a targeted clarification question
  3. Suggest options when possible (e.g., list of topics)

At most 2 clarifications per session to prevent annoying loops.
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.llm import chat_complete_json

logger = logging.getLogger(__name__)
settings = get_settings()


CLARIFICATION_PROMPT = """\
You are an intent validator for an AI agent system. Your job is to decide \
if the user's request has enough information to execute, or if the agent \
needs to ask a clarifying question BEFORE acting.

Available tools (summary):
{tool_summary}

Current session context:
{session_context}

RULES:
1. If the user's intent is CLEAR and all required parameters can be \
   inferred → respond with {{"needs_clarification": false, "confidence": 0.9}}
2. If the missing info can be OBTAINED BY CALLING A TOOL (e.g. the agent \
   can call `list_knowledge_nodes`, `list_my_courses`, \
   `search_course_materials` to discover the list of topics / courses / \
   concepts) → respond with {{"needs_clarification": false, \
   "confidence": 0.9}}. Do NOT clarify in this case — let the agent fetch \
   the real data via tools, then ask the user using that real data.
3. Only ask for clarification when the missing info is something ONLY THE \
   USER can provide (e.g. desired difficulty, number of questions, their \
   preference) AND you cannot infer it from context.
4. Do NOT ask for clarification on optional parameters.
5. Do NOT ask for clarification on greetings, thank-yous, or general chat.
6. Respond in the SAME LANGUAGE as the user's message.
 
HARD RULES FOR `clarification_options`:
- NEVER invent, guess, or fabricate options. Do NOT list generic subjects \
   (e.g. "Toán, Văn, Anh") unless they are literally present in the \
   session context above.
- ONLY include options that are DIRECTLY and LITERALLY present in the \
   "Current session context" block above.
- If you cannot produce options from the context, return \
   `"clarification_options": []` — the agent will fetch the real list via \
   a tool and ask the user with accurate choices.
- Do not repeat the user's own words back as options.

Output JSON:
{{
    "needs_clarification": true/false,
    "confidence": 0.0-1.0,
    "clarification_question": "string (only if needs_clarification=true)",
    "clarification_options": ["only if verifiable from session context"],
    "missing_fields": ["field_name"],
    "inferred_intent": "intent_name"
}}
"""


async def should_clarify(
    user_message: str,
    tool_schemas: list[dict],
    session_context: dict,
) -> dict:
    """
    Check if the user's message needs clarification before tool execution.

    Args:
        user_message: The user's raw message.
        tool_schemas: Available tool schemas (for the LLM to understand capabilities).
        session_context: Current MTM compressed context.

    Returns:
        Dict with clarification decision:
        {
            "needs_clarification": bool,
            "confidence": float,
            "clarification_question": str,
            "clarification_options": list[str],
            "missing_fields": list[str],
        }
    """
    # Don't clarify simple messages
    stripped = user_message.strip()
    if len(stripped) < 10:
        return {"needs_clarification": False, "confidence": 1.0}

    # Build tool summary (names + required params only)
    tool_lines = []
    for schema in tool_schemas:
        func = schema.get("function", {})
        name = func.get("name", "")
        desc = func.get("description", "")[:200]
        params = func.get("parameters", {})
        required = params.get("required", [])
        tool_lines.append(
            f"  - {name}: {desc} (required: {', '.join(required) or 'none'})"
        )

    tool_summary = "\n".join(tool_lines)

    # Build context summary
    context_str = ""
    if session_context:
        ctx_parts = []
        if session_context.get("key_facts"):
            ctx_parts.append(f"Known facts: {session_context['key_facts']}")
        if session_context.get("identified_gaps"):
            ctx_parts.append(f"Known gaps: {session_context['identified_gaps']}")
        context_str = "; ".join(ctx_parts) if ctx_parts else "No session context"
    else:
        context_str = "New session — no prior context"

    prompt = CLARIFICATION_PROMPT.format(
        tool_summary=tool_summary,
        session_context=context_str,
    )

    try:
        result = await chat_complete_json(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message[:500]},
            ],
            model=settings.chat_model,  # fast model
            temperature=0.1,
            max_tokens=256,
        )

        if not isinstance(result, dict):
            return {"needs_clarification": False, "confidence": 1.0}

        # Validate the response
        needs = result.get("needs_clarification", False)
        confidence = float(result.get("confidence", 1.0))

        # Only clarify if confidence is low
        if needs and confidence < 0.6:
            raw_options = result.get("clarification_options", []) or []
            verified_options = _verify_options(raw_options, session_context)
 
            # If the model offered options but none survived verification,
            # it was almost certainly fabricating. Downgrade to "no clarify"
            # so the agent gets a chance to discover real options via tools
            # instead of showing the user fake buttons.
            if raw_options and not verified_options:
                logger.info(
                    "Clarification suppressed: model fabricated %d options "
                    "(none grounded in context). Letting agent use tools.",
                    len(raw_options),
                )
                return {
                    "needs_clarification": False,
                    "confidence": max(confidence, 0.7),
                }
 
            logger.info(
                "Clarification needed: confidence=%.2f, missing=%s",
                confidence, result.get("missing_fields", []),
            )
            return {
                "needs_clarification": True,
                "confidence": confidence,
                "clarification_question": result.get(
                    "clarification_question", "Bạn có thể nói rõ hơn không?"
                ),
                "clarification_options": verified_options,
                "missing_fields": result.get("missing_fields", []),
            }

        return {"needs_clarification": False, "confidence": confidence}

    except Exception as exc:
        logger.error("Clarification gate failed: %s", exc)
        # On error, don't block — let the ReAct loop handle it
        return {"needs_clarification": False, "confidence": 0.5}

def _verify_options(
    options: list[str],
    session_context: dict,
) -> list[str]:
    """
    Drop clarification options that aren't grounded in the session context.
 
    The fast clarification model tends to fabricate generic option lists
    (e.g. "Toán / Văn / Anh") when it doesn't know the real topics. We
    only keep options whose text actually appears in the MTM context — so
    when there are no grounded options, the frontend shows the question
    without fake choices and the agent is free to fetch real ones via a
    tool call on the next turn.
    """
    if not options:
        return []
 
    # Flatten session context into a searchable blob
    import json as _json
    try:
        blob = _json.dumps(session_context or {}, ensure_ascii=False).lower()
    except Exception:
        blob = str(session_context or "").lower()
 
    kept: list[str] = []
    for opt in options:
        if not isinstance(opt, str):
            continue
        opt_clean = opt.strip()
        if not opt_clean:
            continue
        # Require the option text (or a long enough prefix) to appear in
        # the context. Short tokens are too easy to accidentally match.
        needle = opt_clean.lower()
        if len(needle) >= 3 and needle in blob:
            kept.append(opt_clean)
    return kept
