"""
ai-service/app/api/endpoints/auto_index.py
POST /ai/auto-index              — kích hoạt pipeline tự động index tài liệu
GET  /ai/auto-index/{content_id}/status  — poll trạng thái job (kèm progress %)
GET  /ai/knowledge-graph/{course_id}     — nodes + edges cho visualization
DELETE /ai/knowledge-graph/node/{node_id} — xóa node auto-generated
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

router = APIRouter(prefix="/auto-index", tags=["Auto-Index"])
graph_router = APIRouter(prefix="/knowledge-graph", tags=["Knowledge Graph"])


#  Schemas 

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
    status: str                  # queued | processing | indexed | failed
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


#  Endpoints 

@router.post("", response_model=AutoIndexResponse)
async def trigger_auto_index(body: AutoIndexRequest, request: Request):
    """
    LMS gọi sau khi giáo viên click "Index tài liệu".
    - force=False (default): skip nếu content đã indexed
    - force=True: xóa chunks/nodes cũ và re-index
    Trả về ngay job_id; Celery xử lý bất đồng bộ.
    """
    _verify_internal(request)

    # Nếu force, xóa chunks và nodes cũ
    if body.force:
        from app.services.rag_service import rag_service
        await rag_service.delete_chunks_for_content(body.content_id)

        async with get_async_conn() as conn:
            await conn.execute(
                "DELETE FROM knowledge_nodes WHERE source_content_id=$1",
                body.content_id,
            )

    # Cập nhật trạng thái → processing
    async with get_async_conn() as conn:
        await conn.execute(
            "UPDATE section_content SET ai_index_status='processing' WHERE id=$1",
            body.content_id,
        )

    # Enqueue Celery task
    from app.worker.celery_app import auto_index_task
    task = auto_index_task.delay(
        content_id=body.content_id,
        course_id=body.course_id,
        file_url=body.file_url,
        content_type=body.content_type,
        force=body.force,
    )

    return AutoIndexResponse(
        job_id=task.id,
        content_id=body.content_id,
        status="queued",
    )


@router.post("/text", response_model=AutoIndexResponse)
async def trigger_auto_index_text(body: AutoIndexTextRequest, request: Request):
    """
    LMS gọi để index TEXT content.
    - Gửi text_content trực tiếp thay vì file_url
    - Tạo Celery task để xử lý asynchronously
    """
    _verify_internal(request)

    # Nếu force, xóa chunks và nodes cũ
    if body.force:
        from app.services.rag_service import rag_service
        await rag_service.delete_chunks_for_content(body.content_id)

        async with get_async_conn() as conn:
            await conn.execute(
                "DELETE FROM knowledge_nodes WHERE source_content_id=$1",
                body.content_id,
            )

    # Cập nhật trạng thái → processing
    async with get_async_conn() as conn:
        await conn.execute(
            "UPDATE section_content SET ai_index_status='processing' WHERE id=$1",
            body.content_id,
        )

    # Enqueue Celery task for text content
    from app.worker.celery_app import auto_index_text_task
    
    try:
        task = auto_index_text_task.delay(
            content_id=body.content_id,
            course_id=body.course_id,
            title=body.title,
            text_content=body.text_content,
            force=body.force,
        )
    except Exception as e:
        logger.error("Failed to enqueue auto_index_text_task: %s", e)
        # Fallback: mark as failed
        async with get_async_conn() as conn:
            await conn.execute(
                "UPDATE section_content SET ai_index_status='failed' WHERE id=$1",
                body.content_id,
            )
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")

    return AutoIndexResponse(
        job_id=task.id,
        content_id=body.content_id,
        status="queued",
    )


@router.get("/{content_id}/status", response_model=AutoIndexStatusResponse)
async def get_auto_index_status(
    content_id: int,
    request: Request,
    job_id: Optional[str] = None,
):
    """
    Frontend poll endpoint này để biết trạng thái index.
    - Kết hợp DB status (real-time) + Celery task state (progress %)
    - Truyền job_id làm query param để lấy được progress chi tiết.
    """
    _verify_internal(request)

    async with get_async_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT ai_index_status,
                   (SELECT COUNT(*) FROM knowledge_nodes
                    WHERE source_content_id=$1) AS nodes_created,
                   (SELECT COUNT(*) FROM document_chunks
                    WHERE content_id=$1 AND status='ready') AS chunks_created
            FROM section_content WHERE id=$1
            """,
            content_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Content not found")

    # Lấy progress từ Celery task state (nếu có job_id)
    progress = 0
    stage = ""
    if job_id:
        try:
            from app.worker.celery_app import celery_app
            task_result = celery_app.AsyncResult(job_id)
            if task_result.state == "PROGRESS" and task_result.info:
                progress = task_result.info.get("progress", 0)
                stage = task_result.info.get("stage", "")
            elif task_result.state == "SUCCESS":
                progress = 100
                stage = "done"
        except Exception:
            pass  # Celery backend không khả dụng → bỏ qua

    # Map DB status → progress estimate (khi không có job_id)
    if not progress:
        status_progress_map = {
            "pending": 0,
            "processing": 50,
            "indexed": 100,
            "failed": 0,
        }
        progress = status_progress_map.get(row["ai_index_status"], 0)

    return AutoIndexStatusResponse(
        content_id=content_id,
        status=row["ai_index_status"],
        nodes_created=row["nodes_created"] or 0,
        chunks_created=row["chunks_created"] or 0,
        progress=progress,
        stage=stage,
        job_id=job_id,
    )


#  Knowledge Graph endpoints 

@graph_router.get("/{course_id}", response_model=KnowledgeGraphResponse)
async def get_knowledge_graph(course_id: int, request: Request):
    """
    Trả về toàn bộ knowledge graph của một khóa học.
    Dùng để visualize trên frontend (teacher dashboard).
    """
    _verify_internal(request)

    async with get_async_conn() as conn:
        node_rows = await conn.fetch(
            """
            SELECT kn.id, kn.name, kn.name_vi, kn.name_en, kn.description,
                   kn.source_content_id, kn.auto_generated, kn.level,
                   sc.title AS source_content_title,
                   COUNT(DISTINCT dc.id) AS chunk_count
            FROM knowledge_nodes kn
            LEFT JOIN section_content sc ON sc.id = kn.source_content_id
            LEFT JOIN document_chunks dc ON dc.node_id = kn.id
            WHERE kn.course_id = $1
            GROUP BY kn.id, kn.name, kn.name_vi, kn.name_en, kn.description,
                     kn.source_content_id, kn.auto_generated, kn.level, sc.title
            ORDER BY kn.level, kn.order_index
            """,
            course_id,
        )

        edge_rows = await conn.fetch(
            """
            SELECT source_node_id, target_node_id, relation_type, strength, auto_generated
            FROM knowledge_node_relations
            WHERE course_id = $1
            ORDER BY strength DESC
            """,
            course_id,
        )

    nodes = [
        GraphNode(
            id=r["id"], name=r["name"], name_vi=r["name_vi"], name_en=r["name_en"],
            description=r["description"], source_content_id=r["source_content_id"],
            source_content_title=r["source_content_title"],
            auto_generated=r["auto_generated"],
            chunk_count=r["chunk_count"] or 0,
            level=r["level"],
        )
        for r in node_rows
    ]
    edges = [
        GraphEdge(
            source=r["source_node_id"], target=r["target_node_id"],
            relation_type=r["relation_type"],
            strength=float(r["strength"]),
            auto_generated=r["auto_generated"],
        )
        for r in edge_rows
    ]
    return KnowledgeGraphResponse(course_id=course_id, nodes=nodes, edges=edges)


@graph_router.delete("/node/{node_id}")
async def delete_knowledge_node(node_id: int, request: Request):
    """
    Cho phép giáo viên xóa node auto-generated không chính xác.
    Chunks liên quan sẽ được reassign node_id=NULL (vẫn searchable).
    """
    _verify_internal(request)

    async with get_async_conn() as conn:
        node = await conn.fetchrow(
            "SELECT id, course_id, auto_generated FROM knowledge_nodes WHERE id=$1",
            node_id,
        )
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        await conn.execute("DELETE FROM knowledge_nodes WHERE id=$1", node_id)

    return {"ok": True, "deleted_node_id": node_id}


#  Auth 

def _verify_internal(request: Request):
    secret = request.headers.get("X-AI-Secret", "")
    if secret != settings.ai_service_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")