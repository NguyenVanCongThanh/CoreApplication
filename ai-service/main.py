"""
ai-service/main.py
FastAPI application entry point.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_async_pool, close_async_pool
from app.api.endpoints.process import router as process_router
from app.api.endpoints.diagnose import router as diagnose_router, nodes_router
from app.api.endpoints.quiz_gen import router as quiz_router, sr_router

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
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://lms-backend:8081", "http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    logger.info("Starting AI Service...")
    await init_async_pool()
    logger.info("Database pool initialized.")
    
    logger.info("Pre-loading embedding model (may take a few minutes on first run)...")
    try:
        from app.core.llm import get_embed_model
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, get_embed_model)
        logger.info("Embedding model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to pre-load embedding model: {e}")

@app.on_event("shutdown")
async def shutdown():
    await close_async_pool()
    logger.info("AI Service shut down.")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "service": "ai-service", "version": "1.0.0"}


# ── Routers (all under /ai prefix) ───────────────────────────────────────────

app.include_router(process_router, prefix="/ai")
app.include_router(diagnose_router, prefix="/ai")
app.include_router(nodes_router, prefix="/ai")
app.include_router(quiz_router, prefix="/ai")
app.include_router(sr_router, prefix="/ai")
