-- ============================================================
-- 005_bge_m3_migration.sql
-- Migrate embedding vectors from nomic-ai/nomic-embed-text-v1.5 (768d)
-- to BAAI/bge-m3 (1024d).
--
-- STRATEGY (zero-downtime gradual):
--   1. Add shadow column embedding_v2 VECTOR(1024) — system writes here
--      for all NEW chunks while old embedding column stays live.
--   2. Background reindex job populates embedding_v2 for existing chunks.
--   3. Once reindex_progress = 100%, run the cutover migration (Part B).
--
-- Run Part A now.  Run Part B in maintenance window after reindex completes.
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- PART A  — shadow column + tracking (run immediately)
-- ────────────────────────────────────────────────────────────

BEGIN;

-- 1. Add shadow embedding column for bge-m3 (1024d)
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding_v2 VECTOR(1024);

ALTER TABLE knowledge_nodes
    ADD COLUMN IF NOT EXISTS description_embedding_v2 VECTOR(1024);

-- 2. Track reindex progress per content item
ALTER TABLE section_content
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(64) DEFAULT 'nomic-v1.5';

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(64) DEFAULT 'nomic-v1.5';

-- 3. Reindex job tracking table
CREATE TABLE IF NOT EXISTS embedding_reindex_jobs (
    id            BIGSERIAL PRIMARY KEY,
    course_id     BIGINT    REFERENCES courses(id) ON DELETE CASCADE,
    content_id    BIGINT    REFERENCES section_content(id) ON DELETE CASCADE,
    status        VARCHAR(20) DEFAULT 'pending'
                      CHECK (status IN ('pending','processing','done','failed')),
    chunks_total  INTEGER DEFAULT 0,
    chunks_done   INTEGER DEFAULT 0,
    error_message TEXT,
    started_at    TIMESTAMP,
    completed_at  TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reindex_jobs_status     ON embedding_reindex_jobs(status);
CREATE INDEX IF NOT EXISTS idx_reindex_jobs_course     ON embedding_reindex_jobs(course_id);
CREATE INDEX IF NOT EXISTS idx_reindex_jobs_content    ON embedding_reindex_jobs(content_id);

-- 4. Aggregate view — reindex progress dashboard
CREATE OR REPLACE VIEW v_reindex_progress AS
SELECT
    COUNT(*)                                          AS total_jobs,
    COUNT(*) FILTER (WHERE status = 'done')           AS done,
    COUNT(*) FILTER (WHERE status = 'pending')        AS pending,
    COUNT(*) FILTER (WHERE status = 'processing')     AS processing,
    COUNT(*) FILTER (WHERE status = 'failed')         AS failed,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'done')::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                 AS pct_done,
    SUM(chunks_total)                                 AS total_chunks,
    SUM(chunks_done)                                  AS reindexed_chunks
FROM embedding_reindex_jobs;

-- 5. HNSW index on shadow column (build while live traffic uses old index)
--    Using hnsw with ef_construction=128 for better recall on 1024d
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_v2_hnsw
    ON document_chunks
    USING hnsw (embedding_v2 vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

CREATE INDEX IF NOT EXISTS idx_nodes_embedding_v2_hnsw
    ON knowledge_nodes
    USING hnsw (description_embedding_v2 vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

COMMIT;


-- ────────────────────────────────────────────────────────────
-- PART B  — cutover  (run AFTER reindex_progress.pct_done = 100)
--           Execute in a maintenance window
-- ────────────────────────────────────────────────────────────
-- DO NOT RUN PART B until all jobs are 'done'.
--
-- BEGIN;
--
-- -- Swap columns: rename old → _nomic, new → canonical
-- ALTER TABLE document_chunks
--     DROP   COLUMN IF EXISTS embedding,
--     RENAME COLUMN embedding_v2 TO embedding;
--
-- ALTER TABLE knowledge_nodes
--     DROP   COLUMN IF EXISTS description_embedding,
--     RENAME COLUMN description_embedding_v2 TO description_embedding;
--
-- -- Drop the old 768d HNSW index (was named idx_chunks_embedding_hnsw)
-- DROP INDEX IF EXISTS idx_chunks_embedding_hnsw;
-- DROP INDEX IF EXISTS idx_knowledge_nodes_embedding;
--
-- -- Rename the new HNSW indexes to canonical names
-- ALTER INDEX idx_chunks_embedding_v2_hnsw  RENAME TO idx_chunks_embedding_hnsw;
-- ALTER INDEX idx_nodes_embedding_v2_hnsw   RENAME TO idx_knowledge_nodes_embedding;
--
-- -- Update model tags
-- UPDATE document_chunks   SET embedding_model = 'bge-m3';
-- UPDATE section_content   SET embedding_model = 'bge-m3';
--
-- COMMIT;