-- =============================================================
-- AI Service — Migration 003: Performance indexes
-- Apply to postgres-ai instance.
-- All statements use IF NOT EXISTS — safe to re-run.
-- =============================================================

-- ── ai_diagnoses ──────────────────────────────────────────────
-- Hot path: diagnosis cache lookup (question_id + wrong_answer hash)
-- Already exists as idx_ad_cache_lookup from migration 002, but
-- that migration may not have been applied everywhere.
CREATE INDEX IF NOT EXISTS idx_ad_cache_lookup
    ON ai_diagnoses (question_id, md5(wrong_answer))
    WHERE question_id IS NOT NULL;

-- Additional: per-student history queries
CREATE INDEX IF NOT EXISTS idx_ad_student_node
    ON ai_diagnoses (student_id, node_id, created_at DESC)
    WHERE node_id IS NOT NULL;

-- ── spaced_repetitions ────────────────────────────────────────
-- Hot path: "what reviews are due today?" — called on every student login
CREATE INDEX IF NOT EXISTS idx_sr_student_due
    ON spaced_repetitions (student_id, course_id, next_review_date)
    WHERE next_review_date <= CURRENT_DATE;

-- Supporting: stats endpoint
CREATE INDEX IF NOT EXISTS idx_sr_course_date
    ON spaced_repetitions (student_id, course_id, next_review_date);

-- ── flashcard_repetitions ─────────────────────────────────────
-- Hot path: due flashcards query
CREATE INDEX IF NOT EXISTS idx_fcr_student_due
    ON flashcard_repetitions (student_id, course_id, next_review_date)
    WHERE next_review_date <= CURRENT_DATE;

-- ── document_chunks ──────────────────────────────────────────
-- Covering index for content deletion (delete_chunks_for_content)
CREATE INDEX IF NOT EXISTS idx_dc_content_status
    ON document_chunks (content_id, status);

-- Covering index for node chunk count queries
CREATE INDEX IF NOT EXISTS idx_dc_node_status
    ON document_chunks (node_id, status)
    WHERE node_id IS NOT NULL;

-- ── knowledge_nodes ───────────────────────────────────────────
-- Covering index for source content queries (used in title_map builds)
CREATE INDEX IF NOT EXISTS idx_kn_source_content
    ON knowledge_nodes (source_content_id, source_content_title)
    WHERE source_content_id IS NOT NULL;

-- ── ai_quiz_generations ───────────────────────────────────────
-- Draft listing query (course + status + node)
CREATE INDEX IF NOT EXISTS idx_aiqg_course_status_node
    ON ai_quiz_generations (course_id, status, node_id);

-- ── student_knowledge_progress ───────────────────────────────
-- Heatmap query: per-node across all students in a course
CREATE INDEX IF NOT EXISTS idx_skp_node_course
    ON student_knowledge_progress (node_id, course_id);

-- ── content_index_status ─────────────────────────────────────
-- Polling: find unindexed/failed content per course
CREATE INDEX IF NOT EXISTS idx_cis_course_status
    ON content_index_status (course_id, status);

-- ── flashcards ────────────────────────────────────────────────
-- Node + course listing
CREATE INDEX IF NOT EXISTS idx_fc_student_course_node
    ON flashcards (student_id, course_id, node_id)
    WHERE status = 'ACTIVE';

-- =============================================================
-- Verify with:
--   SELECT indexname, tablename
--   FROM pg_indexes
--   WHERE schemaname = 'public'
--     AND indexname LIKE 'idx_%'
--   ORDER BY tablename, indexname;
-- =============================================================
