"""
Bootstrap — called once on application startup to guarantee that:
 
  1. The default Groq provider exists (idempotent).
  2. The two legacy models (chat + quiz) are registered with their current
     env-var values so callers that upgrade mid-flight still work.
  3. If GROQ_API_KEY is set, it's migrated into llm_api_keys as alias
     'groq-env' — but only if no key for that provider exists yet.
  4. Default task bindings are created so every known task_code resolves to
     at least one model.
 
This preserves current behaviour for existing deployments while switching
the runtime to the new gateway.
"""
from __future__ import annotations
 
import logging
 
from app.core.config import get_settings
from app.core.llm_gateway.registry import get_registry
from app.core.llm_gateway.types import (
    ALL_TASK_CODES,
    TASK_AGENT_REACT,
    TASK_AGENT_ROUTER,
    TASK_CHAT,
    TASK_CLARIFICATION,
    TASK_DIAGNOSIS,
    TASK_FLASHCARD_GEN,
    TASK_GRAPH_LINK,
    TASK_LANGUAGE_DETECT,
    TASK_MEMORY_COMPRESS,
    TASK_NODE_EXTRACT,
    TASK_QUIZ_GEN,
)
 
logger = logging.getLogger(__name__)
 
 
# These metadata defaults are based on Groq's published specs (Nov 2024).
# They're safe defaults; admins can edit them live from the UI.
_DEFAULT_GROQ_MODELS = [
    {
        "model_name": "llama-3.1-8b-instant",
        "display_name": "Llama 3.1 8B Instant",
        "family": "llama",
        "context_window": 131072,
        "supports_tools": True,
        "default_temperature": 0.3,
        "default_max_tokens": 1024,
        "input_cost_per_1k": 0.00005,
        "output_cost_per_1k": 0.00008,
    },
    {
        "model_name": "llama-3.3-70b-versatile",
        "display_name": "Llama 3.3 70B Versatile",
        "family": "llama",
        "context_window": 131072,
        "supports_tools": True,
        "default_temperature": 0.3,
        "default_max_tokens": 2048,
        "input_cost_per_1k": 0.00059,
        "output_cost_per_1k": 0.00079,
    },
]
 
 
async def bootstrap_llm_registry() -> None:
    settings = get_settings()
    registry = get_registry()
 
    # 1. Provider
    provider = await registry.upsert_provider(
        code="groq",
        display_name="Groq",
        adapter_type="groq",
        base_url=None,
        enabled=True,
    )
 
    # 2. Models — upsert with current env-var names so the task map still works
    chat_env = settings.chat_model
    quiz_env = settings.quiz_model
 
    models_by_name: dict[str, int] = {}
    for spec in _DEFAULT_GROQ_MODELS:
        m = await registry.upsert_model(provider_id=provider.id, **spec)
        models_by_name[m.model_name] = m.id
 
    # Make sure the exact env-var names exist even if they differ from the
    # hard-coded defaults above (operators may pin a specific slug).
    for env_name, default_temp, default_max in (
        (chat_env, 0.3, 1024),
        (quiz_env, 0.3, 2048),
    ):
        if env_name and env_name not in models_by_name:
            m = await registry.upsert_model(
                provider_id=provider.id,
                model_name=env_name,
                display_name=env_name,
                family="llama",
                context_window=131072,
                supports_tools=True,
                default_temperature=default_temp,
                default_max_tokens=default_max,
            )
            models_by_name[m.model_name] = m.id
 
    chat_model_id = models_by_name.get(chat_env) or next(iter(models_by_name.values()))
    quiz_model_id = models_by_name.get(quiz_env) or chat_model_id
 
    # 3. Seed API key from env if pool is empty
    existing_keys = await registry.list_api_keys(provider_id=provider.id)
    if not existing_keys and settings.groq_api_key:
        try:
            await registry.create_api_key(
                provider_id=provider.id,
                alias="groq-env",
                plaintext_key=settings.groq_api_key,
            )
            logger.info("Migrated GROQ_API_KEY from env into llm_api_keys (alias=groq-env)")
        except Exception as exc:
            logger.warning("Could not seed Groq env key: %s", exc)
 
    # 4. Default task bindings. Priority 10 = primary; admins can add more.
    default_bindings: list[tuple[str, int]] = [
        (TASK_CHAT,             chat_model_id),
        (TASK_CLARIFICATION,    chat_model_id),
        (TASK_LANGUAGE_DETECT,  chat_model_id),
        (TASK_NODE_EXTRACT,     chat_model_id),
        (TASK_AGENT_ROUTER,     chat_model_id),
        (TASK_MEMORY_COMPRESS,  chat_model_id),
        (TASK_FLASHCARD_GEN,    chat_model_id),
        (TASK_GRAPH_LINK,       chat_model_id),
        (TASK_DIAGNOSIS,        chat_model_id),
        (TASK_QUIZ_GEN,         quiz_model_id),
        (TASK_AGENT_REACT,      quiz_model_id),
    ]
 
    existing = {(b.task_code, b.model.id) for b in await registry.list_bindings()}
    for task_code, model_id in default_bindings:
        if (task_code, model_id) in existing:
            continue
        # Only seed if the task currently has no bindings at all — never overwrite
        # an admin's choice.
        chain = await registry.list_bindings(task_code)
        if chain:
            continue
        await registry.upsert_binding(
            task_code=task_code,
            model_id=model_id,
            priority=10,
            enabled=True,
            notes="seeded-default",
        )
 
    registry.invalidate()
    warmed: list[str] = []
    for task_code in ALL_TASK_CODES:
        try:
            chain = await registry.get_binding_chain(task_code)
            if chain:
                warmed.append(task_code)
        except Exception as exc:
            logger.warning("Could not warm binding cache for task=%s: %s", task_code, exc)

    logger.info(
        "LLM registry bootstrapped: provider=%s models=%d keys=%d warmed=%s",
        provider.code, len(models_by_name),
        len(existing_keys) + (1 if settings.groq_api_key and not existing_keys else 0),
        warmed,
    )