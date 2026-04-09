from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_ai_conn

logger   = logging.getLogger(__name__)
settings = get_settings()

router       = APIRouter(prefix="/auto-index",    tags=["Auto-Index"])
graph_router = APIRouter(prefix="/knowledge-graph", tags=["Knowledge Graph"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class AutoIndexRequest(BaseModel):
    content_id: int
    course_id: int
    file_url: str
    content_type: str = "application/pdf"
    force: bool = False


class AutoIndexTextRequest(BaseModel):
    content_id: int
    course_id: int
    title: str
    text_content: str
    force: bool = False


class AutoIndexResponse(BaseModel):
    job_id: str
    content_id: int
    status: str = "queued"
    message: str = "Document queued for auto-indexing"


class AutoIndexStatusResponse(BaseModel):
    content_id: int
    status: str
    nodes_created: int = 0
    chunks_created: int = 0
    progress: int = 0
    stage: str = ""
    error: Optional[str] = None
    job_id: Optional[str] = None


class GraphNode(BaseModel):
    id: int
    name: str
    name_vi: Optional[str]
    name_en: Optional[str]
    description: Optional[str]
    source_content_id: Optional[int]
    source_content_title: Optional[str]
    course_id: Optional[int] = None
    auto_generated: bool
    chunk_count: int
    level: int


class GraphEdge(BaseModel):
    source: int
    target: int
    relation_type: str
    strength: float
    auto_generated: bool


class KnowledgeGraphResponse(BaseModel):
    course_id: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ── Helper: AI-owned content index status ──────────────────────────────────────

async def _upsert_content_status(content_id: int, course_id: int, status: str, title: str = ""):
    """Create or update the content index status in AI DB."""
    async with get_ai_conn() as conn:
        await conn.execute(
            """INSERT INTO content_index_status (content_id, course_id, title, status, updated_at)
               VALUES ($1, $2, $3, $4, NOW())
               ON CONFLICT (content_id) DO UPDATE
                   SET status = $4, updated_at = NOW()""",
            content_id, course_id, title, status,
        )


async def _get_content_status(content_id: int) -> dict | None:
    """Read content index status from AI DB."""
    async with get_ai_conn() as conn:
        row = await conn.fetchrow(
            "SELECT status, error FROM content_index_status WHERE content_id=$1",
            content_id,
        )
    return dict(row) if row else None


# ── Helper: build title map from AI DB knowledge_nodes ─────────────────────────

async def _build_title_map(content_ids: list[int]) -> dict[int, str]:
    """Get source_content_title from knowledge_nodes (denormalized, no LMS DB)."""
    if not content_ids:
        return {}
    async with get_ai_conn() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT source_content_id, source_content_title
               FROM knowledge_nodes
               WHERE source_content_id = ANY($1)
                 AND source_content_title IS NOT NULL
                 AND source_content_title != ''""",
            content_ids,
        )
    return {r["source_content_id"]: r["source_content_title"] for r in rows}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", response_model=AutoIndexResponse)
async def trigger_auto_index(body: AutoIndexRequest, request: Request):
    _verify(request)

    if body.force:
        from app.services.rag_service import rag_service
        await rag_service.delete_chunks_for_content(body.content_id)
        async with get_ai_conn() as conn:
            await conn.execute(
                "DELETE FROM knowledge_nodes WHERE source_content_id=$1", body.content_id
            )

    # Track status in AI DB
    await _upsert_content_status(body.content_id, body.course_id, "processing")

    from app.worker.celery_app import auto_index_task
    task = auto_index_task.delay(
        content_id=body.content_id,
        course_id=body.course_id,
        file_url=body.file_url,
        content_type=body.content_type,
        force=body.force,
    )

    return AutoIndexResponse(job_id=task.id, content_id=body.content_id)


@router.post("/text", response_model=AutoIndexResponse)
async def trigger_auto_index_text(body: AutoIndexTextRequest, request: Request):
    _verify(request)

    if body.force:
        from app.services.rag_service import rag_service
        await rag_service.delete_chunks_for_content(body.content_id)
        async with get_ai_conn() as conn:
            await conn.execute(
                "DELETE FROM knowledge_nodes WHERE source_content_id=$1", body.content_id
            )

    await _upsert_content_status(body.content_id, body.course_id, "processing")

    from app.worker.celery_app import auto_index_text_task
    try:
        task = auto_index_text_task.delay(
            content_id=body.content_id, course_id=body.course_id,
            title=body.title, text_content=body.text_content, force=body.force,
        )
    except Exception as e:
        logger.error("Failed to enqueue auto_index_text_task: %s", e)
        await _upsert_content_status(body.content_id, body.course_id, "failed")
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")

    return AutoIndexResponse(job_id=task.id, content_id=body.content_id)


@router.get("/{content_id}/status", response_model=AutoIndexStatusResponse)
async def get_auto_index_status(
    content_id: int, request: Request, job_id: Optional[str] = None
):
    _verify(request)

    # Read status from AI DB
    status_data = await _get_content_status(content_id)
    if not status_data:
        ai_status = "unindexed"
    else:
        ai_status = status_data["status"]

    async with get_ai_conn() as conn:
        nodes_row  = await conn.fetchrow(
            "SELECT COUNT(*) AS n FROM knowledge_nodes WHERE source_content_id=$1", content_id
        )
        chunks_row = await conn.fetchrow(
            "SELECT COUNT(*) AS n FROM document_chunks WHERE content_id=$1 AND status='ready'", content_id
        )

    progress, stage = 0, ""
    if job_id:
        try:
            from app.worker.celery_app import celery_app
            task_result = celery_app.AsyncResult(job_id)
            if task_result.state == "PROGRESS" and task_result.info:
                progress = task_result.info.get("progress", 0)
                stage    = task_result.info.get("stage", "")
            elif task_result.state == "SUCCESS":
                progress, stage = 100, "done"
        except Exception:
            pass

    if not progress:
        progress = {"pending": 0, "processing": 50, "indexed": 100, "failed": 0}.get(
            ai_status, 0
        )

    return AutoIndexStatusResponse(
        content_id=content_id,
        status=ai_status,
        nodes_created=nodes_row["n"]  or 0,
        chunks_created=chunks_row["n"] or 0,
        progress=progress, stage=stage, job_id=job_id,
    )


# ── Knowledge Graph endpoints ──────────────────────────────────────────────────

@graph_router.get("/global")
async def get_global_knowledge_graph(
    request: Request,
    min_strength: float = 0.5,
    limit: int = 2000,
):
    """
    Entire knowledge graph across all courses.
    For admin dashboard and AI agent context.
    """
    _verify(request)

    if not settings.neo4j_enabled:
        raise HTTPException(status_code=501, detail="Neo4j not enabled")

    from app.services.neo4j_service import neo4j_service
    graph = await neo4j_service.get_global_graph(
        limit_nodes=limit, min_strength=min_strength
    )

    # Enrich source_content_title from AI DB (denormalized)
    content_ids = [
        n["source_content_id"] for n in graph["nodes"]
        if n.get("source_content_id")
    ]
    title_map = await _build_title_map(content_ids)

    nodes = [
        GraphNode(
            id=n["id"], name=n.get("name", ""),
            name_vi=n.get("name_vi"), name_en=n.get("name_en"),
            description=n.get("description"),
            source_content_id=n.get("source_content_id"),
            source_content_title=title_map.get(n["source_content_id"])
                if n.get("source_content_id") else None,
            course_id=n.get("course_id"),
            auto_generated=bool(n.get("auto_generated", True)),
            chunk_count=0, level=0,
        )
        for n in graph["nodes"]
    ]
    edges = [
        GraphEdge(
            source=e["source"], target=e["target"],
            relation_type=e.get("relation_type", "RELATED").lower(),
            strength=float(e.get("strength", 0.5)),
            auto_generated=bool(e.get("auto_generated", True)),
        )
        for e in graph["edges"]
    ]
    return KnowledgeGraphResponse(
        course_id=0, nodes=nodes, edges=edges  # course_id=0 for global
    )


@graph_router.get("/{course_id}", response_model=KnowledgeGraphResponse)
async def get_knowledge_graph(course_id: int, request: Request):
    _verify(request)

    # Use Neo4j if enabled — richer graph with cross-course edges
    if settings.neo4j_enabled:
        from app.services.neo4j_service import neo4j_service
        graph = await neo4j_service.get_course_graph(course_id)

        # Enrich source_content_title from AI DB
        content_ids = [
            n["source_content_id"] for n in graph["nodes"]
            if n.get("source_content_id")
        ]
        title_map = await _build_title_map(content_ids)

        nodes = [
            GraphNode(
                id=n["id"], name=n.get("name", ""),
                name_vi=n.get("name_vi"), name_en=n.get("name_en"),
                description=n.get("description"),
                source_content_id=n.get("source_content_id"),
                source_content_title=title_map.get(n["source_content_id"])
                    if n.get("source_content_id") else None,
                course_id=n.get("course_id", course_id),
                auto_generated=bool(n.get("auto_generated", True)),
                chunk_count=0,
                level=0,
            )
            for n in graph["nodes"]
        ]
        edges = [
            GraphEdge(
                source=e["source"], target=e["target"],
                relation_type=e.get("relation_type", "RELATED").lower(),
                strength=float(e.get("strength", 0.5)),
                auto_generated=bool(e.get("auto_generated", True)),
            )
            for e in graph["edges"]
        ]
        return KnowledgeGraphResponse(
            course_id=course_id, nodes=nodes, edges=edges
        )

    # Fallback: PostgreSQL path (legacy)
    async with get_ai_conn() as conn:
        node_rows = await conn.fetch(
            """
            SELECT kn.id, kn.course_id, kn.name, kn.name_vi, kn.name_en, kn.description,
                   kn.source_content_id, kn.source_content_title,
                   kn.auto_generated, kn.level,
                   COUNT(DISTINCT dc.id) AS chunk_count
            FROM knowledge_nodes kn
            LEFT JOIN document_chunks dc ON dc.node_id = kn.id
            WHERE kn.course_id = $1
            GROUP BY kn.id, kn.course_id, kn.name, kn.name_vi, kn.name_en, kn.description,
                     kn.source_content_id, kn.source_content_title,
                     kn.auto_generated, kn.level
            ORDER BY kn.level, kn.order_index
            """,
            course_id,
        )
        edge_rows = await conn.fetch(
            """
            SELECT source_node_id, target_node_id, relation_type, strength, auto_generated
            FROM knowledge_node_relations WHERE course_id = $1 ORDER BY strength DESC
            """,
            course_id,
        )

    nodes = [
        GraphNode(
            id=r["id"], name=r["name"], name_vi=r["name_vi"], name_en=r["name_en"],
            description=r["description"], source_content_id=r["source_content_id"],
            source_content_title=r["source_content_title"] if r["source_content_id"] else None,
            course_id=r["course_id"],
            auto_generated=r["auto_generated"],
            chunk_count=r["chunk_count"] or 0, level=r["level"],
        )
        for r in node_rows
    ]
    edges = [
        GraphEdge(
            source=r["source_node_id"], target=r["target_node_id"],
            relation_type=r["relation_type"], strength=float(r["strength"]),
            auto_generated=r["auto_generated"],
        )
        for r in edge_rows
    ]
    return KnowledgeGraphResponse(course_id=course_id, nodes=nodes, edges=edges)


@graph_router.delete("/node/{node_id}")
async def delete_knowledge_node(node_id: int, request: Request):
    _verify(request)

    async with get_ai_conn() as conn:
        node = await conn.fetchrow(
            "SELECT id, course_id, auto_generated FROM knowledge_nodes WHERE id=$1", node_id
        )
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        await conn.execute("DELETE FROM knowledge_nodes WHERE id=$1", node_id)

    return {"ok": True, "deleted_node_id": node_id}




@graph_router.get("/node/{node_id}/neighbors")
async def get_node_neighbors(
    node_id: int,
    request: Request,
    depth: int = 2,
    max_nodes: int = 50,
):
    """
    BFS from a node across all courses.
    For AI learning agent context building.
    """
    _verify(request)

    if not settings.neo4j_enabled:
        raise HTTPException(status_code=501, detail="Neo4j not enabled")

    from app.services.neo4j_service import neo4j_service
    result = await neo4j_service.get_node_neighbors(
        node_id=node_id, max_depth=min(depth, 4), max_nodes=min(max_nodes, 200)
    )

    # Enrich content titles from AI DB
    all_nodes = [result.get("center")] if result.get("center") else []
    all_nodes.extend(result.get("neighbors", []))
    content_ids = [
        n["source_content_id"] for n in all_nodes
        if n and n.get("source_content_id")
    ]
    title_map = await _build_title_map(content_ids)

    nodes = [
        GraphNode(
            id=n["id"], name=n.get("name", ""),
            name_vi=n.get("name_vi"), name_en=n.get("name_en"),
            description=n.get("description"),
            source_content_id=n.get("source_content_id"),
            source_content_title=title_map.get(n["source_content_id"])
                if n.get("source_content_id") else None,
            course_id=n.get("course_id"),
            auto_generated=bool(n.get("auto_generated", True)),
            chunk_count=0, level=0,
        )
        for n in all_nodes if n
    ]
    edges = [
        GraphEdge(
            source=e["source"], target=e["target"],
            relation_type=e.get("relation_type", "RELATED").lower(),
            strength=float(e.get("strength", 0.5)),
            auto_generated=bool(e.get("auto_generated", True)),
        )
        for e in result.get("edges", [])
    ]
    return KnowledgeGraphResponse(
        course_id=0, nodes=nodes, edges=edges
    )

def _verify(request: Request):
    if request.headers.get("X-AI-Secret", "") != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")