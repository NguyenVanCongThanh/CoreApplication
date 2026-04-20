"""
ai-service/app/agents/memory/compressor.py

LLM-powered context compression.

When STM exceeds the token threshold, this module summarises the
conversation into a compact JSONB structure for MTM storage.

The compressed output is designed to be injected into the system prompt,
giving the agent continuity across many turns without replaying the
entire conversation.

Uses the fast chat model (llama-3.1-8b-instant) for low latency.
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.llm import chat_complete_json

logger = logging.getLogger(__name__)
settings = get_settings()

COMPRESS_SYSTEM_PROMPT = """\
You are a conversation compressor for an AI teaching/mentoring system.
Your job is to extract ONLY valuable long-term information from a conversation.

RULES:
1. KEEP: decisions made, content IDs created, knowledge gaps found, \
   pending tasks, student progress data, key preferences.
2. DISCARD: greetings, confirmations, repeated information, \
   temporary debugging info, chitchat.
3. Output MUST be valid JSON matching the schema below.
4. Keep the output compact — under 300 tokens.
5. If the conversation is in Vietnamese, keep the output in Vietnamese.

Output JSON schema:
{
    "decisions_made": ["string"],
    "content_created": ["string — include IDs if available"],
    "identified_gaps": ["concept names the student is weak at"],
    "student_progress": {
        "avg_mastery": 0.0,
        "recent_scores": [],
        "notes": "string"
    },
    "pending_actions": ["things not yet completed"],
    "key_facts": {"key": "value — important preferences or context"}
}

If a field has no data, use an empty array [] or empty object {}.
"""


async def compress_conversation(
    messages: list[dict],
    agent_type: str,
    existing_ctx: dict | None = None,
) -> dict:
    """
    Compress a conversation history into a compact JSONB summary.

    Args:
        messages: List of messages in OpenAI format from STM.
        agent_type: "teacher" or "mentor" — affects what to prioritise.
        existing_ctx: Previous compressed context to merge with.

    Returns:
        Compressed context dict matching the schema above.
    """
    # Build conversation text (skip system messages)
    conversation_lines = []
    for m in messages:
        role = m.get("role", "unknown").upper()
        content = m.get("content", "")
        if role == "SYSTEM" or not content:
            continue
        # Truncate very long tool results
        if role == "TOOL" and len(content) > 500:
            content = content[:500] + "... [truncated]"
        conversation_lines.append(f"{role}: {content}")

    conversation_text = "\n".join(conversation_lines)

    if not conversation_text.strip():
        return existing_ctx or {}

    # Add context about what to prioritise
    agent_hint = (
        "Focus on: content created, quiz IDs, course decisions."
        if agent_type == "teacher"
        else "Focus on: student knowledge gaps, mastery levels, study progress."
    )

    # Include existing context for merging
    existing_section = ""
    if existing_ctx and any(existing_ctx.values()):
        import json
        existing_section = (
            f"\n\nEXISTING CONTEXT (merge new info into this):\n"
            f"{json.dumps(existing_ctx, ensure_ascii=False, indent=2)}"
        )

    user_prompt = (
        f"Agent type: {agent_type}\n"
        f"{agent_hint}\n"
        f"{existing_section}\n\n"
        f"CONVERSATION TO COMPRESS:\n{conversation_text}"
    )

    try:
        result = await chat_complete_json(
            messages=[
                {"role": "system", "content": COMPRESS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=settings.chat_model,  # fast model for compression
            temperature=0.1,
            max_tokens=512,
        )

        # Validate structure
        if not isinstance(result, dict):
            logger.warning("Compressor returned non-dict: %s", type(result))
            return existing_ctx or {}

        # Ensure all expected keys exist
        defaults = {
            "decisions_made": [],
            "content_created": [],
            "identified_gaps": [],
            "student_progress": {},
            "pending_actions": [],
            "key_facts": {},
        }
        for key, default in defaults.items():
            if key not in result:
                result[key] = default

        logger.info(
            "Conversation compressed: gaps=%d, actions=%d, facts=%d",
            len(result.get("identified_gaps", [])),
            len(result.get("pending_actions", [])),
            len(result.get("key_facts", {})),
        )
        return result

    except Exception as exc:
        logger.error("Context compression failed: %s", exc)
        return existing_ctx or {}
