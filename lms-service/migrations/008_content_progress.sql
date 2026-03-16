-- migrations/008_content_progress.sql
-- Tracks which mandatory content items each student has completed.
-- Progress percent = completed_count / total_mandatory * 100.

CREATE TABLE IF NOT EXISTS content_progress (
    id           BIGSERIAL PRIMARY KEY,
    content_id   BIGINT NOT NULL REFERENCES section_content(id) ON DELETE CASCADE,
    student_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_content_progress_student         ON content_progress(student_id);
CREATE INDEX IF NOT EXISTS idx_content_progress_content         ON content_progress(content_id);
CREATE INDEX IF NOT EXISTS idx_content_progress_student_content ON content_progress(student_id, content_id);