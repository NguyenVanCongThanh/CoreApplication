-- =============================================================================
-- V005__performance_indexes.sql
-- =============================================================================

-- ── quiz_student_answers ──────────────────────────────────────────────────────
-- Used by: calculateAttemptScore, GetQuizWrongAnswerStats, BulkGrade
-- Pattern: filter by attempt_id + look up is_correct for scoring

CREATE INDEX IF NOT EXISTS idx_student_answers_attempt_grading
    ON quiz_student_answers(attempt_id, is_correct, points_earned)
    WHERE is_correct IS NOT NULL;

-- Used by: GetAnswersForGrading (teacher grading view)
-- Pattern: filter ungraded essays/short answers across a quiz
CREATE INDEX IF NOT EXISTS idx_student_answers_ungraded
    ON quiz_student_answers(attempt_id, question_id)
    WHERE points_earned IS NULL;

-- ── content_progress ─────────────────────────────────────────────────────────
-- Used by: GetCourseProgress, GetCourseStudentProgressOverview
-- Pattern: JOIN section_content on content_id + filter student_id

CREATE INDEX IF NOT EXISTS idx_content_progress_content_student
    ON content_progress(content_id, student_id)
    INCLUDE (completed_at);

-- Used by: GetBatchCourseProgress (new batch method for Fix #1)
-- Pattern: filter student across multiple courses at once
CREATE INDEX IF NOT EXISTS idx_content_progress_student_course
    ON content_progress(student_id, content_id);

-- ── quiz_attempts ─────────────────────────────────────────────────────────────
-- Used by: GetCourseQuizAnalytics, GetQuizAllAttempts
-- Pattern: filter submitted/graded attempts for analytics
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_analytics
    ON quiz_attempts(quiz_id, student_id, status, percentage, is_passed)
    WHERE status IN ('SUBMITTED', 'GRADED');

-- Used by: GetStudentQuizScores (per-student per-course query)
-- Pattern: look up best attempt per quiz for a student
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_status
    ON quiz_attempts(student_id, quiz_id, status, submitted_at)
    WHERE status IN ('SUBMITTED', 'GRADED');

-- ── enrollments ──────────────────────────────────────────────────────────────
-- Used by: GetCourseStudentProgressOverview (joins enrollments → users → content)
-- Pattern: fetch all accepted students for a course in one shot
CREATE INDEX IF NOT EXISTS idx_enrollments_course_accepted
    ON enrollments(course_id, student_id)
    WHERE status = 'ACCEPTED';

-- ── section_content ──────────────────────────────────────────────────────────
-- Used by: GetBatchCourseProgress — resolve course_id for many content_ids
-- Pattern: JOIN course_sections on section_id
CREATE INDEX IF NOT EXISTS idx_section_content_section_mandatory
    ON section_content(section_id, id, is_mandatory)
    WHERE is_mandatory = true;

-- ── quiz_questions ────────────────────────────────────────────────────────────
-- Used by: calculateAttemptScore batch path (GetQuestionsByIDs)
-- Pattern: fetch many questions by their IDs (pq.Array)
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz_order
    ON quiz_questions(quiz_id, order_index)
    INCLUDE (points, question_type, node_id);

-- ── forum_posts ──────────────────────────────────────────────────────────────
-- Used by: ListPosts with vote-sort
-- Pattern: ORDER BY (upvotes - downvotes) DESC — needs expression index
CREATE INDEX IF NOT EXISTS idx_forum_posts_score
    ON forum_posts(content_id, (upvotes - downvotes) DESC, created_at DESC)
    WHERE is_pinned = false;

-- ── Analyze updated tables so planner picks up new indexes immediately ────────
ANALYZE quiz_student_answers;
ANALYZE content_progress;
ANALYZE quiz_attempts;
ANALYZE enrollments;
ANALYZE section_content;
ANALYZE quiz_questions;
ANALYZE forum_posts;