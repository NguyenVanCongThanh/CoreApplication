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
   inferred → respond with {{"needs_clarification": false}}
2. If critical information is MISSING → respond with a clarification question
3. Do NOT ask for clarification on optional parameters
4. Do NOT ask for clarification on greetings, thank-yous, or general chat
5. Keep clarification questions SHORT and offer options when possible
6. Respond in the SAME LANGUAGE as the user's message

Output JSON:
{{
    "needs_clarification": true/false,
    "confidence": 0.0-1.0,
    "clarification_question": "string (only if needs_clarification=true)",
    "clarification_options": ["option1", "option2"],
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
        desc = func.get("description", "")[:80]
        params = func.get("parameters", {})
        required = params.get("required", [])
        tool_lines.append(f"  - {name}: {desc} (required: {', '.join(required)})")

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
        if needs and confidence < 0.7:
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
                "clarification_options": result.get("clarification_options", []),
                "missing_fields": result.get("missing_fields", []),
            }

        return {"needs_clarification": False, "confidence": confidence}

    except Exception as exc:
        logger.error("Clarification gate failed: %s", exc)
        # On error, don't block — let the ReAct loop handle it
        return {"needs_clarification": False, "confidence": 0.5}
