-- ============================================================
-- lms-service/migrations/004_ai_references.sql
--
-- LMS-side AI integration columns.
-- These are plain BIGINT "soft references" to AI-domain entities
-- that now live in the dedicated AI PostgreSQL instance.
--
-- ⚠️  NO pgvector extension required here.
--     Vector storage has moved to Qdrant (ai-service).
--     Knowledge graph storage lives in AI PostgreSQL.
--
-- This file replaces the former 004_ai_system.sql which tried to
-- replicate the full AI schema inside the LMS database.
-- ============================================================

-- ── section_content: AI indexing state ────────────────────────────────────────
-- ai_index_status already exists from 001_core_schema.sql.
-- These additional columns make it easier to trace indexing history.

ALTER TABLE section_content
    ADD COLUMN IF NOT EXISTS ai_index_job_id  BIGINT,        -- soft ref → AI.document_processing_jobs.id
    ADD COLUMN IF NOT EXISTS ai_indexed_at    TIMESTAMP,
    ADD COLUMN IF NOT EXISTS embedding_model  VARCHAR(64) DEFAULT 'bge-m3';

-- ── quiz_questions: Bloom's taxonomy + knowledge graph links ──────────────────
-- Soft references into the AI PostgreSQL instance.
-- No FK constraints: cross-DB referential integrity is enforced at app layer.

ALTER TABLE quiz_questions
    ADD COLUMN IF NOT EXISTS node_id            BIGINT,      -- soft ref → AI.knowledge_nodes.id
    ADD COLUMN IF NOT EXISTS bloom_level        VARCHAR(20)
        CHECK (bloom_level IN ('remember','understand','apply','analyze','evaluate','create')),
    ADD COLUMN IF NOT EXISTS reference_chunk_id BIGINT;      -- soft ref → AI.document_chunks.id

-- Index for common join patterns (fetch questions by knowledge node)
CREATE INDEX IF NOT EXISTS idx_quiz_questions_node     ON quiz_questions(node_id)
    WHERE node_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quiz_questions_bloom    ON quiz_questions(bloom_level)
    WHERE bloom_level IS NOT NULL;

-- ── Trigger: reset AI index state on content re-index request ─────────────────
-- When ai_index_status transitions to 'processing', clear the stale job reference
-- so the new job ID can be written cleanly.

CREATE OR REPLACE FUNCTION reset_ai_index_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ai_index_status = 'processing' AND OLD.ai_index_status <> 'processing' THEN
        NEW.ai_indexed_at   := NULL;
        NEW.ai_index_job_id := NULL;
    END IF;
    IF NEW.ai_index_status = 'indexed' THEN
        NEW.ai_indexed_at := CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_reset_ai_index_timestamp ON section_content;

CREATE TRIGGER trigger_reset_ai_index_timestamp
    BEFORE UPDATE OF ai_index_status ON section_content
    FOR EACH ROW EXECUTE FUNCTION reset_ai_index_timestamp();

-- ── Convenience view: content items with their AI index status ─────────────────

CREATE OR REPLACE VIEW v_content_ai_status AS
SELECT
    sc.id                AS content_id,
    sc.title,
    sc.type,
    sc.ai_index_status,
    sc.ai_indexed_at,
    sc.embedding_model,
    cs.course_id,
    c.title              AS course_title
FROM section_content    sc
JOIN course_sections    cs ON cs.id       = sc.section_id
JOIN courses            c  ON c.id        = cs.course_id
WHERE sc.type NOT IN ('QUIZ', 'FORUM', 'ANNOUNCEMENT')
ORDER BY sc.ai_index_status, sc.updated_at DESC;
