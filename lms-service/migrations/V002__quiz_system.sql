-- ── QUIZZES ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS quizzes (
    id                       BIGSERIAL PRIMARY KEY,
    content_id               BIGINT NOT NULL REFERENCES section_content(id) ON DELETE CASCADE,
    title                    VARCHAR(500) NOT NULL,
    description              TEXT,
    instructions             TEXT,
    time_limit_minutes       INTEGER,
    available_from           TIMESTAMP,
    available_until          TIMESTAMP,
    max_attempts             INTEGER DEFAULT 1,
    shuffle_questions        BOOLEAN DEFAULT false,
    shuffle_answers          BOOLEAN DEFAULT false,
    passing_score            DECIMAL(5,2),
    total_points             DECIMAL(10,2) DEFAULT 100.00,
    auto_grade               BOOLEAN DEFAULT true,
    show_results_immediately BOOLEAN DEFAULT true,
    show_correct_answers     BOOLEAN DEFAULT true,
    allow_review             BOOLEAN DEFAULT true,
    show_feedback            BOOLEAN DEFAULT true,
    is_published             BOOLEAN DEFAULT false,
    created_by               BIGINT NOT NULL REFERENCES users(id),
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quizzes_content   ON quizzes(content_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_published ON quizzes(is_published);
CREATE INDEX IF NOT EXISTS idx_quizzes_available ON quizzes(available_from, available_until);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_quizzes_updated_at'
                   AND tgrelid='quizzes'::regclass) THEN
        CREATE TRIGGER update_quizzes_updated_at
            BEFORE UPDATE ON quizzes
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ── QUIZ QUESTIONS ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS quiz_questions (
    id            BIGSERIAL PRIMARY KEY,
    quiz_id       BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_type VARCHAR(50) NOT NULL CHECK (question_type IN (
                      'SINGLE_CHOICE','MULTIPLE_CHOICE','SHORT_ANSWER','ESSAY',
                      'FILE_UPLOAD','FILL_BLANK_TEXT','FILL_BLANK_DROPDOWN'
                  )),
    question_text TEXT NOT NULL,
    question_html TEXT,
    explanation   TEXT,
    points        DECIMAL(10,2) DEFAULT 10.00,
    order_index   INTEGER NOT NULL,
    settings      JSONB DEFAULT '{}',
    is_required   BOOLEAN DEFAULT true,
    node_id       BIGINT,
    bloom_level   VARCHAR(20) CHECK (bloom_level IN
                      ('remember','understand','apply','analyze','evaluate','create')),
    reference_chunk_id BIGINT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz  ON quiz_questions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_order ON quiz_questions(quiz_id, order_index);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_type  ON quiz_questions(question_type);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_node  ON quiz_questions(node_id)
    WHERE node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quiz_questions_bloom ON quiz_questions(bloom_level)
    WHERE bloom_level IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quiz_questions_settings ON quiz_questions USING gin(settings);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_quiz_questions_updated_at'
                   AND tgrelid='quiz_questions'::regclass) THEN
        CREATE TRIGGER update_quiz_questions_updated_at
            BEFORE UPDATE ON quiz_questions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ── QUIZ ANSWER OPTIONS ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS quiz_answer_options (
    id          BIGSERIAL PRIMARY KEY,
    question_id BIGINT NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    option_html TEXT,
    is_correct  BOOLEAN DEFAULT false,
    order_index INTEGER NOT NULL,
    blank_id    INTEGER,
    settings    JSONB DEFAULT '{}',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_answer_options_question ON quiz_answer_options(question_id);
CREATE INDEX IF NOT EXISTS idx_answer_options_blank    ON quiz_answer_options(question_id, blank_id);
CREATE INDEX IF NOT EXISTS idx_answer_options_blank_id ON quiz_answer_options(blank_id)
    WHERE blank_id IS NOT NULL;

-- ── QUIZ CORRECT ANSWERS ──────────────────────────────────────

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

CREATE INDEX IF NOT EXISTS idx_correct_answers_question ON quiz_correct_answers(question_id);
CREATE INDEX IF NOT EXISTS idx_correct_answers_blank_id ON quiz_correct_answers(blank_id)
    WHERE blank_id IS NOT NULL;

-- ── QUIZ ATTEMPTS ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                 BIGSERIAL PRIMARY KEY,
    quiz_id            BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    student_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_number     INTEGER NOT NULL DEFAULT 1,
    started_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at       TIMESTAMP,
    time_spent_seconds INTEGER,
    total_points       DECIMAL(10,2),
    earned_points      DECIMAL(10,2),
    percentage         DECIMAL(5,2),
    is_passed          BOOLEAN,
    status             VARCHAR(20) DEFAULT 'IN_PROGRESS' CHECK (status IN (
                           'IN_PROGRESS','SUBMITTED','GRADED','ABANDONED'
                       )),
    auto_graded_at     TIMESTAMP,
    manually_graded_at TIMESTAMP,
    graded_by          BIGINT REFERENCES users(id),
    ip_address         VARCHAR(45),
    user_agent         TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quiz_id, student_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz         ON quiz_attempts(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student      ON quiz_attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_status       ON quiz_attempts(status);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_student ON quiz_attempts(quiz_id, student_id);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_quiz_attempts_updated_at'
                   AND tgrelid='quiz_attempts'::regclass) THEN
        CREATE TRIGGER update_quiz_attempts_updated_at
            BEFORE UPDATE ON quiz_attempts
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ── QUIZ STUDENT ANSWERS ──────────────────────────────────────

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

CREATE INDEX IF NOT EXISTS idx_student_answers_attempt  ON quiz_student_answers(attempt_id);
CREATE INDEX IF NOT EXISTS idx_student_answers_question ON quiz_student_answers(question_id);
CREATE INDEX IF NOT EXISTS idx_student_answers_data     ON quiz_student_answers USING gin(answer_data);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_quiz_student_answers_updated_at'
                   AND tgrelid='quiz_student_answers'::regclass) THEN
        CREATE TRIGGER update_quiz_student_answers_updated_at
            BEFORE UPDATE ON quiz_student_answers
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ── QUIZ ANALYTICS ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS quiz_analytics (
    id                BIGSERIAL PRIMARY KEY,
    quiz_id           BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_id       BIGINT REFERENCES quiz_questions(id) ON DELETE CASCADE,
    total_attempts    INTEGER DEFAULT 0,
    correct_count     INTEGER DEFAULT 0,
    incorrect_count   INTEGER DEFAULT 0,
    average_score     DECIMAL(5,2),
    difficulty_rating VARCHAR(20),
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quiz_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_quiz_analytics_quiz     ON quiz_analytics(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_analytics_question ON quiz_analytics(question_id);

-- ── CONTENT PROGRESS ─────────────────────────────────────────

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

-- ── HELPER FUNCTIONS ──────────────────────────────────────────

CREATE OR REPLACE FUNCTION count_question_blanks(question_text TEXT)
RETURNS INTEGER AS $$
DECLARE blank_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO blank_count
    FROM regexp_matches(question_text, '\{BLANK_\d+\}', 'g');
    RETURN COALESCE(blank_count, 0);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION calculate_attempt_score(p_attempt_id BIGINT)
RETURNS void AS $$
DECLARE
    v_total_points  DECIMAL(10,2);
    v_earned_points DECIMAL(10,2);
    v_percentage    DECIMAL(5,2);
    v_passing_score DECIMAL(5,2);
BEGIN
    SELECT SUM(qq.points), SUM(COALESCE(qsa.points_earned, 0))
    INTO   v_total_points, v_earned_points
    FROM   quiz_student_answers qsa
    JOIN   quiz_questions qq ON qsa.question_id = qq.id
    WHERE  qsa.attempt_id = p_attempt_id;

    v_percentage := (v_earned_points / NULLIF(v_total_points, 0)) * 100;

    SELECT q.passing_score INTO v_passing_score
    FROM   quizzes q JOIN quiz_attempts qa ON q.id = qa.quiz_id
    WHERE  qa.id = p_attempt_id;

    UPDATE quiz_attempts
    SET    total_points  = v_total_points,
           earned_points = v_earned_points,
           percentage    = v_percentage,
           is_passed     = (v_percentage >= COALESCE(v_passing_score, 0)),
           status        = 'GRADED',
           updated_at    = CURRENT_TIMESTAMP
    WHERE  id = p_attempt_id;
END;
$$ LANGUAGE plpgsql;

-- ── VIEWS ─────────────────────────────────────────────────────

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
