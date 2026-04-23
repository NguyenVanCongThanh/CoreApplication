"""
ai-service/app/agents/memory/ltm.py

Long-Term Memory (LTM) — Qdrant + PostgreSQL episodic memory.

When a session is compressed (or explicitly ended), an "episode" summary
is created and stored:
  - Vector embedding in Qdrant (collection: agent_episodes)
  - Metadata row in PostgreSQL (agent_episodes table)

Later, the agent can semantically search past episodes to recall
relevant historical context about a user's learning journey.

Collection: agent_episodes
  - Dimensions: 1024 (bge-m3)
  - Distance: Cosine
  - Payload: {user_id, agent_type, session_id, summary, created_at}
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from app.core.config import get_settings
from app.core.database import get_ai_conn

logger = logging.getLogger(__name__)
settings = get_settings()

EPISODE_COLLECTION = "agent_episodes"
EPISODE_VECTOR_SIZE = 1024  # bge-m3


class LTMemory:
    """Long-Term Memory using Qdrant + PostgreSQL."""

    # ── Qdrant collection lifecycle ────────────────────────────────────────────

    async def ensure_collection(self) -> None:
        """Create the agent_episodes Qdrant collection if it doesn't exist."""
        if not settings.use_qdrant:
            logger.info("LTM: Qdrant disabled, skipping collection init")
            return

        from app.services.qdrant_service import qdrant_service
        from qdrant_client.http.models import (
            Distance, VectorParams, HnswConfigDiff,
        )

        client = qdrant_service._get_client()
        exists = await client.collection_exists(EPISODE_COLLECTION)
        if not exists:
            await client.create_collection(
                collection_name=EPISODE_COLLECTION,
                vectors_config=VectorParams(
                    size=EPISODE_VECTOR_SIZE,
                    distance=Distance.COSINE,
                    on_disk=True,
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=5_000,
                    on_disk=False,
                ),
            )
            # Create payload indexes for filtering
            from qdrant_client.http.models import PayloadSchemaType
            await client.create_payload_index(
                EPISODE_COLLECTION, "user_id", PayloadSchemaType.INTEGER,
            )
            await client.create_payload_index(
                EPISODE_COLLECTION, "agent_type", PayloadSchemaType.KEYWORD,
            )
            logger.info("Created Qdrant collection: %s", EPISODE_COLLECTION)
        else:
            logger.debug("Qdrant collection already exists: %s", EPISODE_COLLECTION)

    # ── Store episode ─────────────────────────────────────────────────────────

    async def store_episode(
        self,
        session_id: str,
        user_id: int,
        agent_type: str,
        summary_text: str,
    ) -> Optional[str]:
        """
        Create a new episodic memory entry.

        1. Embed the summary text
        2. Upsert to Qdrant
        3. Save metadata to PostgreSQL

        Returns the episode UUID, or None if storage failed.
        """
        if not summary_text.strip():
            return None

        try:
            from app.core.embeddings import create_passage_embedding

            # 1. Create embedding
            embedding = await create_passage_embedding(summary_text)

            # 2. Generate a positive int64 point ID for Qdrant
            point_id = uuid.uuid4().int >> 64  # positive int64

            # 3. Upsert to Qdrant
            if settings.use_qdrant:
                from app.services.qdrant_service import qdrant_service
                from qdrant_client.http.models import PointStruct

                client = qdrant_service._get_client()
                await client.upsert(
                    collection_name=EPISODE_COLLECTION,
                    points=[PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "user_id": user_id,
                            "agent_type": agent_type,
                            "session_id": session_id,
                            "summary": summary_text,
                            "created_at": int(time.time()),
                        },
                    )],
                    wait=True,
                )

            # 4. Save metadata to PostgreSQL
            async with get_ai_conn() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO agent_episodes
                           (session_id, user_id, agent_type, summary, qdrant_point_id)
                       VALUES ($1, $2, $3, $4, $5)
                       RETURNING id""",
                    session_id, user_id, agent_type, summary_text, point_id,
                )

            episode_id = str(row["id"]) if row else None
            logger.info(
                "LTM episode stored: user=%d, agent=%s, episode=%s, point=%d",
                user_id, agent_type, episode_id, point_id,
            )
            return episode_id

        except Exception as exc:
            logger.error("Failed to store LTM episode: %s", exc)
            return None

    # ── Recall episodes ───────────────────────────────────────────────────────

    async def recall(
        self,
        user_id: int,
        agent_type: str,
        query: str,
        top_k: int = 3,
        min_score: float = 0.40,
    ) -> list[dict]:
        """
        Semantically search past episodes for this user.

        Returns a list of episode summaries sorted by relevance.
        """
        if not settings.use_qdrant:
            # Fallback: return recent episodes from PostgreSQL
            return await self._recall_from_pg(user_id, agent_type, top_k)

        try:
            from app.core.embeddings import create_embedding
            from app.services.qdrant_service import qdrant_service
            from qdrant_client.http.models import (
                Filter, FieldCondition, MatchValue,
            )

            query_vector = await create_embedding(query)
            client = qdrant_service._get_client()

            results = await client.search(
                collection_name=EPISODE_COLLECTION,
                query_vector=query_vector,
                query_filter=Filter(must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id),
                    ),
                    FieldCondition(
                        key="agent_type",
                        match=MatchValue(value=agent_type),
                    ),
                ]),
                limit=top_k,
                score_threshold=min_score,
                with_payload=True,
                with_vectors=False,
            )

            return [
                {
                    "summary": r.payload.get("summary", ""),
                    "session_id": r.payload.get("session_id", ""),
                    "score": round(r.score, 3),
                    "created_at": r.payload.get("created_at", 0),
                }
                for r in results
            ]

        except Exception as exc:
            logger.error("LTM recall failed: %s", exc)
            return await self._recall_from_pg(user_id, agent_type, top_k)

    async def _recall_from_pg(
        self,
        user_id: int,
        agent_type: str,
        limit: int = 3,
    ) -> list[dict]:
        """Fallback: return the most recent episodes from PostgreSQL."""
        try:
            async with get_ai_conn() as conn:
                rows = await conn.fetch(
                    """SELECT summary, session_id::TEXT, created_at
                       FROM agent_episodes
                       WHERE user_id = $1 AND agent_type = $2
                       ORDER BY created_at DESC
                       LIMIT $3""",
                    user_id, agent_type, limit,
                )
            return [
                {
                    "summary": r["summary"],
                    "session_id": r["session_id"],
                    "score": 1.0,  # no relevance score from PG
                    "created_at": r["created_at"].isoformat()
                        if r["created_at"] else "",
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("LTM PG fallback failed: %s", exc)
            return []


# Singleton
ltm = LTMemory()
