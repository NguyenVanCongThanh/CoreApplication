"""
ai-service/app/core/database.py
Async PostgreSQL connection pool (asyncpg).
Sync pool for Celery workers that run in separate threads.
"""
from __future__ import annotations

import asyncpg
import psycopg2
import psycopg2.extras
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from app.core.config import get_settings

settings = get_settings()

# ── Async pool (FastAPI endpoints) ───────────────────────────────────────────
_async_pool: asyncpg.Pool | None = None


async def init_async_pool() -> None:
    global _async_pool
    _async_pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        min_size=settings.db_min_connections,
        max_size=settings.db_max_connections,
    )


async def close_async_pool() -> None:
    global _async_pool
    if _async_pool:
        await _async_pool.close()
        _async_pool = None


@asynccontextmanager
async def get_async_conn() -> AsyncIterator[asyncpg.Connection]:
    """Async context manager — use inside FastAPI endpoints."""
    assert _async_pool is not None, "Async pool not initialized"
    async with _async_pool.acquire() as conn:
        yield conn


# ── Sync pool (Celery workers) ────────────────────────────────────────────────
@contextmanager
def get_sync_conn() -> Iterator[psycopg2.extensions.connection]:
    """Sync context manager — use inside Celery tasks."""
    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        dbname=settings.db_name,
    )
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_sync_cursor(conn):
    """Returns a DictCursor for convenient row access by column name."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)