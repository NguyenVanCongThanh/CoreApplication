"""
ai-service/app/core/multilingual.py

Cross-lingual retrieval utilities.

Strategy:
  1. Detect query language (VI / EN)
  2. Translate to the other language using fast LLM (cached)
  3. Run TWO parallel semantic searches (original + translated)
  4. Merge ranked results with Reciprocal Rank Fusion (RRF)

This lets a Vietnamese question find English-language document chunks
and vice-versa, without changing the embedding model or DB schema.

Optional upgrade path (see bottom): switch to BAAI/bge-m3 for native
cross-lingual embeddings — eliminates the translation round-trip entirely.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# ── In-memory translation cache ───────────────────────────────────────────────
# Keyed by (target_lang, md5(text)). Never evicted — translations are
# deterministic and the number of unique queries per session is small.
_translation_cache: dict[str, str] = {}

T = TypeVar("T")


# ── Language detection ────────────────────────────────────────────────────────

def detect_query_language(text: str) -> str:
    """
    Returns 'vi' or 'en'.
    Reuses the same heuristic from chunker.py (Vietnamese diacritics ratio).
    """
    from app.services.chunker import detect_language
    return detect_language(text)


# ── Translation agent ─────────────────────────────────────────────────────────

async def translate_query(text: str, target_lang: str) -> str:
    """
    Translate *text* to *target_lang* ('vi' or 'en').

    • Uses llama-3.1-8b-instant (fast, ~100ms) — cheap for short queries.
    • Result is cached so repeated identical queries cost nothing.
    • Falls back to original text on any error (search still works, just mono-lingual).
    """
    text = text.strip()
    if not text:
        return text

    cache_key = f"{target_lang}:{hashlib.md5(text.encode()).hexdigest()}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    if target_lang == "vi":
        prompt = (
            "Dịch đoạn văn sau sang tiếng Việt học thuật, "
            "chỉ trả về bản dịch, không giải thích:\n\n" + text
        )
    else:
        prompt = (
            "Translate the following to academic English. "
            "Return only the translation, no explanation:\n\n" + text
        )

    try:
        from app.core.llm import chat_complete
        from app.core.config import get_settings
        settings = get_settings()

        result = await chat_complete(
            messages=[{"role": "user", "content": prompt}],
            model=settings.chat_model,   # llama-3.1-8b-instant — fast
            temperature=0.05,
            max_tokens=300,
        )
        translated = result.strip()

        # Sanity: if LLM echoed the original or returned empty, skip caching
        if translated and translated.lower() != text.lower():
            _translation_cache[cache_key] = translated
            logger.debug(f"Translated [{target_lang}]: '{text[:60]}' → '{translated[:60]}'")
            return translated

        return text

    except Exception as exc:
        logger.warning(f"translate_query failed (fallback to original): {exc}")
        return text


async def expand_query_bilingual(query: str) -> tuple[str, str]:
    """
    Return (original_query, translated_query).
    Translation runs async; if source == target language or translation
    is identical, translated == original (no extra search penalty).
    """
    src_lang = detect_query_language(query)
    tgt_lang = "en" if src_lang == "vi" else "vi"
    translated = await translate_query(query, tgt_lang)
    return query, translated


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    result_lists: list[list[T]],
    id_fn: Callable[[T], Any],
    k: int = 60,
) -> list[T]:
    """
    Merge multiple ranked lists into a single ranking using RRF.

        RRF_score(d) = Σ_i  1 / (k + rank_i(d))

    k=60 is the standard constant from the original paper (Cormack 2009).
    Higher k → more weight to lower-ranked items (smoother merge).

    Items that appear in multiple lists get a bonus, which is exactly what
    we want: a chunk relevant in both VI and EN queries is very likely to be
    the best answer.
    """
    scores: dict[Any, float] = {}
    items: dict[Any, T] = {}

    for result_list in result_lists:
        for rank, item in enumerate(result_list):
            item_id = id_fn(item)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)

            # Keep the item version with the highest raw similarity score
            if item_id not in items:
                items[item_id] = item
            else:
                existing = items[item_id]
                if (
                    hasattr(item, "similarity")
                    and hasattr(existing, "similarity")
                    and item.similarity > existing.similarity
                ):
                    items[item_id] = item

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [items[i] for i in sorted_ids]


# ── High-level helper used by RAGService ─────────────────────────────────────

async def multilingual_search(
    search_fn,          # coroutine: (query, **kwargs) -> list[RetrievedChunk]
    query: str,
    top_k: int,
    id_fn: Callable,
    min_similarity: float = 0.25,
    **search_kwargs,
) -> list:
    """
    Generic cross-lingual search wrapper.

    1. Translate query in the background while running original search.
    2. Run translated search only if translation is meaningfully different.
    3. Merge with RRF.

    Args:
        search_fn  : async function (query, top_k, min_similarity, **kwargs) → list
        query      : original user query (any language)
        top_k      : desired number of final results
        id_fn      : function that extracts a unique ID from a result item
        **search_kwargs: extra kwargs forwarded to search_fn (course_id, node_id, …)
    """
    fetch_k = top_k * 2   # fetch more per search so RRF has material to rank

    # Run original query + translation in parallel
    original_query, translated_query = await expand_query_bilingual(query)

    if translated_query.lower() == original_query.lower():
        # Same language or translation failed — plain search
        return await search_fn(
            query=original_query,
            top_k=top_k,
            min_similarity=min_similarity,
            **search_kwargs,
        )

    # Both searches in parallel
    original_results, translated_results = await asyncio.gather(
        search_fn(
            query=original_query,
            top_k=fetch_k,
            min_similarity=min_similarity,
            **search_kwargs,
        ),
        search_fn(
            query=translated_query,
            top_k=fetch_k,
            min_similarity=min_similarity - 0.05,  # slightly relaxed for cross-lingual
            **search_kwargs,
        ),
    )

    logger.debug(
        "Multilingual RAG: original=%d translated=%d | q='%s' → '%s'",
        len(original_results),
        len(translated_results),
        original_query[:50],
        translated_query[:50],
    )

    if not translated_results:
        return original_results[:top_k]

    merged = reciprocal_rank_fusion(
        [original_results, translated_results],
        id_fn=id_fn,
    )
    return merged[:top_k]


# ═════════════════════════════════════════════════════════════════════════════
# OPTIONAL UPGRADE — BGE-M3 Multilingual Embedding
# ═════════════════════════════════════════════════════════════════════════════
#
# Switching the embedding model to BAAI/bge-m3 eliminates the translation
# round-trip entirely: VI and EN text with the same meaning get SIMILAR
# vectors, so a VI query naturally finds EN chunks.
#
# Steps:
#   1. In config.py:
#        embedding_model: str = "BAAI/bge-m3"
#        embedding_dimensions: int = 1024          # was 768
#
#   2. Migrate DB vector column:
#        ALTER TABLE document_chunks
#          ALTER COLUMN embedding TYPE vector(1024)
#          USING NULL;                             -- wipe old embeddings
#        ALTER TABLE knowledge_nodes
#          ALTER COLUMN description_embedding TYPE vector(1024)
#          USING NULL;
#
#   3. Re-index all content with force=True via the auto-index endpoint.
#
#   4. In llm.py, add E5-style prefixes (BGE-M3 also benefits):
#        query_text  = "query: " + text
#        passage_text = "passage: " + text
#      (Update create_embedding / create_embeddings_batch accordingly.)
#
# Until re-indexing is complete, the translation layer in this file
# acts as a bridge that works with the EXISTING 768-dim nomic embeddings.
# ═════════════════════════════════════════════════════════════════════════════