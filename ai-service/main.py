from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import get_settings
from app.core.database import (
    init_ai_pool,  close_ai_pool,
)
from app.api.endpoints.process    import router as process_router
from app.api.endpoints.diagnose   import router as diagnose_router, nodes_router
from app.api.endpoints.quiz_gen   import router as quiz_router, sr_router
from app.api.endpoints.flashcards import router as flashcards_router
from app.api.endpoints.auto_index import router as auto_index_router, graph_router
from app.api.endpoints.admin      import router as admin_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="BDC AI Service",
    description=(
        "AI engine for LMS — Phase 1 (Error Diagnosis & Deep Linking) "
        "and Phase 2 (Smart Quiz & Spaced Repetition). "
        "Internal microservice — not exposed to public internet."
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=ORJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://lms-backend:8081", "http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    logger.info("Starting AI Service v2.1.0 ...")

    await asyncio.gather(init_ai_pool())
    logger.info("AI pool ready.")

    # 2. Qdrant collections (idempotent — safe to call on every restart)
    if settings.use_qdrant:
        try:
            from app.services.qdrant_service import qdrant_service
            await qdrant_service.init_collections()
            logger.info("Qdrant collections initialised.")
        except Exception as exc:
            # Non-fatal: service can still start; Qdrant may be warming up.
            # Writes will fail until Qdrant is healthy, but reads from PG fallback work.
            logger.error("Qdrant init failed (non-fatal): %s", exc)
    else:
        logger.info("USE_QDRANT=false — using pgvector backend.")

    # 3. Neo4j Knowledge Graph
    if settings.neo4j_enabled:
        try:
            from app.services.neo4j_service import neo4j_service
            await neo4j_service.init()
            logger.info("Neo4j knowledge graph ready.")
        except Exception as exc:
            logger.error("Neo4j init failed (non-fatal): %s", exc)

    # 3. ML model warm-up (background thread, non-blocking)
    loop = asyncio.get_event_loop()

    def _init_models():
        import subprocess, sys
        subprocess.run(
            [sys.executable, "/app/scripts/download_models.py"],
            check=True,
        )
        from app.core.embeddings import warm_up_models
        warm_up_models()

    loop.run_in_executor(None, _init_models)
    logger.info("Model warm-up queued (background thread).")


@app.on_event("shutdown")
async def shutdown():
    if settings.use_qdrant:
        try:
            from app.services.qdrant_service import qdrant_service
            await qdrant_service.close()
        except Exception:
            pass
    if settings.neo4j_enabled:
        try:
            from app.services.neo4j_service import neo4j_service
            await neo4j_service.close()
        except Exception:
            pass
    await asyncio.gather(close_ai_pool())
    logger.info("AI Service shut down.")


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    status: dict = {
        "status":  "healthy",
        "service": "ai-service",
        "version": "2.1.0",
        "backend": "qdrant" if settings.use_qdrant else "pgvector",
    }
    if settings.use_qdrant:
        from app.services.qdrant_service import qdrant_service
        status["qdrant"] = await qdrant_service.health()
    return status


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(process_router,    prefix="/ai")
app.include_router(diagnose_router,   prefix="/ai")
app.include_router(nodes_router,      prefix="/ai")
app.include_router(quiz_router,       prefix="/ai")
app.include_router(sr_router,         prefix="/ai")
app.include_router(flashcards_router, prefix="/ai")
app.include_router(auto_index_router, prefix="/ai")
app.include_router(graph_router,      prefix="/ai")
app.include_router(admin_router,      prefix="/ai")