"""
ai-service/app/services/graph_linker.py

Smart cross-course knowledge graph linker.

Pipeline (called after every auto_index run):
  1. Take new node embeddings + all existing nodes (from Qdrant).
  2. Compute cosine similarity against nodes from OTHER courses.
  3. For pairs above CROSS_COURSE_THRESHOLD, call LLM to:
       a. Confirm the connection is real (not coincidental term overlap).
       b. Classify the relationship type.
       c. Write a human-readable reason.
  4. Write edges to Neo4j.

Why LLM enrichment matters:
  "Array" in a programming course vs "Array" in a math course may be
  similar vectors but are NOT the same concept.
  The LLM reads descriptions and decides: EQUIVALENT, RELATED, or no link.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import numpy as np

from app.core.config import get_settings
from app.core.llm import chat_complete_json
from app.services.neo4j_service import (
    neo4j_service,
    INTRA_COURSE_THRESHOLD,
    CROSS_COURSE_THRESHOLD,
    EQUIVALENT_THRESHOLD,
    RELATIONSHIP_TYPES,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Max cross-course pairs to send to LLM per indexing run
# (prevents token/cost explosion on large knowledge graphs)
MAX_LLM_ENRICHMENT_PAIRS = 20

LINKER_SYSTEM_PROMPT = """\
Bạn là chuyên gia phân tích mối quan hệ giữa các khái niệm học thuật.
Nhiệm vụ: Xác định mối quan hệ giữa hai khái niệm từ hai khóa học khác nhau.
Chỉ trả về JSON hợp lệ, không thêm text khác.\
"""

LINKER_PROMPT_TEMPLATE = """\
KHÁI NIỆM A (Khóa học {course_a}):
  Tên: {name_a}
  Mô tả: {desc_a}

KHÁI NIỆM B (Khóa học {course_b}):
  Tên: {name_b}
  Mô tả: {desc_b}

Hai khái niệm này có liên quan với nhau không?

Nếu có, hãy xác định:
- relation_type: một trong ["equivalent", "prerequisite", "extends", "related", "contrasts_with"]
  * equivalent    = cùng một khái niệm, chỉ khác ngữ cảnh/ngôn ngữ/ký hiệu
  * prerequisite  = A cần học trước để hiểu B (source=A → target=B)
  * extends       = B mở rộng / đào sâu A (source=A → target=B)
  * related       = liên quan nhưng không có chiều rõ ràng
  * contrasts_with = đối lập / so sánh nhau
- strength: 0.5 → 1.0 (mức độ liên kết)
- reason: giải thích ngắn gọn tại sao (1 câu)
- direction: "a_to_b" | "b_to_a" | "bidirectional" (cho prerequisite/extends)

Nếu KHÔNG liên quan thực sự (chỉ trùng từ ngữ tình cờ), trả về connected=false.

Trả về JSON:
{
  "connected": true/false,
  "relation_type": "...",
  "strength": 0.0,
  "reason": "...",
  "direction": "bidirectional"
}
"""


@dataclass
class NodeInfo:
    id: int
    course_id: int
    name: str
    description: str
    embedding: list[float]


async def link_cross_course(
    new_nodes: list[NodeInfo],
    new_course_id: int,
) -> int:
    """
    Main entry point.
    Called after auto_index creates new nodes for a course.
    Returns number of cross-course edges created.
    """
    if not new_nodes:
        return 0

    # 1. Fetch existing nodes from OTHER courses (ids + embeddings from Qdrant)
    other_nodes = await _fetch_other_course_nodes(new_course_id)
    if not other_nodes:
        logger.info("No nodes from other courses yet — skipping cross-course linking")
        return 0

    # 2. Compute cosine similarity matrix
    candidate_pairs = _find_candidate_pairs(new_nodes, other_nodes)

    if not candidate_pairs:
        logger.info("No cross-course candidates above threshold (%.2f)", CROSS_COURSE_THRESHOLD)
        return 0

    logger.info("Found %d cross-course candidate pairs — enriching with LLM", len(candidate_pairs))

    # 3. LLM enrichment (batched, max MAX_LLM_ENRICHMENT_PAIRS)
    top_pairs = sorted(candidate_pairs, key=lambda x: x[2], reverse=True)
    top_pairs = top_pairs[:MAX_LLM_ENRICHMENT_PAIRS]

    edges_to_create = []
    # Run LLM calls concurrently (max 5 at a time to respect rate limits)
    semaphore = asyncio.Semaphore(5)

    async def enrich_pair(node_a: NodeInfo, node_b: NodeInfo, sim: float):
        async with semaphore:
            return await _llm_enrich_pair(node_a, node_b, sim)

    results = await asyncio.gather(
        *[enrich_pair(a, b, sim) for a, b, sim in top_pairs],
        return_exceptions=True,
    )

    for (node_a, node_b, sim), result in zip(top_pairs, results):
        if isinstance(result, Exception):
            logger.warning("LLM enrichment failed for (%d, %d): %s", node_a.id, node_b.id, result)
            # Fallback: use pure similarity to create a RELATED edge
            if sim >= CROSS_COURSE_THRESHOLD + 0.05:
                edges_to_create.append({
                    "source_id":     node_a.id,
                    "target_id":     node_b.id,
                    "rel_type":      "RELATED",
                    "strength":      round(sim, 3),
                    "auto_generated": True,
                    "cross_course":  True,
                    "reason":        f"Similarity={sim:.3f} (LLM fallback)",
                })
            continue

        if not result or not result.get("connected"):
            continue

        rel_type_raw = result.get("relation_type", "related").lower()
        rel_type     = RELATIONSHIP_TYPES.get(rel_type_raw, "RELATED")
        strength     = float(result.get("strength", sim))
        reason       = result.get("reason", "")
        direction    = result.get("direction", "bidirectional")

        if direction == "b_to_a":
            node_a, node_b = node_b, node_a

        if direction == "bidirectional":
            # Both directions
            for src, tgt in [(node_a.id, node_b.id), (node_b.id, node_a.id)]:
                edges_to_create.append({
                    "source_id": src, "target_id": tgt,
                    "rel_type": rel_type, "strength": strength,
                    "auto_generated": True, "cross_course": True,
                    "reason": reason,
                })
        else:
            edges_to_create.append({
                "source_id":     node_a.id,
                "target_id":     node_b.id,
                "rel_type":      rel_type,
                "strength":      strength,
                "auto_generated": True,
                "cross_course":  True,
                "reason":        reason,
            })

    # 4. Write to Neo4j
    if edges_to_create:
        await neo4j_service.upsert_relationships_batch(edges_to_create)
        logger.info(
            "Created %d cross-course edges (from %d candidates)",
            len(edges_to_create), len(top_pairs),
        )

    return len(edges_to_create)


async def link_intra_course(
    new_nodes: list[NodeInfo],
    existing_nodes: list[NodeInfo],
    course_id: int,
    llm_relations: list[dict] | None = None,
) -> int:
    """
    Build intra-course graph edges.
    1. LLM-derived prerequisite/extends relations (from auto_index LLM call).
    2. Similarity-based RELATED edges for high-similarity pairs.
    """
    edges: list[dict] = []

    # 1. LLM-derived relations (already classified)
    if llm_relations:
        for rel in llm_relations:
            src_idx = rel.get("source_index")
            tgt_idx = rel.get("target_index")
            if not (isinstance(src_idx, int) and isinstance(tgt_idx, int)):
                continue
            if src_idx >= len(new_nodes) or tgt_idx >= len(new_nodes):
                continue
            rel_type = RELATIONSHIP_TYPES.get(
                rel.get("relation_type", "related"), "RELATED"
            )
            edges.append({
                "source_id":     new_nodes[src_idx].id,
                "target_id":     new_nodes[tgt_idx].id,
                "rel_type":      rel_type,
                "strength":      round(float(rel.get("strength", 0.85)), 3),
                "auto_generated": True,
                "cross_course":  False,
                "reason":        rel.get("reason", ""),
            })

    # 2. Similarity-based edges (new ↔ new + new ↔ existing)
    all_pairs = _find_candidate_pairs(
        new_nodes,
        existing_nodes,
        threshold=INTRA_COURSE_THRESHOLD,
    )
    # Also intra-new pairs
    all_pairs += _find_candidate_pairs(
        new_nodes, new_nodes,
        threshold=INTRA_COURSE_THRESHOLD,
        skip_same_id=True,
    )

    for node_a, node_b, sim in all_pairs:
        if node_a.id == node_b.id:
            continue
        rel_type = "EQUIVALENT" if sim >= EQUIVALENT_THRESHOLD else "RELATED"
        edges.append({
            "source_id":     node_a.id,
            "target_id":     node_b.id,
            "rel_type":      rel_type,
            "strength":      round(sim, 3),
            "auto_generated": True,
            "cross_course":  False,
            "reason":        f"Cosine similarity={sim:.3f}",
        })

    if edges:
        await neo4j_service.upsert_relationships_batch(edges)

    return len(edges)


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _fetch_other_course_nodes(course_id: int) -> list[NodeInfo]:
    """
    Fetch nodes + embeddings from Qdrant for all courses except course_id.
    Returns NodeInfo list (with embedding populated).
    """
    from app.services.qdrant_service import qdrant_service
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue
    from qdrant_client.http.models import FilterSelector
    from qdrant_client.http.models import models as qdrant_models

    try:
        # Scroll all nodes NOT in this course
        all_points: list = []
        offset = None
        client = qdrant_service._get_client()

        while True:
            from qdrant_client.http.models import Filter, FieldCondition, MustNot, MatchValue
            records, next_offset = await client.scroll(
                collection_name="knowledge_nodes",
                scroll_filter=Filter(
                    must_not=[
                        FieldCondition(
                            key="course_id",
                            match=MatchValue(value=course_id),
                        )
                    ]
                ),
                limit=500,
                offset=offset,
                with_vectors=True,
                with_payload=True,
            )
            all_points.extend(records)
            if next_offset is None or not records:
                break
            offset = next_offset
            if len(all_points) >= 2000:  # cap to avoid memory issues
                break

        result = []
        for p in all_points:
            if p.vector is None:
                continue
            payload = p.payload or {}
            result.append(NodeInfo(
                id=int(p.id),
                course_id=payload.get("course_id", 0),
                name=payload.get("name", ""),
                description=payload.get("description", ""),
                embedding=p.vector,
            ))
        return result

    except Exception as exc:
        logger.warning("_fetch_other_course_nodes failed: %s", exc)
        return []


def _find_candidate_pairs(
    nodes_a: list[NodeInfo],
    nodes_b: list[NodeInfo],
    threshold: float = CROSS_COURSE_THRESHOLD,
    skip_same_id: bool = False,
) -> list[tuple[NodeInfo, NodeInfo, float]]:
    """Vectorized cosine similarity — returns pairs above threshold."""
    if not nodes_a or not nodes_b:
        return []

    emb_a = np.array([n.embedding for n in nodes_a], dtype=np.float32)
    emb_b = np.array([n.embedding for n in nodes_b], dtype=np.float32)

    # L2-normalize
    norms_a = np.linalg.norm(emb_a, axis=1, keepdims=True) + 1e-8
    norms_b = np.linalg.norm(emb_b, axis=1, keepdims=True) + 1e-8
    emb_a /= norms_a
    emb_b /= norms_b

    sims = emb_a @ emb_b.T  # (n_a, n_b)

    pairs = []
    for i, node_a in enumerate(nodes_a):
        for j, node_b in enumerate(nodes_b):
            if skip_same_id and node_a.id == node_b.id:
                continue
            sim = float(sims[i, j])
            if sim >= threshold:
                pairs.append((node_a, node_b, sim))

    return pairs


async def _llm_enrich_pair(
    node_a: NodeInfo,
    node_b: NodeInfo,
    sim: float,
) -> dict | None:
    """
    Call LLM to classify relationship between two nodes from different courses.
    Returns the parsed JSON dict or None on failure.
    """
    prompt = LINKER_PROMPT_TEMPLATE.format(
        course_a=node_a.course_id,
        name_a=node_a.name,
        desc_a=(node_a.description or "")[:300],
        course_b=node_b.course_id,
        name_b=node_b.name,
        desc_b=(node_b.description or "")[:300],
    )
    messages = [
        {"role": "system", "content": LINKER_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    try:
        result = await chat_complete_json(
            messages=messages,
            model=settings.chat_model,  # llama-3.1-8b-instant — fast + cheap
            temperature=0.1,
            max_tokens=200,
        )
        return result
    except Exception as exc:
        logger.warning("LLM enrich pair failed: %s", exc)
        return None