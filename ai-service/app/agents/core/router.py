"""
ai-service/app/agents/core/router.py

Intent Router — lightweight intent classifier for memory weighting.

Classifies user messages into intent types using a fast LLM call.
The classified intent is passed to ContextBuilder to determine
which memory tiers to query (and at what weight).

Intent types:
  - knowledge_question   : Asking about a concept, how something works
  - progress_advice      : Asking about scores, progress, recommendations
  - content_creation     : Asking to create quizzes, content, slides
  - interactive_exercise : Asking for practice, exercises, challenges
  - general_chat         : Greetings, chitchat, meta-questions

Uses the fast model (llama-3.1-8b-instant) for sub-200ms latency.
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.llm import chat_complete
from app.core.llm_gateway import TASK_AGENT_ROUTER

logger = logging.getLogger(__name__)
settings = get_settings()

VALID_INTENTS = {
    "knowledge_question",
    "progress_advice",
    "content_creation",
    "interactive_exercise",
    "general_chat",
}

ROUTER_PROMPT = """\
Classify the user message into exactly ONE intent type. Reply with ONLY \
the intent name, nothing else.

Intent types:
- knowledge_question: Asking about a concept (what, how, why, explain)
- progress_advice: Asking about scores, progress, study advice, grades
- content_creation: Asking to create/generate quizzes, content, slides, assessments
- interactive_exercise: Asking for practice, exercises, flashcards, mini-tests
- general_chat: Greetings, thank you, unclear/ambiguous messages

Examples:
User: "Đa hình là gì?" → knowledge_question
User: "Tôi học bài nào tiếp?" → progress_advice
User: "Tạo 5 câu hỏi trắc nghiệm" → content_creation
User: "Cho tôi 1 bài tập nhỏ" → interactive_exercise
User: "Xin chào" → general_chat
User: "What is polymorphism in OOP?" → knowledge_question
User: "My scores are bad, what should I do?" → progress_advice

User message:
"""


async def classify_intent(
    user_message: str,
    agent_type: str = "mentor",
) -> str:
    """
    Classify the user's message into an intent type.

    Returns one of the VALID_INTENTS strings.
    Falls back to "general_chat" on error.
    """
    try:
        # Short messages and greetings → skip LLM call
        stripped = user_message.strip().lower()
        if len(stripped) < 5 or stripped in (
            "hi", "hello", "hey", "xin chào", "chào",
            "thanks", "cảm ơn", "ok", "bye",
        ):
            return "general_chat"

        result = await chat_complete(
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": user_message[:300]},
            ],
            model=settings.chat_model,  # fast model
            temperature=0.0,
            max_tokens=20,
            task=TASK_AGENT_ROUTER,
        )

        intent = result.strip().lower().replace(" ", "_")

        # Handle partial matches
        for valid in VALID_INTENTS:
            if valid in intent:
                logger.debug("Intent classified: '%s' → %s", user_message[:50], valid)
                return valid

        # Fallback
        logger.warning(
            "Unknown intent '%s' for message '%s', defaulting to general_chat",
            intent, user_message[:50],
        )
        return "general_chat"

    except Exception as exc:
        logger.error("Intent classification failed: %s", exc)
        return "general_chat"
