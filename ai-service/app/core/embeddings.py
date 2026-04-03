from __future__ import annotations

import asyncio
import logging
import os
from typing import TypeVar

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embed_model = None
_reranker_model = None
T = TypeVar("T")

_CACHE_DIR = os.getenv("SENTENCE_TRANSFORMERS_HOME", "/app/.cache/models")


# Loaders 

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _embed_model = SentenceTransformer(
            settings.embedding_model,
            cache_folder=_CACHE_DIR,
        )
        logger.info("Embedding model ready.")
    return _embed_model


def get_reranker():
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers.cross_encoder import CrossEncoder
            logger.info(f"Loading reranker: {settings.reranker_model}")
            _reranker_model = CrossEncoder(
                settings.reranker_model,
                cache_dir=_CACHE_DIR,
            )
            logger.info("Reranker ready.")
        except Exception as exc:
            logger.warning(f"Reranker load failed ({exc}). Reranking disabled.")
            _reranker_model = None
    return _reranker_model


def warm_up_models() -> None:
    """Gọi 1 lần khi startup trong background thread."""
    get_embed_model()
    if settings.use_reranker:
        get_reranker()
    logger.info("All models warm.")


# Prefix helper 

def _apply_prefix(text: str, role: str) -> str:
    """BGE convention: 'query: ...' khi search, 'passage: ...' khi index."""
    mode = getattr(settings, "embedding_prefix_mode", "none")
    if mode in ("bge", "e5"):
        return f"{role}: {text}"
    return text


# Sync embedding (chạy trong thread pool, không block event loop) 

def _embed_sync(texts: list[str]) -> list[list[float]]:
    model = get_embed_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]


async def _run_in_thread(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)


# Public API 

async def create_embedding(text: str) -> list[float]:
    clean = _apply_prefix(text.replace("\n", " ").strip() or " ", "query")
    result = await _run_in_thread(_embed_sync, [clean])
    return result[0]


async def create_passage_embedding(text: str) -> list[float]:
    clean = _apply_prefix(text.replace("\n", " ").strip() or " ", "passage")
    result = await _run_in_thread(_embed_sync, [clean])
    return result[0]


async def create_embeddings_batch(texts: list[str]) -> list[list[float]]:
    cleaned = [_apply_prefix(t.replace("\n", " ").strip() or " ", "query") for t in texts]
    return await _run_in_thread(_embed_sync, cleaned)


async def create_passage_embeddings_batch(texts: list[str]) -> list[list[float]]:
    cleaned = [_apply_prefix(t.replace("\n", " ").strip() or " ", "passage") for t in texts]
    return await _run_in_thread(_embed_sync, cleaned)


# Reranking 

def _rerank_sync(query: str, passages: list[str]) -> list[float]:
    reranker = get_reranker()
    if reranker is None:
        return [0.0] * len(passages)
    try:
        pairs = [(query, p) for p in passages]
        scores = reranker.predict(pairs, show_progress_bar=False)
        return [float(s) for s in scores]
    except Exception as exc:
        logger.warning(f"Reranking failed ({exc}), using original order.")
        return [0.0] * len(passages)


async def rerank_chunks(
    query: str,
    chunks: list[T],
    text_fn,
    top_k: int,
) -> list[T]:
    if not chunks:
        return chunks
    if not settings.use_reranker or get_reranker() is None:
        return chunks[:top_k]
    passages = [text_fn(c) for c in chunks]
    scores = await _run_in_thread(_rerank_sync, query, passages)
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:top_k]]