-- ============================================================
-- 004_ai_system_unified.sql
-- AI / RAG Infrastructure, Knowledge Graph, Flashcards
-- Integrated with bge-m3 (1024d) by default
-- ============================================================

-- pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- EXTERNAL TABLE UPDATES (Migrated from 005)
-- ============================================================
-- Track embedding model for content
ALTER TABLE section_content
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(64) DEFAULT 'bge-m3';

-- ============================================================
-- KNOWLEDGE NODES
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id                    BIGSERIAL PRIMARY KEY,
    course_id             BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    parent_id             BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    name                  VARCHAR(255) NOT NULL,
    name_vi               VARCHAR(255),
    name_en               VARCHAR(255),
    description           TEXT,
    description_embedding VECTOR(1024),         -- 1024d for bge-m3
    level                 INTEGER DEFAULT 0,    -- depth in the tree
    order_index           INTEGER DEFAULT 0,
    source_content_id     BIGINT REFERENCES section_content(id) ON DELETE SET NULL,
    auto_generated        BOOLEAN DEFAULT false,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_nodes_course         ON knowledge_nodes(course_id);
CREATE INDEX idx_knowledge_nodes_parent         ON knowledge_nodes(parent_id);
CREATE INDEX idx_knowledge_nodes_level          ON knowledge_nodes(course_id, level);
CREATE INDEX idx_knowledge_nodes_source_content ON knowledge_nodes(source_content_id)
    WHERE source_content_id IS NOT NULL;

-- HNSW index updated to ef_construction = 128 for 1024d better recall
CREATE INDEX idx_knowledge_nodes_embedding
    ON knowledge_nodes USING hnsw (description_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

CREATE TRIGGER update_knowledge_nodes_updated_at
    BEFORE UPDATE ON knowledge_nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- KNOWLEDGE NODE RELATIONS  (Knowledge Graph edges)
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_node_relations (
    id             BIGSERIAL PRIMARY KEY,
    course_id      BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    source_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    relation_type  VARCHAR(30) DEFAULT 'related'
                       CHECK (relation_type IN ('prerequisite', 'related', 'extends')),
    strength       FLOAT DEFAULT 1.0 CHECK (strength BETWEEN 0.0 AND 1.0),
    auto_generated BOOLEAN DEFAULT true,    -- false = created by a human
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_node_id, target_node_id, relation_type)
);

CREATE INDEX idx_node_relations_source ON knowledge_node_relations(source_node_id);
CREATE INDEX idx_node_relations_target ON knowledge_node_relations(target_node_id);
CREATE INDEX idx_node_relations_course ON knowledge_node_relations(course_id);

-- ============================================================
-- DOCUMENT CHUNKS  (RAG backbone)
-- ============================================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id             BIGSERIAL PRIMARY KEY,
    node_id        BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    content_id     BIGINT REFERENCES section_content(id) ON DELETE CASCADE,
    course_id      BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chunk_text     TEXT NOT NULL,
    chunk_index    INTEGER NOT NULL,
    chunk_hash     VARCHAR(64) UNIQUE,         -- SHA-256 for deduplication
    embedding      VECTOR(1024),               -- 1024d for bge-m3
    embedding_model VARCHAR(64) DEFAULT 'bge-m3', -- Track current model
    source_type    VARCHAR(20) DEFAULT 'document'
                       CHECK (source_type IN ('document', 'video')),
    page_number    INTEGER,                    -- PDF deep-link
    start_time_sec INTEGER,                    -- video deep-link
    end_time_sec   INTEGER,
    language       VARCHAR(10) DEFAULT 'vi',
    status         VARCHAR(20) DEFAULT 'ready'
                       CHECK (status IN ('pending', 'processing', 'ready', 'error')),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- HNSW index updated to ef_construction = 128 for 1024d better recall
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

CREATE INDEX idx_chunks_content ON document_chunks(content_id);
CREATE INDEX idx_chunks_node    ON document_chunks(node_id);
CREATE INDEX idx_chunks_course  ON document_chunks(course_id);
CREATE INDEX idx_chunks_status  ON document_chunks(status);
CREATE INDEX idx_chunks_hash    ON document_chunks(chunk_hash);

-- ============================================================
-- DOCUMENT PROCESSING JOBS
-- ============================================================

CREATE TABLE IF NOT EXISTS document_processing_jobs (
    id             BIGSERIAL PRIMARY KEY,
    content_id     BIGINT NOT NULL REFERENCES section_content(id) ON DELETE CASCADE,
    course_id      BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    node_id        BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    status         VARCHAR(20) DEFAULT 'queued'
                       CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    error_message  TEXT,
    chunks_created INTEGER DEFAULT 0,
    started_at     TIMESTAMP,
    completed_at   TIMESTAMP,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_processing_jobs_content ON document_processing_jobs(content_id);
CREATE INDEX idx_processing_jobs_status  ON document_processing_jobs(status);

CREATE TRIGGER update_processing_jobs_updated_at
    BEFORE UPDATE ON document_processing_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- AI DIAGNOSES  (Phase 1 — Error Diagnosis)
-- ============================================================

CREATE TABLE IF NOT EXISTS ai_diagnoses (
    id              BIGSERIAL PRIMARY KEY,
    student_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_id      BIGINT REFERENCES quiz_attempts(id) ON DELETE SET NULL,
    question_id     BIGINT REFERENCES quiz_questions(id) ON DELETE SET NULL,
    node_id         BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    wrong_answer    TEXT,
    correct_answer  TEXT,
    explanation     TEXT NOT NULL,      -- LLM-generated explanation
    gap_type        VARCHAR(50),        -- misconception | missing_prerequisite | careless
    confidence      FLOAT DEFAULT 0.8,
    source_chunk_id BIGINT REFERENCES document_chunks(id) ON DELETE SET NULL,
    language        VARCHAR(10) DEFAULT 'vi',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_diagnoses_student  ON ai_diagnoses(student_id);
CREATE INDEX idx_diagnoses_question ON ai_diagnoses(question_id);
CREATE INDEX idx_diagnoses_node     ON ai_diagnoses(node_id);

-- ============================================================
-- STUDENT KNOWLEDGE PROGRESS  (Weakness Heatmap)
-- ============================================================

CREATE TABLE IF NOT EXISTS student_knowledge_progress (
    id             BIGSERIAL PRIMARY KEY,
    student_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    node_id        BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id      BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    total_attempts INTEGER DEFAULT 0,
    correct_count  INTEGER DEFAULT 0,
    wrong_count    INTEGER DEFAULT 0,
    mastery_level  FLOAT DEFAULT 0.0,   -- 0.0 to 1.0
    last_tested_at TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, node_id)
);

CREATE INDEX idx_skp_student_course ON student_knowledge_progress(student_id, course_id);
CREATE INDEX idx_skp_node           ON student_knowledge_progress(node_id);
CREATE INDEX idx_skp_mastery        ON student_knowledge_progress(mastery_level);

CREATE TRIGGER update_skp_updated_at
    BEFORE UPDATE ON student_knowledge_progress
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- SPACED REPETITION ENGINE — SM-2 Algorithm
-- ============================================================

CREATE TABLE IF NOT EXISTS spaced_repetitions (
    id               BIGSERIAL PRIMARY KEY,
    student_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id      BIGINT REFERENCES quiz_questions(id) ON DELETE CASCADE,
    node_id          BIGINT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    easiness_factor  FLOAT   DEFAULT 2.5,   -- E-factor, minimum 1.3
    interval_days    INTEGER DEFAULT 1,
    repetitions      INTEGER DEFAULT 0,
    quality_last     INTEGER DEFAULT 0,     -- last response quality (0–5)
    next_review_date DATE NOT NULL DEFAULT CURRENT_DATE,
    last_reviewed_at TIMESTAMP,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, question_id)
);

CREATE INDEX idx_sr_student_due ON spaced_repetitions(student_id, next_review_date);
CREATE INDEX idx_sr_course      ON spaced_repetitions(student_id, course_id);

CREATE TRIGGER update_sr_updated_at
    BEFORE UPDATE ON spaced_repetitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- AI GENERATED QUIZZES  (Phase 2 — DRAFT pending teacher review)
-- ============================================================

CREATE TABLE IF NOT EXISTS ai_quiz_generations (
    id               BIGSERIAL PRIMARY KEY,
    node_id          BIGINT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    created_by       BIGINT NOT NULL REFERENCES users(id),
    bloom_level      VARCHAR(20) CHECK (bloom_level IN (
                         'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'
                     )),
    question_text    TEXT NOT NULL,
    question_type    VARCHAR(50) NOT NULL,
    answer_options   JSONB,    -- [{text, is_correct, explanation}]
    correct_answer   TEXT,
    explanation      TEXT,
    source_quote     TEXT,
    source_chunk_id  BIGINT REFERENCES document_chunks(id) ON DELETE SET NULL,
    language         VARCHAR(10) DEFAULT 'vi',
    status           VARCHAR(20) DEFAULT 'DRAFT'
                         CHECK (status IN ('DRAFT', 'APPROVED', 'REJECTED', 'PUBLISHED')),
    review_note      TEXT,
    reviewed_by      BIGINT REFERENCES users(id),
    reviewed_at      TIMESTAMP,
    quiz_question_id BIGINT REFERENCES quiz_questions(id) ON DELETE SET NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aiqg_node   ON ai_quiz_generations(node_id);
CREATE INDEX idx_aiqg_status ON ai_quiz_generations(status);
CREATE INDEX idx_aiqg_course ON ai_quiz_generations(course_id);

CREATE TRIGGER update_aiqg_updated_at
    BEFORE UPDATE ON ai_quiz_generations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- FLASHCARDS & FLASHCARD REPETITIONS
-- AI-generated flashcards per student × knowledge node with SM-2 tracking
-- ============================================================

CREATE TABLE IF NOT EXISTS flashcards (
    id                  BIGSERIAL PRIMARY KEY,
    course_id           BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    node_id             BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    student_id          BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    front_text          TEXT NOT NULL,
    back_text           TEXT NOT NULL,
    source_diagnosis_id BIGINT REFERENCES ai_diagnoses(id) ON DELETE SET NULL,
    status              VARCHAR(20) DEFAULT 'ACTIVE'
                            CHECK (status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_flashcards_student_node ON flashcards(student_id, node_id);
CREATE INDEX idx_flashcards_course       ON flashcards(course_id);

CREATE TRIGGER update_flashcards_updated_at
    BEFORE UPDATE ON flashcards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS flashcard_repetitions (
    id               BIGSERIAL PRIMARY KEY,
    student_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flashcard_id     BIGINT NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    easiness_factor  FLOAT   DEFAULT 2.5,
    interval_days    INTEGER DEFAULT 1,
    repetitions      INTEGER DEFAULT 0,
    quality_last     INTEGER DEFAULT 0,
    next_review_date DATE NOT NULL DEFAULT CURRENT_DATE,
    last_reviewed_at TIMESTAMP,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, flashcard_id)
);

CREATE INDEX idx_flashcard_rep_due ON flashcard_repetitions(student_id, course_id, next_review_date);

CREATE TRIGGER update_flashcard_rep_updated_at
    BEFORE UPDATE ON flashcard_repetitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- LINK quiz_questions → knowledge graph
-- ============================================================

ALTER TABLE quiz_questions
    ADD COLUMN IF NOT EXISTS node_id            BIGINT
        REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS bloom_level        VARCHAR(20)
        CHECK (bloom_level IN ('remember','understand','apply','analyze','evaluate','create')),
    ADD COLUMN IF NOT EXISTS reference_chunk_id BIGINT
        REFERENCES document_chunks(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_quiz_q_node ON quiz_questions(node_id);

-- ============================================================
-- TRIGGER: Auto-update student_knowledge_progress on answer grading
-- ============================================================

CREATE OR REPLACE FUNCTION update_knowledge_progress_on_answer()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_correct IS NULL THEN
        RETURN NEW;
    END IF;

    INSERT INTO student_knowledge_progress (
        student_id, node_id, course_id,
        total_attempts, correct_count, wrong_count, mastery_level, last_tested_at
    )
    SELECT
        qa.student_id,
        qq.node_id,
        cs2.course_id,
        1,
        CASE WHEN NEW.is_correct THEN 1 ELSE 0 END,
        CASE WHEN NEW.is_correct THEN 0 ELSE 1 END,
        CASE WHEN NEW.is_correct THEN 0.6 ELSE 0.0 END,
        NOW()
    FROM  quiz_questions  qq
    JOIN  quiz_attempts   qa  ON  qa.id   = NEW.attempt_id
    JOIN  quizzes         qz  ON  qz.id   = qa.quiz_id
    JOIN  section_content sc  ON  sc.id   = qz.content_id
    JOIN  course_sections cs2 ON  cs2.id  = sc.section_id
    WHERE qq.id       = NEW.question_id
      AND qq.node_id  IS NOT NULL
    ON CONFLICT (student_id, node_id) DO UPDATE SET
        total_attempts = student_knowledge_progress.total_attempts + 1,
        correct_count  = student_knowledge_progress.correct_count
                         + CASE WHEN NEW.is_correct THEN 1 ELSE 0 END,
        wrong_count    = student_knowledge_progress.wrong_count
                         + CASE WHEN NEW.is_correct THEN 0 ELSE 1 END,
        mastery_level  = LEAST(1.0,
                           (student_knowledge_progress.correct_count
                            + CASE WHEN NEW.is_correct THEN 1 ELSE 0 END)::FLOAT
                           / NULLIF(student_knowledge_progress.total_attempts + 1, 0)),
        last_tested_at = NOW(),
        updated_at     = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_knowledge_progress
    AFTER UPDATE OF is_correct ON quiz_student_answers
    FOR EACH ROW
    WHEN (NEW.is_correct IS NOT NULL)
    EXECUTE FUNCTION update_knowledge_progress_on_answer();

-- ============================================================
-- TRIGGER: Reset AI index state on re-index
-- ============================================================

CREATE OR REPLACE FUNCTION reset_content_ai_index()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ai_index_status = 'processing' AND OLD.ai_index_status <> 'processing' THEN
        -- Remove stale chunks for this content
        DELETE FROM document_chunks WHERE content_id = NEW.id;
        -- Remove AI-generated nodes only (preserve manually created ones)
        DELETE FROM knowledge_nodes
        WHERE  source_content_id = NEW.id AND auto_generated = true;
        NEW.ai_indexed_at := NULL;
    END IF;

    IF NEW.ai_index_status = 'indexed' THEN
        NEW.ai_indexed_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_reset_content_ai_index
    BEFORE UPDATE OF ai_index_status ON section_content
    FOR EACH ROW EXECUTE FUNCTION reset_content_ai_index();

-- ============================================================
-- VIEW: Knowledge graph per course (for visualization)
-- ============================================================

CREATE OR REPLACE VIEW knowledge_graph_view AS
SELECT
    kn.id                           AS node_id,
    kn.course_id,
    kn.name,
    kn.name_vi,
    kn.level,
    kn.auto_generated,
    kn.source_content_id,
    sc.title                        AS source_content_title,
    COUNT(DISTINCT dc.id)           AS chunk_count,
    COUNT(DISTINCT knr_out.id)      AS out_edges,
    COUNT(DISTINCT knr_in.id)       AS in_edges
FROM       knowledge_nodes          kn
LEFT JOIN  section_content          sc      ON  sc.id             = kn.source_content_id
LEFT JOIN  document_chunks          dc      ON  dc.node_id        = kn.id
LEFT JOIN  knowledge_node_relations knr_out ON  knr_out.source_node_id = kn.id
LEFT JOIN  knowledge_node_relations knr_in  ON  knr_in.target_node_id  = kn.id
GROUP BY
    kn.id, kn.course_id, kn.name, kn.name_vi,
    kn.level, kn.auto_generated, kn.source_content_id, sc.title;