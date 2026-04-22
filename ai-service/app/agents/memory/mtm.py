"""
ai-service/app/agents/memory/mtm.py

Medium-Term Memory (MTM) — PostgreSQL-backed session context.

Stores compressed conversation summaries in the `agent_sessions` table.
When STM exceeds the token threshold, the compressor produces a JSONB
summary that is merged into the session's `compressed_ctx`.

This lets the agent "remember" key facts across many turns without
re-reading the entire conversation history.

compressed_ctx schema:
    {
        "decisions_made": ["..."],
        "content_created": ["quiz #42", "flashcard set"],
        "identified_gaps": ["Polymorphism", "Recursion"],
        "student_progress": {"avg_mastery": 0.65, "weak_count": 3},
        "pending_actions": ["Review quiz #42 draft"],
        "key_facts": {"preferred_language": "vi", "current_topic": "OOP"}
    }
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core.database import get_ai_conn

logger = logging.getLogger(__name__)


class MTMemory:
    """Medium-Term Memory backed by PostgreSQL agent_sessions table."""

    async def get_or_create_session(
        self,
        user_id: int,
        agent_type: str,
        course_id: Optional[int] = None,
    ) -> dict:
        """
        Get the most recent session for this user+agent, or create a new one.

        Returns:
            {
                "session_id": str (UUID),
                "context": dict (compressed_ctx JSONB),
                "turn_count": int,
            }
        """
        async with get_ai_conn() as conn:
            # Try to find an existing active session
            row = await conn.fetchrow(
                """SELECT id, compressed_ctx, turn_count
                   FROM agent_sessions
                   WHERE user_id = $1
                     AND agent_type = $2
                     AND ($3::BIGINT IS NULL OR course_id = $3)
                   ORDER BY last_active_at DESC
                   LIMIT 1""",
                user_id, agent_type, course_id,
            )

            if row:
                # Touch last_active_at
                await conn.execute(
                    "UPDATE agent_sessions SET last_active_at = NOW() WHERE id = $1",
                    row["id"],
                )
                ctx = row["compressed_ctx"]
                if isinstance(ctx, str):
                    ctx = json.loads(ctx)
                return {
                    "session_id": str(row["id"]),
                    "context": ctx or {},
                    "turn_count": row["turn_count"] or 0,
                }

            # Create new session
            new_row = await conn.fetchrow(
                """INSERT INTO agent_sessions
                       (user_id, agent_type, course_id, compressed_ctx, turn_count, title)
                   VALUES ($1, $2, $3, '{}'::jsonb, 0, NULL)
                   RETURNING id""",
                user_id, agent_type, course_id,
            )
            return {
                "session_id": str(new_row["id"]),
                "context": {},
                "turn_count": 0,
            }

    async def create_new_session(
        self,
        user_id: int,
        agent_type: str,
        course_id: Optional[int] = None,
    ) -> dict:
        """Force create a completely new session."""
        async with get_ai_conn() as conn:
            new_row = await conn.fetchrow(
                """INSERT INTO agent_sessions
                       (user_id, agent_type, course_id, compressed_ctx, turn_count, title)
                   VALUES ($1, $2, $3, '{}'::jsonb, 0, NULL)
                   RETURNING id""",
                user_id, agent_type, course_id,
            )
            return {
                "session_id": str(new_row["id"]),
                "context": {},
                "turn_count": 0,
            }

    async def get_context(self, session_id: str) -> dict:
        """Get the compressed context for a session."""
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                "SELECT compressed_ctx FROM agent_sessions WHERE id = $1",
                session_id,
            )
            if not row:
                return {}
            ctx = row["compressed_ctx"]
            if isinstance(ctx, str):
                ctx = json.loads(ctx)
            return ctx or {}

    async def save_compressed(
        self,
        session_id: str,
        compressed_ctx: dict,
        turn_count: int,
    ) -> None:
        """
        Update the session with new compressed context.

        Called after the compressor runs. Merges new context with existing
        (the compressor's output replaces the old context).
        """
        async with get_ai_conn() as conn:
            await conn.execute(
                """UPDATE agent_sessions
                   SET compressed_ctx = $1::jsonb,
                       turn_count = $2,
                       last_active_at = NOW()
                   WHERE id = $3""",
                json.dumps(compressed_ctx, ensure_ascii=False),
                turn_count,
                session_id,
            )
        logger.debug(
            "MTM updated: session=%s, turn_count=%d, keys=%s",
            session_id, turn_count, list(compressed_ctx.keys()),
        )

    async def increment_turn_count(self, session_id: str) -> int:
        """Increment and return the new turn count."""
        async with get_ai_conn() as conn:
            row = await conn.fetchrow(
                """UPDATE agent_sessions
                   SET turn_count = turn_count + 1,
                       last_active_at = NOW()
                   WHERE id = $1
                   RETURNING turn_count""",
                session_id,
            )
            return row["turn_count"] if row else 0

    async def update_title(self, session_id: str, title: str) -> None:
        """Set the AI-generated title for a session."""
        async with get_ai_conn() as conn:
            await conn.execute(
                "UPDATE agent_sessions SET title = $1 WHERE id = $2",
                title, session_id
            )

    async def list_sessions(
        self,
        user_id: int,
        agent_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """List recent sessions for a user (for session history UI)."""
        async with get_ai_conn() as conn:
            if agent_type:
                rows = await conn.fetch(
                    """SELECT id, agent_type, course_id, turn_count,
                              last_active_at, created_at, title
                       FROM agent_sessions
                       WHERE user_id = $1 AND agent_type = $2
                       ORDER BY last_active_at DESC
                       LIMIT $3""",
                    user_id, agent_type, limit,
                )
            else:
                rows = await conn.fetch(
                    """SELECT id, agent_type, course_id, turn_count,
                              last_active_at, created_at, title
                       FROM agent_sessions
                       WHERE user_id = $1
                       ORDER BY last_active_at DESC
                       LIMIT $2""",
                    user_id, limit,
                )
            return [
                {
                    "session_id": str(r["id"]),
                    "title": r["title"],
                    "agent_type": r["agent_type"],
                    "course_id": r["course_id"],
                    "turn_count": r["turn_count"],
                    "last_active_at": r["last_active_at"].isoformat()
                        if r["last_active_at"] else None,
                    "created_at": r["created_at"].isoformat()
                        if r["created_at"] else None,
                }
                for r in rows
            ]


# Singleton
mtm = MTMemory()
