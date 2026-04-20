"""
ai-service/app/agents/memory/system_memory.py

System Memory — knowledge about course content and structure.

Wraps the existing RAG service and Neo4j knowledge graph to provide
the agent with structured information about course materials.

This is NOT user-specific — it's the "world knowledge" of the LMS:
  - Document chunks via Qdrant/pgvector (rag_service)
  - Knowledge graph topology via Neo4j (neo4j_service)
  - Course structure via PostgreSQL (knowledge_nodes)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import get_settings
from app.core.database import get_ai_conn

logger = logging.getLogger(__name__)
settings = get_settings()


class SystemMemory:
    """Provides course content and structure context to agents."""

    async def retrieve_course_context(
        self,
        course_id: int,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """
        RAG search over course materials.

        Returns top_k relevant document chunks for the given query.
        """
        from app.services.rag_service import rag_service

        try:
            chunks = await rag_service.search_multilingual(
                query=query,
                course_id=course_id,
                top_k=top_k,
            )
            return [
                {
                    "chunk_id": c.chunk_id,
                    "text": c.chunk_text,
                    "similarity": round(c.similarity, 3),
                    "source_type": c.source_type,
                    "page_number": c.page_number,
                    "content_id": c.content_id,
                    "node_id": c.node_id,
                }
                for c in chunks
            ]
        except Exception as exc:
            logger.error("System memory RAG search failed: %s", exc)
            return []

    async def retrieve_knowledge_structure(
        self,
        course_id: int,
    ) -> dict:
        """
        Get the knowledge graph structure for a course.

        Returns nodes and their relationships from Neo4j.
        Falls back to PostgreSQL if Neo4j is disabled.
        """
        if settings.neo4j_enabled:
            try:
                from app.services.neo4j_service import neo4j_service
                graph = await neo4j_service.get_course_graph(course_id)
                return {
                    "nodes": [
                        {
                            "id": n["id"],
                            "name": n.get("name", ""),
                            "name_vi": n.get("name_vi", ""),
                            "description": n.get("description", ""),
                        }
                        for n in graph.get("nodes", [])
                    ],
                    "edges": [
                        {
                            "source": e["source"],
                            "target": e["target"],
                            "type": e.get("relation_type", "related"),
                        }
                        for e in graph.get("edges", [])
                    ],
                    "source": "neo4j",
                }
            except Exception as exc:
                logger.warning("Neo4j graph fetch failed, falling back to PG: %s", exc)

        # Fallback: PostgreSQL knowledge_nodes
        return await self._get_structure_from_pg(course_id)

    async def _get_structure_from_pg(self, course_id: int) -> dict:
        """Fallback: get knowledge structure from PostgreSQL."""
        try:
            async with get_ai_conn() as conn:
                nodes = await conn.fetch(
                    """SELECT id, name, name_vi, description, level
                       FROM knowledge_nodes
                       WHERE course_id = $1
                       ORDER BY level, order_index""",
                    course_id,
                )
                edges = await conn.fetch(
                    """SELECT source_node_id AS source,
                              target_node_id AS target,
                              relation_type AS type
                       FROM knowledge_node_relations
                       WHERE course_id = $1""",
                    course_id,
                )
            return {
                "nodes": [
                    {
                        "id": n["id"],
                        "name": n["name"],
                        "name_vi": n["name_vi"],
                        "description": n["description"],
                    }
                    for n in nodes
                ],
                "edges": [
                    {"source": e["source"], "target": e["target"], "type": e["type"]}
                    for e in edges
                ],
                "source": "postgresql",
            }
        except Exception as exc:
            logger.error("PG knowledge structure fetch failed: %s", exc)
            return {"nodes": [], "edges": [], "source": "error"}

    async def get_node_context(
        self,
        node_id: int,
        max_depth: int = 2,
    ) -> dict:
        """
        Get detailed context for a specific knowledge node,
        including its neighbors in the graph.
        """
        if settings.neo4j_enabled:
            try:
                from app.services.neo4j_service import neo4j_service
                return await neo4j_service.get_node_neighbors(
                    node_id=node_id,
                    max_depth=max_depth,
                )
            except Exception as exc:
                logger.warning("Neo4j node context failed: %s", exc)

        # Fallback: just get the node from PG
        try:
            async with get_ai_conn() as conn:
                node = await conn.fetchrow(
                    """SELECT id, name, name_vi, description, course_id
                       FROM knowledge_nodes WHERE id = $1""",
                    node_id,
                )
            if node:
                return {
                    "center_id": node_id,
                    "neighbors": [],
                    "edges": [],
                    "node": dict(node),
                }
        except Exception as exc:
            logger.error("PG node context failed: %s", exc)

        return {"center_id": node_id, "neighbors": [], "edges": []}

    async def get_course_summary(self, course_id: int) -> dict:
        """
        Get a high-level summary of course content.
        Used for the agent to understand what the course covers.
        """
        try:
            async with get_ai_conn() as conn:
                # Count indexed content
                stats = await conn.fetchrow(
                    """SELECT
                           COUNT(DISTINCT kn.id) AS node_count,
                           COUNT(DISTINCT dc.id) AS chunk_count,
                           COUNT(DISTINCT dc.content_id) AS content_count
                       FROM knowledge_nodes kn
                       LEFT JOIN document_chunks dc ON dc.course_id = kn.course_id
                       WHERE kn.course_id = $1""",
                    course_id,
                )

                # Get top-level knowledge nodes
                top_nodes = await conn.fetch(
                    """SELECT name, name_vi, description
                       FROM knowledge_nodes
                       WHERE course_id = $1 AND level <= 1
                       ORDER BY order_index
                       LIMIT 10""",
                    course_id,
                )

            return {
                "course_id": course_id,
                "node_count": stats["node_count"] if stats else 0,
                "chunk_count": stats["chunk_count"] if stats else 0,
                "content_count": stats["content_count"] if stats else 0,
                "top_topics": [
                    {"name": n["name"], "name_vi": n["name_vi"]}
                    for n in top_nodes
                ],
            }
        except Exception as exc:
            logger.error("Course summary failed: %s", exc)
            return {"course_id": course_id, "error": str(exc)}


# Singleton
system_memory = SystemMemory()
