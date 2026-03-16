-- migrations/009_auto_mark_quiz_completion.sql
-- Auto-mark quiz content items as completed when student submits/grades the quiz.
-- This backfills existing quiz attempts that have already been submitted.

-- ============================================
-- BACKFILL: Mark existing quiz submissions as completed
-- ============================================
-- For all submitted/graded quiz attempts, mark their quiz content item as completed

INSERT INTO content_progress (content_id, student_id, completed_at)
SELECT 
    q.content_id,
    qa.student_id,
    qa.submitted_at::timestamp AS completed_at
FROM quiz_attempts qa
JOIN quizzes q ON q.id = qa.quiz_id
WHERE qa.status IN ('SUBMITTED', 'GRADED')
  AND qa.submitted_at IS NOT NULL
  -- Only mark mandatory content (content_id must reference a content item)
  AND q.content_id IS NOT NULL
  -- Avoid duplicates (idempotent due to UNIQUE constraint)
ON CONFLICT (content_id, student_id) DO NOTHING;

-- ============================================
-- NOTE: Going forward, the backend will automatically mark quiz content as completed
-- when a student submits the quiz. No additional migration needed.
-- ============================================
