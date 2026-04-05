from __future__ import annotations

import asyncpg
import psycopg2
import psycopg2.extras
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from app.core.config import get_settings

settings = get_settings()


# ── Async pools (FastAPI) ─────────────────────────────────────────────────────

_lms_pool: asyncpg.Pool | None = None
_ai_pool:  asyncpg.Pool | None = None


async def init_lms_pool() -> None:
    global _lms_pool
    _lms_pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        min_size=settings.db_min_connections,
        max_size=settings.db_max_connections,
    )


async def init_ai_pool() -> None:
    global _ai_pool
    _ai_pool = await asyncpg.create_pool(
        host=settings.ai_db_host,
        port=settings.ai_db_port,
        user=settings.ai_db_user,
        password=settings.ai_db_password,
        database=settings.ai_db_name,
        min_size=settings.ai_db_min_connections,
        max_size=settings.ai_db_max_connections,
    )


async def close_lms_pool() -> None:
    global _lms_pool
    if _lms_pool:
        await _lms_pool.close()
        _lms_pool = None


async def close_ai_pool() -> None:
    global _ai_pool
    if _ai_pool:
        await _ai_pool.close()
        _ai_pool = None


# Public async context managers ────────────────────────────────────────────────

@asynccontextmanager
async def get_lms_conn() -> AsyncIterator[asyncpg.Connection]:
    """Read LMS entities (quiz_questions, section_content, users, …)."""
    assert _lms_pool is not None, "LMS pool not initialised — call init_lms_pool()"
    async with _lms_pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_ai_conn() -> AsyncIterator[asyncpg.Connection]:
    """Read/write AI-domain data (knowledge_nodes, document_chunks, …)."""
    assert _ai_pool is not None, "AI pool not initialised — call init_ai_pool()"
    async with _ai_pool.acquire() as conn:
        yield conn


# Backward-compat alias — existing callers of get_async_conn() that still
# operate on LMS tables (e.g. section_content status writes) keep working.
get_async_conn = get_lms_conn


# ── Sync connections (Celery workers) ─────────────────────────────────────────

def _make_sync_conn(
    host: str, port: int, user: str, password: str, dbname: str
) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname
    )
    conn.autocommit = False
    return conn


@contextmanager
def get_sync_lms_conn() -> Iterator[psycopg2.extensions.connection]:
    """Sync context manager for LMS tables — use in Celery tasks."""
    conn = _make_sync_conn(
        settings.db_host, settings.db_port,
        settings.db_user, settings.db_password, settings.db_name,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_sync_ai_conn() -> Iterator[psycopg2.extensions.connection]:
    """Sync context manager for AI tables — use in Celery tasks."""
    conn = _make_sync_conn(
        settings.ai_db_host, settings.ai_db_port,
        settings.ai_db_user, settings.ai_db_password, settings.ai_db_name,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Backward-compat alias for Celery tasks that still use get_sync_conn().
get_sync_conn = get_sync_lms_conn


def get_sync_cursor(conn: psycopg2.extensions.connection):
    """Returns a DictCursor for convenient column-name access."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)