-- ============================================================
-- Migration 013: Fix knowledge progress trigger function
-- BUG: CTE referenced undefined alias "sc2", causing:
--   pq: missing FROM-clause entry for table "sc2" (42P01)
-- IMPACT: All quiz auto-grading silently failed on production
--         because UpdateStudentAnswer was rolled back by trigger error.
-- ============================================================

-- STEP 1: Fix the trigger function (remove dead CTE with bad alias)
CREATE OR REPLACE FUNCTION update_knowledge_progress_on_answer()
RETURNS TRIGGER AS $$
BEGIN
    -- Only process when is_correct is set (auto or manual graded)
    IF NEW.is_correct IS NULL THEN
        RETURN NEW;
    END IF;

    -- Update knowledge progress if question is linked to a knowledge node
    INSERT INTO student_knowledge_progress (student_id, node_id, course_id, total_attempts, correct_count, wrong_count, mastery_level, last_tested_at)
    SELECT
        qa.student_id,
        qq.node_id,
        cs2.course_id,
        1,
        CASE WHEN NEW.is_correct THEN 1 ELSE 0 END,
        CASE WHEN NEW.is_correct THEN 0 ELSE 1 END,
        CASE WHEN NEW.is_correct THEN 0.6 ELSE 0.0 END,
        NOW()
    FROM quiz_student_answers qsa2
    JOIN quiz_questions qq ON qq.id = NEW.question_id
    JOIN quiz_attempts qa ON qa.id = NEW.attempt_id
    JOIN quizzes qz ON qz.id = qa.quiz_id
    JOIN section_content sc ON sc.id = qz.content_id
    JOIN course_sections cs2 ON cs2.id = sc.section_id
    WHERE qsa2.id = NEW.id AND qq.node_id IS NOT NULL
    ON CONFLICT (student_id, node_id) DO UPDATE SET
        total_attempts  = student_knowledge_progress.total_attempts + 1,
        correct_count   = student_knowledge_progress.correct_count + CASE WHEN NEW.is_correct THEN 1 ELSE 0 END,
        wrong_count     = student_knowledge_progress.wrong_count   + CASE WHEN NEW.is_correct THEN 0 ELSE 1 END,
        mastery_level   = LEAST(1.0, (student_knowledge_progress.correct_count + CASE WHEN NEW.is_correct THEN 1 ELSE 0 END)::FLOAT
                          / NULLIF(student_knowledge_progress.total_attempts + 1, 0)),
        last_tested_at  = NOW(),
        updated_at      = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- STEP 2: Re-grade all affected quiz answers
-- These are SINGLE_CHOICE answers that were never graded due to the trigger bug
UPDATE quiz_student_answers
SET
    is_correct = qao.is_correct,
    points_earned = CASE WHEN qao.is_correct THEN qq.points ELSE 0 END,
    graded_at = NOW(),
    updated_at = NOW()
FROM quiz_questions qq
JOIN quiz_answer_options qao
    ON qao.id = (quiz_student_answers.answer_data->>'selected_option_id')::BIGINT
WHERE quiz_student_answers.question_id = qq.id
  AND qq.question_type = 'SINGLE_CHOICE'
  AND quiz_student_answers.is_correct IS NULL
  AND quiz_student_answers.points_earned IS NULL;

-- STEP 3: Recalculate attempt scores for affected attempts
UPDATE quiz_attempts qa
SET
    earned_points = sub.earned,
    total_points  = sub.total,
    percentage    = CASE WHEN sub.total > 0 THEN (sub.earned / sub.total) * 100 ELSE 0 END,
    is_passed     = CASE WHEN sub.total > 0 THEN (sub.earned / sub.total) * 100 >= COALESCE(sub.passing, 0) ELSE false END,
    status        = 'GRADED',
    updated_at    = NOW()
FROM (
    SELECT
        qa2.id AS attempt_id,
        SUM(qq.points) AS total,
        SUM(COALESCE(qsa.points_earned, 0)) AS earned,
        q.passing_score AS passing
    FROM quiz_attempts qa2
    JOIN quizzes q ON q.id = qa2.quiz_id
    JOIN quiz_student_answers qsa ON qsa.attempt_id = qa2.id
    JOIN quiz_questions qq ON qq.id = qsa.question_id
    WHERE qa2.id IN (4, 5)  -- affected attempt IDs
    GROUP BY qa2.id, q.passing_score
) sub
WHERE qa.id = sub.attempt_id;

-- ============================================================
-- VERIFICATION
-- ============================================================
-- SELECT qa.id, qa.status, qa.earned_points, qa.percentage, qa.is_passed
-- FROM quiz_attempts WHERE id IN (4, 5);
--
-- SELECT qsa.id, qsa.is_correct, qsa.points_earned
-- FROM quiz_student_answers qsa WHERE qsa.attempt_id IN (4, 5);
