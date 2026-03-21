-- ============================================================
-- Migration 010: AI Knowledge Graph & RAG Infrastructure
-- Phase 1 & 2: Error Diagnosis + Smart Quiz
-- ============================================================

-- Enable pgvector extension (MUST be run as superuser if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- KNOWLEDGE NODES (Atomic learning units — "Mắt xích kiến thức")
-- ============================================================
-- Each course is decomposed into a tree of knowledge nodes.
-- Example: "Data Structures" → "Array" → "Dynamic Array"
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id          BIGSERIAL PRIMARY KEY,
    course_id   BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    parent_id   BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    name        VARCHAR(255) NOT NULL,             -- e.g., "Mảng động (Dynamic Array)"
    name_vi     VARCHAR(255),                       -- Vietnamese name
    name_en     VARCHAR(255),                       -- English name
    description TEXT,
    level       INTEGER DEFAULT 0,                  -- depth in the tree
    order_index INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_nodes_course  ON knowledge_nodes(course_id);
CREATE INDEX idx_knowledge_nodes_parent  ON knowledge_nodes(parent_id);
CREATE INDEX idx_knowledge_nodes_level   ON knowledge_nodes(course_id, level);

-- ============================================================
-- DOCUMENT CHUNKS (RAG heart — "Trái tim của RAG")
-- ============================================================
-- Each PDF page or video segment is a chunk with its embedding vector.
-- Deep Link: page_number for PDF, start_time_sec for video.
CREATE TABLE IF NOT EXISTS document_chunks (
    id              BIGSERIAL PRIMARY KEY,
    node_id         BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    content_id      BIGINT REFERENCES section_content(id) ON DELETE CASCADE,
    course_id       BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,

    -- Chunk text (500–1000 chars)
    chunk_text      TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,               -- position within the document
    chunk_hash      VARCHAR(64),                     -- SHA256 for dedup

    -- Embedding vector
    embedding       VECTOR(768),

    -- Deep Link metadata
    source_type     VARCHAR(20) DEFAULT 'document'  -- 'document' | 'video'
                        CHECK (source_type IN ('document', 'video')),
    page_number     INTEGER,                         -- for PDF deep link
    start_time_sec  INTEGER,                         -- for video deep link (seconds)
    end_time_sec    INTEGER,

    -- Language detection
    language        VARCHAR(10) DEFAULT 'vi',        -- 'vi' | 'en' | 'mixed'

    -- Processing status
    status          VARCHAR(20) DEFAULT 'ready'
                        CHECK (status IN ('pending', 'processing', 'ready', 'error')),

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- HNSW index for fast cosine similarity search (critical for RAG latency)
CREATE INDEX idx_chunks_embedding_hnsw
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_chunks_content    ON document_chunks(content_id);
CREATE INDEX idx_chunks_node       ON document_chunks(node_id);
CREATE INDEX idx_chunks_course     ON document_chunks(course_id);
CREATE INDEX idx_chunks_status     ON document_chunks(status);
CREATE INDEX idx_chunks_hash       ON document_chunks(chunk_hash);

-- ============================================================
-- DOCUMENT PROCESSING JOBS
-- ============================================================
CREATE TABLE IF NOT EXISTS document_processing_jobs (
    id              BIGSERIAL PRIMARY KEY,
    content_id      BIGINT NOT NULL REFERENCES section_content(id) ON DELETE CASCADE,
    course_id       BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    node_id         BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,

    status          VARCHAR(20) DEFAULT 'queued'
                        CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    error_message   TEXT,
    chunks_created  INTEGER DEFAULT 0,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_processing_jobs_content ON document_processing_jobs(content_id);
CREATE INDEX idx_processing_jobs_status  ON document_processing_jobs(status);

-- ============================================================
-- AI DIAGNOSES (Error diagnosis history — Phase 1)
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_diagnoses (
    id              BIGSERIAL PRIMARY KEY,
    student_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_id      BIGINT REFERENCES quiz_attempts(id) ON DELETE SET NULL,
    question_id     BIGINT REFERENCES quiz_questions(id) ON DELETE SET NULL,
    node_id         BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,

    wrong_answer    TEXT,
    correct_answer  TEXT,
    explanation     TEXT NOT NULL,         -- LLM diagnosis
    gap_type        VARCHAR(50),           -- 'misconception' | 'missing_prerequisite' | 'careless'
    confidence      FLOAT DEFAULT 0.8,
    source_chunk_id BIGINT REFERENCES document_chunks(id) ON DELETE SET NULL,
    language        VARCHAR(10) DEFAULT 'vi',

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_diagnoses_student   ON ai_diagnoses(student_id);
CREATE INDEX idx_diagnoses_question  ON ai_diagnoses(question_id);
CREATE INDEX idx_diagnoses_node      ON ai_diagnoses(node_id);

-- ============================================================
-- STUDENT KNOWLEDGE PROGRESS (Weakness Heatmap — Phase 1)
-- ============================================================
CREATE TABLE IF NOT EXISTS student_knowledge_progress (
    id              BIGSERIAL PRIMARY KEY,
    student_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    node_id         BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id       BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,

    total_attempts  INTEGER DEFAULT 0,
    correct_count   INTEGER DEFAULT 0,
    wrong_count     INTEGER DEFAULT 0,
    mastery_level   FLOAT DEFAULT 0.0,     -- 0.0 to 1.0
    last_tested_at  TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(student_id, node_id)
);

CREATE INDEX idx_skp_student  ON student_knowledge_progress(student_id, course_id);
CREATE INDEX idx_skp_node     ON student_knowledge_progress(node_id);
CREATE INDEX idx_skp_mastery  ON student_knowledge_progress(mastery_level);

-- ============================================================
-- SPACED REPETITION ENGINE — SM-2 Algorithm (Phase 2)
-- ============================================================
CREATE TABLE IF NOT EXISTS spaced_repetitions (
    id                      BIGSERIAL PRIMARY KEY,
    student_id              BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id             BIGINT REFERENCES quiz_questions(id) ON DELETE CASCADE,
    node_id                 BIGINT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id               BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,

    -- SM-2 fields
    easiness_factor         FLOAT DEFAULT 2.5,      -- E-factor (min 1.3)
    interval_days           INTEGER DEFAULT 1,       -- days until next review
    repetitions             INTEGER DEFAULT 0,       -- consecutive correct answers
    quality_last            INTEGER DEFAULT 0,       -- last response quality (0-5)

    next_review_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    last_reviewed_at        TIMESTAMP,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(student_id, question_id)
);

CREATE INDEX idx_sr_student_due ON spaced_repetitions(student_id, next_review_date);
CREATE INDEX idx_sr_course      ON spaced_repetitions(student_id, course_id);

-- ============================================================
-- AI GENERATED QUIZZES (Phase 2 — DRAFT status before teacher review)
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_quiz_generations (
    id              BIGSERIAL PRIMARY KEY,
    node_id         BIGINT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id       BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    created_by      BIGINT NOT NULL REFERENCES users(id),

    bloom_level     VARCHAR(20)           -- 'remember' | 'understand' | 'apply' | ...
                        CHECK (bloom_level IN (
                            'remember', 'understand', 'apply',
                            'analyze', 'evaluate', 'create'
                        )),
    question_text   TEXT NOT NULL,
    question_type   VARCHAR(50) NOT NULL,
    answer_options  JSONB,               -- [{text, is_correct, explanation}]
    correct_answer  TEXT,
    explanation     TEXT,
    source_quote    TEXT,                -- exact quote from source material
    source_chunk_id BIGINT REFERENCES document_chunks(id) ON DELETE SET NULL,
    language        VARCHAR(10) DEFAULT 'vi',

    -- Review workflow
    status          VARCHAR(20) DEFAULT 'DRAFT'
                        CHECK (status IN ('DRAFT', 'APPROVED', 'REJECTED', 'PUBLISHED')),
    review_note     TEXT,
    reviewed_by     BIGINT REFERENCES users(id),
    reviewed_at     TIMESTAMP,

    -- If published → linked quiz question
    quiz_question_id BIGINT REFERENCES quiz_questions(id) ON DELETE SET NULL,

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aiqg_node    ON ai_quiz_generations(node_id);
CREATE INDEX idx_aiqg_status  ON ai_quiz_generations(status);
CREATE INDEX idx_aiqg_course  ON ai_quiz_generations(course_id);

-- ============================================================
-- LINK QUIZ QUESTIONS → KNOWLEDGE NODES (for heatmap)
-- ============================================================
ALTER TABLE quiz_questions
    ADD COLUMN IF NOT EXISTS node_id BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS bloom_level VARCHAR(20)
        CHECK (bloom_level IN ('remember','understand','apply','analyze','evaluate','create')),
    ADD COLUMN IF NOT EXISTS reference_chunk_id BIGINT REFERENCES document_chunks(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_quiz_q_node ON quiz_questions(node_id);

-- ============================================================
-- TRIGGERS
-- ============================================================
CREATE TRIGGER update_knowledge_nodes_updated_at
    BEFORE UPDATE ON knowledge_nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_jobs_updated_at
    BEFORE UPDATE ON document_processing_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_skp_updated_at
    BEFORE UPDATE ON student_knowledge_progress
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sr_updated_at
    BEFORE UPDATE ON spaced_repetitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_aiqg_updated_at
    BEFORE UPDATE ON ai_quiz_generations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- HELPER: Auto-update student_knowledge_progress on answer submission
-- ============================================================
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

CREATE TRIGGER trigger_update_knowledge_progress
    AFTER UPDATE OF is_correct ON quiz_student_answers
    FOR EACH ROW
    WHEN (NEW.is_correct IS NOT NULL)
    EXECUTE FUNCTION update_knowledge_progress_on_answer();