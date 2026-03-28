-- ============================================================
-- QUIZZES
-- ============================================================

CREATE TABLE IF NOT EXISTS quizzes (
    id                       BIGSERIAL PRIMARY KEY,
    content_id               BIGINT NOT NULL REFERENCES section_content(id) ON DELETE CASCADE,
    title                    VARCHAR(500) NOT NULL,
    description              TEXT,
    instructions             TEXT,
    -- Timing
    time_limit_minutes       INTEGER,        -- NULL = unlimited
    available_from           TIMESTAMP,
    available_until          TIMESTAMP,
    -- Attempt limits
    max_attempts             INTEGER DEFAULT 1,   -- NULL = unlimited
    shuffle_questions        BOOLEAN DEFAULT false,
    shuffle_answers          BOOLEAN DEFAULT false,
    -- Grading
    passing_score            DECIMAL(5,2),
    total_points             DECIMAL(10,2) DEFAULT 100.00,
    auto_grade               BOOLEAN DEFAULT true,
    -- Display
    show_results_immediately BOOLEAN DEFAULT true,
    show_correct_answers     BOOLEAN DEFAULT true,
    allow_review             BOOLEAN DEFAULT true,
    show_feedback            BOOLEAN DEFAULT true,
    -- Status
    is_published             BOOLEAN DEFAULT false,
    created_by               BIGINT NOT NULL REFERENCES users(id),
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quizzes_content   ON quizzes(content_id);
CREATE INDEX idx_quizzes_published ON quizzes(is_published);
CREATE INDEX idx_quizzes_available ON quizzes(available_from, available_until);

CREATE TRIGGER update_quizzes_updated_at
    BEFORE UPDATE ON quizzes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- QUIZ QUESTIONS
-- Supported types:
--   SINGLE_CHOICE      — one correct option
--   MULTIPLE_CHOICE    — many correct options
--   SHORT_ANSWER       — short text (word limit via settings)
--   ESSAY              — long text, manual grading
--   FILE_UPLOAD        — file attachment
--   FILL_BLANK_TEXT    — fill in blanks, text input
--   FILL_BLANK_DROPDOWN— fill in blanks, dropdown options
-- ============================================================

CREATE TABLE IF NOT EXISTS quiz_questions (
    id            BIGSERIAL PRIMARY KEY,
    quiz_id       BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_type VARCHAR(50) NOT NULL CHECK (question_type IN (
                      'SINGLE_CHOICE', 'MULTIPLE_CHOICE', 'SHORT_ANSWER', 'ESSAY',
                      'FILE_UPLOAD', 'FILL_BLANK_TEXT', 'FILL_BLANK_DROPDOWN'
                  )),
    question_text TEXT NOT NULL,
    question_html TEXT,
    explanation   TEXT,   -- feedback/explanation shown after submission
    points        DECIMAL(10,2) DEFAULT 10.00,
    order_index   INTEGER NOT NULL,
    -- Type-specific settings (JSONB for flexibility)
    -- SHORT_ANSWER:      {"max_words": 100, "case_sensitive": false}
    -- FILE_UPLOAD:       {"allowed_types": ["pdf","docx"], "max_size_mb": 10}
    -- FILL_BLANK_TEXT:   {"blank_count": 2}
    -- FILL_BLANK_DROPDOWN:{"blank_count": 2}
    settings      JSONB DEFAULT '{}',
    is_required   BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quiz_questions_quiz     ON quiz_questions(quiz_id);
CREATE INDEX idx_quiz_questions_order    ON quiz_questions(quiz_id, order_index);
CREATE INDEX idx_quiz_questions_type     ON quiz_questions(question_type);
CREATE INDEX idx_quiz_questions_settings ON quiz_questions USING gin(settings);

CREATE TRIGGER update_quiz_questions_updated_at
    BEFORE UPDATE ON quiz_questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- QUIZ ANSWER OPTIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS quiz_answer_options (
    id          BIGSERIAL PRIMARY KEY,
    question_id BIGINT NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    option_html TEXT,
    is_correct  BOOLEAN DEFAULT false,
    order_index INTEGER NOT NULL,
    blank_id    INTEGER,     -- non-null for FILL_BLANK_DROPDOWN options
    settings    JSONB DEFAULT '{}',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_answer_options_question ON quiz_answer_options(question_id);
CREATE INDEX idx_answer_options_blank    ON quiz_answer_options(question_id, blank_id);
CREATE INDEX idx_answer_options_blank_id ON quiz_answer_options(blank_id) WHERE blank_id IS NOT NULL;
CREATE INDEX idx_answer_options_settings ON quiz_answer_options USING gin(settings);

-- ============================================================
-- QUIZ CORRECT ANSWERS  (text / fill-blank questions)
-- ============================================================

CREATE TABLE IF NOT EXISTS quiz_correct_answers (
    id             BIGSERIAL PRIMARY KEY,
    question_id    BIGINT NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    answer_text    TEXT,
    blank_id       INTEGER,
    blank_position INTEGER,
    case_sensitive BOOLEAN DEFAULT false,
    exact_match    BOOLEAN DEFAULT false,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_correct_answers_question ON quiz_correct_answers(question_id);
CREATE INDEX idx_correct_answers_blank_id ON quiz_correct_answers(blank_id) WHERE blank_id IS NOT NULL;

-- ============================================================
-- QUIZ ATTEMPTS
-- ============================================================

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                 BIGSERIAL PRIMARY KEY,
    quiz_id            BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    student_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_number     INTEGER NOT NULL DEFAULT 1,
    -- Timing
    started_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at       TIMESTAMP,
    time_spent_seconds INTEGER,
    -- Score
    total_points       DECIMAL(10,2),
    earned_points      DECIMAL(10,2),
    percentage         DECIMAL(5,2),
    is_passed          BOOLEAN,
    -- Status
    status             VARCHAR(20) DEFAULT 'IN_PROGRESS' CHECK (status IN (
                           'IN_PROGRESS', 'SUBMITTED', 'GRADED', 'ABANDONED'
                       )),
    -- Grading
    auto_graded_at     TIMESTAMP,
    manually_graded_at TIMESTAMP,
    graded_by          BIGINT REFERENCES users(id),
    -- Meta
    ip_address         VARCHAR(45),
    user_agent         TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quiz_id, student_id, attempt_number)
);

CREATE INDEX idx_quiz_attempts_quiz         ON quiz_attempts(quiz_id);
CREATE INDEX idx_quiz_attempts_student      ON quiz_attempts(student_id);
CREATE INDEX idx_quiz_attempts_status       ON quiz_attempts(status);
CREATE INDEX idx_quiz_attempts_quiz_student ON quiz_attempts(quiz_id, student_id);

CREATE TRIGGER update_quiz_attempts_updated_at
    BEFORE UPDATE ON quiz_attempts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- QUIZ STUDENT ANSWERS
-- answer_data JSONB layout by type:
--   SINGLE_CHOICE:       {"selected_option_id": 123}
--   MULTIPLE_CHOICE:     {"selected_option_ids": [123, 456]}
--   SHORT_ANSWER/ESSAY:  {"text": "..."}
--   FILE_UPLOAD:         {"file_path": "...", "file_name": "...", "file_size": 1024}
--   FILL_BLANK_TEXT:     {"blanks": [{"blank_id": 1, "answer": "text"}]}
--   FILL_BLANK_DROPDOWN: {"blanks": [{"blank_id": 1, "selected_option_id": 789}]}
-- ============================================================

CREATE TABLE IF NOT EXISTS quiz_student_answers (
    id                 BIGSERIAL PRIMARY KEY,
    attempt_id         BIGINT NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id        BIGINT NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    answer_data        JSONB NOT NULL,
    points_earned      DECIMAL(10,2),
    is_correct         BOOLEAN,
    grader_feedback    TEXT,
    graded_by          BIGINT REFERENCES users(id),
    graded_at          TIMESTAMP,
    answered_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_spent_seconds INTEGER,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(attempt_id, question_id)
);

CREATE INDEX idx_student_answers_attempt  ON quiz_student_answers(attempt_id);
CREATE INDEX idx_student_answers_question ON quiz_student_answers(question_id);
CREATE INDEX idx_student_answers_grading  ON quiz_student_answers(graded_by) WHERE graded_by IS NOT NULL;
CREATE INDEX idx_student_answers_data     ON quiz_student_answers USING gin(answer_data);

CREATE TRIGGER update_quiz_student_answers_updated_at
    BEFORE UPDATE ON quiz_student_answers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- QUIZ ANALYTICS  (teacher insights)
-- ============================================================

CREATE TABLE IF NOT EXISTS quiz_analytics (
    id                BIGSERIAL PRIMARY KEY,
    quiz_id           BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_id       BIGINT REFERENCES quiz_questions(id) ON DELETE CASCADE,
    total_attempts    INTEGER DEFAULT 0,
    correct_count     INTEGER DEFAULT 0,
    incorrect_count   INTEGER DEFAULT 0,
    average_score     DECIMAL(5,2),
    difficulty_rating VARCHAR(20),   -- EASY | MEDIUM | HARD
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quiz_id, question_id)
);

CREATE INDEX idx_quiz_analytics_quiz     ON quiz_analytics(quiz_id);
CREATE INDEX idx_quiz_analytics_question ON quiz_analytics(question_id);

-- ============================================================
-- CONTENT PROGRESS
-- ============================================================

CREATE TABLE IF NOT EXISTS content_progress (
    id           BIGSERIAL PRIMARY KEY,
    content_id   BIGINT NOT NULL REFERENCES section_content(id) ON DELETE CASCADE,
    student_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_id, student_id)
);

CREATE INDEX idx_content_progress_student         ON content_progress(student_id);
CREATE INDEX idx_content_progress_content         ON content_progress(content_id);
CREATE INDEX idx_content_progress_student_content ON content_progress(student_id, content_id);

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Count images embedded in a question's settings JSONB
CREATE OR REPLACE FUNCTION count_question_images(question_settings JSONB)
RETURNS INTEGER AS $$
BEGIN
    RETURN jsonb_array_length(COALESCE(question_settings -> 'images', '[]'::jsonb));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Auto-grade a single student answer (objective question types only)
CREATE OR REPLACE FUNCTION auto_grade_quiz_answer(p_answer_id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    v_question_type VARCHAR(50);
    v_answer_data   JSONB;
    v_is_correct    BOOLEAN;
    v_points        DECIMAL(10,2);
BEGIN
    SELECT qq.question_type, qq.points, qsa.answer_data
    INTO   v_question_type, v_points, v_answer_data
    FROM   quiz_student_answers qsa
    JOIN   quiz_questions qq ON qsa.question_id = qq.id
    WHERE  qsa.id = p_answer_id;

    IF v_question_type = 'SINGLE_CHOICE' THEN
        SELECT qao.is_correct INTO v_is_correct
        FROM   quiz_answer_options qao
        WHERE  qao.id = (v_answer_data ->> 'selected_option_id')::BIGINT;

    ELSIF v_question_type = 'MULTIPLE_CHOICE' THEN
        WITH selected AS (
            SELECT jsonb_array_elements_text(v_answer_data -> 'selected_option_ids')::BIGINT AS option_id
        ),
        correct_options AS (
            SELECT id FROM quiz_answer_options
            WHERE  question_id = (SELECT question_id FROM quiz_student_answers WHERE id = p_answer_id)
              AND  is_correct = true
        )
        SELECT (
            (SELECT COUNT(*) FROM selected WHERE option_id IN (SELECT id FROM correct_options))
            = (SELECT COUNT(*) FROM correct_options)
        ) AND (
            (SELECT COUNT(*) FROM selected)
            = (SELECT COUNT(*) FROM correct_options)
        ) INTO v_is_correct;

    ELSIF v_question_type = 'FILL_BLANK_TEXT' THEN
        -- Placeholder: implement custom matching logic per project rules
        v_is_correct := true;

    ELSE
        -- ESSAY, FILE_UPLOAD, SHORT_ANSWER: requires manual grading
        RETURN false;
    END IF;

    UPDATE quiz_student_answers
    SET    is_correct    = v_is_correct,
           points_earned = CASE WHEN v_is_correct THEN v_points ELSE 0 END
    WHERE  id = p_answer_id;

    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- Calculate and persist total score for a quiz attempt
CREATE OR REPLACE FUNCTION calculate_attempt_score(p_attempt_id BIGINT)
RETURNS void AS $$
DECLARE
    v_total_points  DECIMAL(10,2);
    v_earned_points DECIMAL(10,2);
    v_percentage    DECIMAL(5,2);
    v_passing_score DECIMAL(5,2);
    v_is_passed     BOOLEAN;
BEGIN
    SELECT SUM(qq.points), SUM(COALESCE(qsa.points_earned, 0))
    INTO   v_total_points, v_earned_points
    FROM   quiz_student_answers qsa
    JOIN   quiz_questions qq ON qsa.question_id = qq.id
    WHERE  qsa.attempt_id = p_attempt_id;

    v_percentage := (v_earned_points / NULLIF(v_total_points, 0)) * 100;

    SELECT q.passing_score INTO v_passing_score
    FROM   quizzes q
    JOIN   quiz_attempts qa ON q.id = qa.quiz_id
    WHERE  qa.id = p_attempt_id;

    v_is_passed := v_percentage >= COALESCE(v_passing_score, 0);

    UPDATE quiz_attempts
    SET    total_points  = v_total_points,
           earned_points = v_earned_points,
           percentage    = v_percentage,
           is_passed     = v_is_passed,
           status        = 'GRADED',
           updated_at    = CURRENT_TIMESTAMP
    WHERE  id = p_attempt_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- FILL-BLANK HELPER FUNCTION
-- ============================================================

-- Count {BLANK_N} placeholders in question text
CREATE OR REPLACE FUNCTION count_question_blanks(question_text TEXT)
RETURNS INTEGER AS $$
DECLARE
    blank_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO blank_count
    FROM   regexp_matches(question_text, '\{BLANK_\d+\}', 'g');
    RETURN COALESCE(blank_count, 0);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Extract unique, sorted blank IDs from question text
CREATE OR REPLACE FUNCTION extract_blank_ids(question_text TEXT)
RETURNS INTEGER[] AS $$
DECLARE
    blank_ids INTEGER[];
    matches   TEXT[];
BEGIN
    SELECT array_agg(match[1]) INTO matches
    FROM   regexp_matches(question_text, '\{BLANK_(\d+)\}', 'g') AS match;

    IF matches IS NULL THEN
        RETURN ARRAY[]::INTEGER[];
    END IF;

    SELECT array_agg(DISTINCT m::INTEGER ORDER BY m::INTEGER)
    INTO   blank_ids
    FROM   unnest(matches) AS m;

    RETURN COALESCE(blank_ids, ARRAY[]::INTEGER[]);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Validate a FILL_BLANK_TEXT question
CREATE OR REPLACE FUNCTION validate_fill_blank_text_question(question_id BIGINT)
RETURNS TABLE (is_valid BOOLEAN, error_message TEXT) AS $$
DECLARE
    q_text               TEXT;
    q_settings           JSONB;
    blank_count          INTEGER;
    expected_blank_count INTEGER;
    blank_ids            INTEGER[];
    missing_answers      INTEGER[];
BEGIN
    SELECT question_text, settings
    INTO   q_text, q_settings
    FROM   quiz_questions
    WHERE  id = question_id AND question_type = 'FILL_BLANK_TEXT';

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Question not found or not FILL_BLANK_TEXT type';
        RETURN;
    END IF;

    blank_count          := count_question_blanks(q_text);
    expected_blank_count := (q_settings ->> 'blank_count')::INTEGER;

    IF blank_count = 0 THEN
        RETURN QUERY SELECT FALSE, 'No blanks found in question text';
        RETURN;
    END IF;

    IF blank_count <> expected_blank_count THEN
        RETURN QUERY SELECT FALSE,
            format('Blank count mismatch: found %s, expected %s', blank_count, expected_blank_count);
        RETURN;
    END IF;

    blank_ids := extract_blank_ids(q_text);

    SELECT array_agg(bid) INTO missing_answers
    FROM   unnest(blank_ids) AS bid
    WHERE  NOT EXISTS (
        SELECT 1 FROM quiz_correct_answers
        WHERE  question_id = validate_fill_blank_text_question.question_id
          AND  blank_id   = bid
          AND  answer_text IS NOT NULL AND answer_text <> ''
    );

    IF missing_answers IS NOT NULL AND array_length(missing_answers, 1) > 0 THEN
        RETURN QUERY SELECT FALSE,
            format('Missing correct answers for blanks: %s', array_to_string(missing_answers, ', '));
        RETURN;
    END IF;

    RETURN QUERY SELECT TRUE, 'Valid'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Validate a FILL_BLANK_DROPDOWN question
CREATE OR REPLACE FUNCTION validate_fill_blank_dropdown_question(question_id BIGINT)
RETURNS TABLE (is_valid BOOLEAN, error_message TEXT) AS $$
DECLARE
    q_text               TEXT;
    q_settings           JSONB;
    blank_count          INTEGER;
    expected_blank_count INTEGER;
    blank_ids            INTEGER[];
    bid                  INTEGER;
    option_count         INTEGER;
    correct_count        INTEGER;
BEGIN
    SELECT question_text, settings
    INTO   q_text, q_settings
    FROM   quiz_questions
    WHERE  id = question_id AND question_type = 'FILL_BLANK_DROPDOWN';

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Question not found or not FILL_BLANK_DROPDOWN type';
        RETURN;
    END IF;

    blank_count          := count_question_blanks(q_text);
    expected_blank_count := (q_settings ->> 'blank_count')::INTEGER;

    IF blank_count = 0 THEN
        RETURN QUERY SELECT FALSE, 'No blanks found in question text';
        RETURN;
    END IF;

    IF blank_count <> expected_blank_count THEN
        RETURN QUERY SELECT FALSE,
            format('Blank count mismatch: found %s, expected %s', blank_count, expected_blank_count);
        RETURN;
    END IF;

    blank_ids := extract_blank_ids(q_text);

    FOREACH bid IN ARRAY blank_ids LOOP
        SELECT COUNT(*) INTO option_count
        FROM   quiz_answer_options
        WHERE  question_id = validate_fill_blank_dropdown_question.question_id
          AND  blank_id    = bid;

        IF option_count < 2 THEN
            RETURN QUERY SELECT FALSE,
                format('Blank %s has fewer than 2 options (%s found)', bid, option_count);
            RETURN;
        END IF;

        SELECT COUNT(*) INTO correct_count
        FROM   quiz_answer_options
        WHERE  question_id = validate_fill_blank_dropdown_question.question_id
          AND  blank_id    = bid
          AND  is_correct  = true;

        IF correct_count = 0 THEN
            RETURN QUERY SELECT FALSE, format('Blank %s has no correct answer', bid);
            RETURN;
        END IF;

        IF correct_count > 1 THEN
            RETURN QUERY SELECT FALSE,
                format('Blank %s has multiple correct answers (%s found)', bid, correct_count);
            RETURN;
        END IF;
    END LOOP;

    RETURN QUERY SELECT TRUE, 'Valid'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- VIEWS
-- ============================================================

CREATE OR REPLACE VIEW quiz_summary_view AS
SELECT
    q.*,
    u.full_name                                                  AS creator_name,
    u.email                                                      AS creator_email,
    COUNT(DISTINCT qq.id)                                        AS question_count,
    COUNT(DISTINCT qa.id)                                        AS attempt_count,
    COUNT(DISTINCT qa.student_id)                                AS student_count,
    AVG(qa.percentage)                                           AS average_score,
    COUNT(DISTINCT qa.id) FILTER (WHERE qa.is_passed = true)     AS passed_count
FROM       quizzes q
LEFT JOIN  users           u  ON q.created_by = u.id
LEFT JOIN  quiz_questions  qq ON q.id = qq.quiz_id
LEFT JOIN  quiz_attempts   qa ON q.id = qa.quiz_id AND qa.status = 'GRADED'
GROUP BY   q.id, u.full_name, u.email;

CREATE OR REPLACE VIEW student_quiz_attempts_view AS
SELECT
    qa.*,
    q.title                                                       AS quiz_title,
    q.total_points                                                AS quiz_total_points,
    q.passing_score,
    u.full_name                                                   AS student_name,
    u.email                                                       AS student_email,
    COUNT(qsa.id)                                                 AS answered_questions,
    COUNT(qsa.id) FILTER (WHERE qsa.is_correct = true)            AS correct_answers
FROM       quiz_attempts        qa
JOIN       quizzes              q   ON qa.quiz_id    = q.id
JOIN       users                u   ON qa.student_id = u.id
LEFT JOIN  quiz_student_answers qsa ON qa.id         = qsa.attempt_id
GROUP BY   qa.id, q.title, q.total_points, q.passing_score, u.full_name, u.email;

CREATE OR REPLACE VIEW v_fill_blank_questions_status AS
SELECT
    q.id,
    q.quiz_id,
    q.question_type,
    q.question_text,
    q.settings,
    count_question_blanks(q.question_text)                          AS detected_blank_count,
    (q.settings ->> 'blank_count')::INTEGER                        AS expected_blank_count,
    CASE
        WHEN q.question_type = 'FILL_BLANK_TEXT'
            THEN (SELECT is_valid      FROM validate_fill_blank_text_question(q.id))
        WHEN q.question_type = 'FILL_BLANK_DROPDOWN'
            THEN (SELECT is_valid      FROM validate_fill_blank_dropdown_question(q.id))
    END AS is_valid,
    CASE
        WHEN q.question_type = 'FILL_BLANK_TEXT'
            THEN (SELECT error_message FROM validate_fill_blank_text_question(q.id))
        WHEN q.question_type = 'FILL_BLANK_DROPDOWN'
            THEN (SELECT error_message FROM validate_fill_blank_dropdown_question(q.id))
    END AS validation_message
FROM quiz_questions q
WHERE q.question_type IN ('FILL_BLANK_TEXT', 'FILL_BLANK_DROPDOWN');

-- ============================================================
-- TABLE COMMENTS
-- ============================================================

COMMENT ON TABLE quizzes              IS 'Quiz configurations and settings';
COMMENT ON TABLE quiz_questions       IS 'Questions within quizzes — supports multiple question types';
COMMENT ON TABLE quiz_answer_options  IS 'Answer options for choice-based and fill-blank-dropdown questions';
COMMENT ON TABLE quiz_correct_answers IS 'Correct answers for text and fill-in-the-blank questions';
COMMENT ON TABLE quiz_attempts        IS 'Student quiz attempts';
COMMENT ON TABLE quiz_student_answers IS 'Student answers per question per attempt';
COMMENT ON TABLE quiz_analytics       IS 'Aggregated analytics per question for teacher insights';
COMMENT ON TABLE content_progress     IS 'Mandatory content completion per student; progress % = completed / total_mandatory * 100';
