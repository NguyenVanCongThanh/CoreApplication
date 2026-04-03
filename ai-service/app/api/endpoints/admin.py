"""
ai-service/app/api/endpoints/admin.py

Internal admin endpoints (protected by X-AI-Secret header):
  POST /ai/admin/reindex            — trigger bge-m3 migration reindex
  GET  /ai/admin/reindex/status     — progress dashboard
  POST /ai/admin/reindex/cutover    — checklist: is it safe to run Part B SQL?
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_async_conn

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/admin", tags=["Admin — Migration"])


class ReindexRequest(BaseModel):
    course_id: Optional[int] = None   # None = all courses


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/reindex")
async def trigger_reindex(body: ReindexRequest, request: Request):
    """
    Enqueue bge-m3 re-embedding jobs for all (or one course's) content items.
    Safe to call multiple times — already-queued jobs are skipped.

    Typical usage:
      1. Deploy new ai-service with bge-m3 (runs Part A migration SQL).
      2. Call this endpoint once.
      3. Monitor GET /ai/admin/reindex/status until pct_done = 100.
      4. Run Part B SQL in DB maintenance window.
    """
    _verify(request)
    from app.services.reindex_service import reindex_service
    result = await reindex_service.enqueue_all(course_id=body.course_id)
    return result


@router.get("/reindex/status")
async def reindex_status(request: Request):
    """
    Returns aggregate progress from v_reindex_progress view.
    Poll every 30s during migration.
    """
    _verify(request)
    from app.services.reindex_service import reindex_service
    progress = await reindex_service.get_progress()

    # Also report failed jobs for investigation
    async with get_async_conn() as conn:
        failed = await conn.fetch(
            """
            SELECT content_id, error_message, updated_at
            FROM embedding_reindex_jobs
            WHERE status = 'failed'
            ORDER BY updated_at DESC
            LIMIT 20
            """
        )

    return {
        **progress,
        "failed_jobs": [dict(r) for r in failed],
        "ready_for_cutover": (
            progress.get("pending", -1) == 0
            and progress.get("processing", -1) == 0
            and progress.get("failed", -1) == 0
            and progress.get("total_jobs", 0) > 0
        ),
    }


@router.post("/reindex/cutover-check")
async def cutover_check(request: Request):
    """
    Pre-flight checks before running Part B SQL (column swap).
    Returns a checklist — all items must be True before proceeding.
    """
    _verify(request)

    async with get_async_conn() as conn:
        # 1. Any chunks still missing embedding_v2?
        pending_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM document_chunks WHERE embedding_v2 IS NULL"
        )
        # 2. Any active Celery reindex jobs?
        active_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM embedding_reindex_jobs WHERE status IN ('pending','processing')"
        )
        # 3. Column exists?
        col_row = await conn.fetchrow(
            """SELECT COUNT(*) AS cnt FROM information_schema.columns
               WHERE table_name='document_chunks' AND column_name='embedding_v2'"""
        )
        # 4. HNSW index on shadow column?
        idx_row = await conn.fetchrow(
            """SELECT COUNT(*) AS cnt FROM pg_indexes
               WHERE tablename='document_chunks'
               AND indexname='idx_chunks_embedding_v2_hnsw'"""
        )

    pending_chunks = int(pending_row["cnt"])
    active_jobs    = int(active_row["cnt"])
    col_exists     = int(col_row["cnt"]) > 0
    idx_exists     = int(idx_row["cnt"]) > 0

    checks = {
        "shadow_column_exists":          col_exists,
        "hnsw_index_on_shadow_built":    idx_exists,
        "no_pending_reindex_jobs":       active_jobs == 0,
        "no_chunks_missing_embedding_v2": pending_chunks == 0,
    }
    all_ok = all(checks.values())

    return {
        "ready_for_cutover": all_ok,
        "checks": checks,
        "pending_chunks_without_v2": pending_chunks,
        "active_reindex_jobs": active_jobs,
        "next_step": (
            "Run the Part B SQL block in lms-service/migrations/005_bge_m3_migration.sql"
            if all_ok
            else "Fix the failing checks above before running Part B."
        ),
    }


# ── Auth ──────────────────────────────────────────────────────────────────────
def _verify(request: Request):
    secret = request.headers.get("X-AI-Secret", "")
    if secret != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")