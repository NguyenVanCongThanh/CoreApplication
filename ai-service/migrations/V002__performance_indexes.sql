-- ── ai_diagnoses ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ad_student_node
    ON ai_diagnoses (student_id, node_id, created_at DESC)
    WHERE node_id IS NOT NULL;

-- ── spaced_repetitions ────────────────────────────────────────
-- Hot path: "what reviews are due today?" — called on every student login
CREATE INDEX IF NOT EXISTS idx_sr_student_due_today
    ON spaced_repetitions (student_id, course_id, next_review_date)
    INCLUDE (question_id, easiness_factor, interval_days, repetitions)
    WHERE next_review_date <= CURRENT_DATE;

CREATE INDEX IF NOT EXISTS idx_sr_course_date
    ON spaced_repetitions (student_id, course_id, next_review_date);

-- ── flashcard_repetitions ─────────────────────────────────────
-- Hot path: "what flashcards are due today?"
CREATE INDEX IF NOT EXISTS idx_fcr_student_due_today
    ON flashcard_repetitions (student_id, course_id, next_review_date)
    INCLUDE (flashcard_id, easiness_factor, interval_days, repetitions)
    WHERE next_review_date <= CURRENT_DATE;

-- ── document_chunks ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_dc_content_status
    ON document_chunks (content_id, status);

CREATE INDEX IF NOT EXISTS idx_dc_node_status
    ON document_chunks (node_id, status)
    WHERE node_id IS NOT NULL;

-- ── knowledge_nodes ───────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_kn_source_content
    ON knowledge_nodes (source_content_id, source_content_title)
    WHERE source_content_id IS NOT NULL;

-- ── ai_quiz_generations ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_aiqg_course_status_node
    ON ai_quiz_generations (course_id, status, node_id);

-- ── student_knowledge_progress ───────────────────────────────
CREATE INDEX IF NOT EXISTS idx_skp_node_course
    ON student_knowledge_progress (node_id, course_id);

-- ── content_index_status ─────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_cis_course_status
    ON content_index_status (course_id, status);

-- ── flashcards ────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_fc_student_course_node
    ON flashcards (student_id, course_id, node_id)
    WHERE status = 'ACTIVE';

-- ── Analyze updated tables so planner picks up new indexes immediately ────────
ANALYZE ai_diagnoses;
ANALYZE spaced_repetitions;
ANALYZE flashcard_repetitions;
ANALYZE document_chunks;
ANALYZE knowledge_nodes;
ANALYZE ai_quiz_generations;
ANALYZE student_knowledge_progress;
ANALYZE content_index_status;
ANALYZE flashcards;
