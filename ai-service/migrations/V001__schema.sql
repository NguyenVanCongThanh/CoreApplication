CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================
-- KNOWLEDGE NODES
-- Embeddings stored in Qdrant (USE_QDRANT=true).
-- description_embedding column nullable — pgvector fallback only.
-- =============================================================

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id                    BIGSERIAL PRIMARY KEY,
    course_id             BIGINT NOT NULL,
    parent_id             BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    name                  VARCHAR(255) NOT NULL,
    name_vi               VARCHAR(255),
    name_en               VARCHAR(255),
    description           TEXT,
    level                 INTEGER DEFAULT 0,
    order_index           INTEGER DEFAULT 0,
    source_content_id     BIGINT,
    source_content_title  TEXT DEFAULT '',
    auto_generated        BOOLEAN DEFAULT false,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kn_course  ON knowledge_nodes(course_id);
CREATE INDEX IF NOT EXISTS idx_kn_parent  ON knowledge_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_kn_level   ON knowledge_nodes(course_id, level);
CREATE INDEX IF NOT EXISTS idx_kn_source  ON knowledge_nodes(source_content_id)
    WHERE source_content_id IS NOT NULL;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'tr_kn_updated'
                     AND tgrelid = 'knowledge_nodes'::regclass) THEN
        CREATE TRIGGER tr_kn_updated
            BEFORE UPDATE ON knowledge_nodes
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- =============================================================
-- KNOWLEDGE NODE RELATIONS
-- =============================================================

CREATE TABLE IF NOT EXISTS knowledge_node_relations (
    id             BIGSERIAL PRIMARY KEY,
    course_id      BIGINT NOT NULL,
    source_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    relation_type  VARCHAR(30) DEFAULT 'related'
                       CHECK (relation_type IN ('prerequisite', 'related', 'extends')),
    strength       FLOAT DEFAULT 1.0 CHECK (strength BETWEEN 0.0 AND 1.0),
    auto_generated BOOLEAN DEFAULT true,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_node_id, target_node_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_knr_source ON knowledge_node_relations(source_node_id);
CREATE INDEX IF NOT EXISTS idx_knr_target ON knowledge_node_relations(target_node_id);
CREATE INDEX IF NOT EXISTS idx_knr_course ON knowledge_node_relations(course_id);

-- =============================================================
-- DOCUMENT CHUNKS
-- embedding column NULL when USE_QDRANT=true.
-- =============================================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id              BIGSERIAL PRIMARY KEY,
    node_id         BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    content_id      BIGINT,
    course_id       BIGINT NOT NULL,
    chunk_text      TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    chunk_hash      VARCHAR(64) UNIQUE,
    embedding_model VARCHAR(64) DEFAULT 'bge-m3',
    source_type     VARCHAR(20) DEFAULT 'document'
                        CHECK (source_type IN ('document', 'video')),
    page_number     INTEGER,
    start_time_sec  INTEGER,
    end_time_sec    INTEGER,
    language        VARCHAR(10) DEFAULT 'vi',
    status          VARCHAR(20) DEFAULT 'ready'
                        CHECK (status IN ('pending', 'processing', 'ready', 'error')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dc_content ON document_chunks(content_id);
CREATE INDEX IF NOT EXISTS idx_dc_node    ON document_chunks(node_id);
CREATE INDEX IF NOT EXISTS idx_dc_course  ON document_chunks(course_id);
CREATE INDEX IF NOT EXISTS idx_dc_status  ON document_chunks(status);
CREATE INDEX IF NOT EXISTS idx_dc_hash    ON document_chunks(chunk_hash);

-- =============================================================
-- AI DIAGNOSES
-- Includes cache fields from 002_add_diagnosis_cache_fields.sql
-- =============================================================

CREATE TABLE IF NOT EXISTS ai_diagnoses (
    id                 BIGSERIAL PRIMARY KEY,
    student_id         BIGINT NOT NULL,
    attempt_id         BIGINT,
    question_id        BIGINT,
    node_id            BIGINT REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    wrong_answer       TEXT,
    correct_answer     TEXT,
    explanation        TEXT NOT NULL,
    gap_type           VARCHAR(50),
    knowledge_gap      TEXT,
    study_suggestion   TEXT,
    suggested_docs_json JSONB,
    confidence         FLOAT DEFAULT 0.8,
    source_chunk_id    BIGINT REFERENCES document_chunks(id) ON DELETE SET NULL,
    language           VARCHAR(10) DEFAULT 'vi',
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ad_student  ON ai_diagnoses(student_id);
CREATE INDEX IF NOT EXISTS idx_ad_question ON ai_diagnoses(question_id);
CREATE INDEX IF NOT EXISTS idx_ad_node     ON ai_diagnoses(node_id);
CREATE INDEX IF NOT EXISTS idx_ad_cache_lookup
    ON ai_diagnoses (question_id, md5(wrong_answer))
    WHERE question_id IS NOT NULL;

-- =============================================================
-- CONTENT INDEX STATUS
-- (from 002_decouple_lms.sql — AI tracks its own indexing state)
-- =============================================================

CREATE TABLE IF NOT EXISTS content_index_status (
    content_id  BIGINT PRIMARY KEY,
    course_id   BIGINT NOT NULL,
    title       TEXT DEFAULT '',
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    error       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cis_course ON content_index_status(course_id);
CREATE INDEX IF NOT EXISTS idx_cis_status ON content_index_status(status);

-- =============================================================
-- STUDENT KNOWLEDGE PROGRESS
-- =============================================================

CREATE TABLE IF NOT EXISTS student_knowledge_progress (
    id             BIGSERIAL PRIMARY KEY,
    student_id     BIGINT NOT NULL,
    node_id        BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id      BIGINT NOT NULL,
    total_attempts INTEGER DEFAULT 0,
    correct_count  INTEGER DEFAULT 0,
    wrong_count    INTEGER DEFAULT 0,
    mastery_level  FLOAT DEFAULT 0.0,
    last_tested_at TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_skp_student_course ON student_knowledge_progress(student_id, course_id);
CREATE INDEX IF NOT EXISTS idx_skp_node           ON student_knowledge_progress(node_id);
CREATE INDEX IF NOT EXISTS idx_skp_mastery        ON student_knowledge_progress(mastery_level);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'tr_skp_updated'
                     AND tgrelid = 'student_knowledge_progress'::regclass) THEN
        CREATE TRIGGER tr_skp_updated
            BEFORE UPDATE ON student_knowledge_progress
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- =============================================================
-- SPACED REPETITIONS (SM-2)
-- =============================================================

CREATE TABLE IF NOT EXISTS spaced_repetitions (
    id               BIGSERIAL PRIMARY KEY,
    student_id       BIGINT NOT NULL,
    question_id      BIGINT,
    node_id          BIGINT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL,
    easiness_factor  FLOAT   DEFAULT 2.5,
    interval_days    INTEGER DEFAULT 1,
    repetitions      INTEGER DEFAULT 0,
    quality_last     INTEGER DEFAULT 0,
    next_review_date DATE NOT NULL DEFAULT CURRENT_DATE,
    last_reviewed_at TIMESTAMP,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_sr_due    ON spaced_repetitions(student_id, next_review_date);
CREATE INDEX IF NOT EXISTS idx_sr_course ON spaced_repetitions(student_id, course_id);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'tr_sr_updated'
                     AND tgrelid = 'spaced_repetitions'::regclass) THEN
        CREATE TRIGGER tr_sr_updated
            BEFORE UPDATE ON spaced_repetitions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- =============================================================
-- AI QUIZ GENERATIONS
-- =============================================================

CREATE TABLE IF NOT EXISTS ai_quiz_generations (
    id               BIGSERIAL PRIMARY KEY,
    node_id          BIGINT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL,
    created_by       BIGINT NOT NULL,
    bloom_level      VARCHAR(20)
                         CHECK (bloom_level IN
                             ('remember','understand','apply','analyze','evaluate','create')),
    question_text    TEXT NOT NULL,
    question_type    VARCHAR(50) NOT NULL,
    answer_options   JSONB,
    correct_answer   TEXT,
    explanation      TEXT,
    source_quote     TEXT,
    source_chunk_id  BIGINT REFERENCES document_chunks(id) ON DELETE SET NULL,
    language         VARCHAR(10) DEFAULT 'vi',
    status           VARCHAR(20) DEFAULT 'DRAFT'
                         CHECK (status IN ('DRAFT','APPROVED','REJECTED','PUBLISHED')),
    review_note      TEXT,
    reviewed_by      BIGINT,
    reviewed_at      TIMESTAMP,
    quiz_question_id BIGINT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_aiqg_node   ON ai_quiz_generations(node_id);
CREATE INDEX IF NOT EXISTS idx_aiqg_status ON ai_quiz_generations(status);
CREATE INDEX IF NOT EXISTS idx_aiqg_course ON ai_quiz_generations(course_id);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'tr_aiqg_updated'
                     AND tgrelid = 'ai_quiz_generations'::regclass) THEN
        CREATE TRIGGER tr_aiqg_updated
            BEFORE UPDATE ON ai_quiz_generations
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- =============================================================
-- FLASHCARDS
-- =============================================================

CREATE TABLE IF NOT EXISTS flashcards (
    id                  BIGSERIAL PRIMARY KEY,
    course_id           BIGINT NOT NULL,
    node_id             BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    student_id          BIGINT NOT NULL,
    front_text          TEXT NOT NULL,
    back_text           TEXT NOT NULL,
    source_diagnosis_id BIGINT REFERENCES ai_diagnoses(id) ON DELETE SET NULL,
    status              VARCHAR(20) DEFAULT 'ACTIVE'
                            CHECK (status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fc_student_node ON flashcards(student_id, node_id);
CREATE INDEX IF NOT EXISTS idx_fc_course       ON flashcards(course_id);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'tr_fc_updated'
                     AND tgrelid = 'flashcards'::regclass) THEN
        CREATE TRIGGER tr_fc_updated
            BEFORE UPDATE ON flashcards
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- =============================================================
-- FLASHCARD REPETITIONS
-- =============================================================

CREATE TABLE IF NOT EXISTS flashcard_repetitions (
    id               BIGSERIAL PRIMARY KEY,
    student_id       BIGINT NOT NULL,
    flashcard_id     BIGINT NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    course_id        BIGINT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_fcr_due ON flashcard_repetitions(student_id, course_id, next_review_date);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'tr_fcr_updated'
                     AND tgrelid = 'flashcard_repetitions'::regclass) THEN
        CREATE TRIGGER tr_fcr_updated
            BEFORE UPDATE ON flashcard_repetitions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- =============================================================
-- EMBEDDING REINDEX JOBS
-- =============================================================

CREATE TABLE IF NOT EXISTS embedding_reindex_jobs (
    id            BIGSERIAL PRIMARY KEY,
    course_id     BIGINT,
    content_id    BIGINT,
    status        VARCHAR(20) DEFAULT 'pending'
                      CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    chunks_total  INTEGER DEFAULT 0,
    chunks_done   INTEGER DEFAULT 0,
    error_message TEXT,
    started_at    TIMESTAMP,
    completed_at  TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_erj_status  ON embedding_reindex_jobs(status);
CREATE INDEX IF NOT EXISTS idx_erj_course  ON embedding_reindex_jobs(course_id);
CREATE INDEX IF NOT EXISTS idx_erj_content ON embedding_reindex_jobs(content_id);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'tr_erj_updated'
                     AND tgrelid = 'embedding_reindex_jobs'::regclass) THEN
        CREATE TRIGGER tr_erj_updated
            BEFORE UPDATE ON embedding_reindex_jobs
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- =============================================================
-- VIEWS
-- =============================================================

CREATE OR REPLACE VIEW v_reindex_progress AS
SELECT
    COUNT(*)                                          AS total_jobs,
    COUNT(*) FILTER (WHERE status = 'done')           AS done,
    COUNT(*) FILTER (WHERE status = 'pending')        AS pending,
    COUNT(*) FILTER (WHERE status = 'processing')     AS processing,
    COUNT(*) FILTER (WHERE status = 'failed')         AS failed,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'done')::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                 AS pct_done,
    SUM(chunks_total)                                 AS total_chunks,
    SUM(chunks_done)                                  AS reindexed_chunks
FROM embedding_reindex_jobs;

CREATE OR REPLACE VIEW knowledge_graph_view AS
SELECT
    kn.id                           AS node_id,
    kn.course_id,
    kn.name,
    kn.name_vi,
    kn.level,
    kn.auto_generated,
    kn.source_content_id,
    COUNT(DISTINCT dc.id)           AS chunk_count,
    COUNT(DISTINCT knr_out.id)      AS out_edges,
    COUNT(DISTINCT knr_in.id)       AS in_edges
FROM       knowledge_nodes          kn
LEFT JOIN  document_chunks          dc      ON  dc.node_id        = kn.id
LEFT JOIN  knowledge_node_relations knr_out ON  knr_out.source_node_id = kn.id
LEFT JOIN  knowledge_node_relations knr_in  ON  knr_in.target_node_id  = kn.id
GROUP BY
    kn.id, kn.course_id, kn.name, kn.name_vi,
    kn.level, kn.auto_generated, kn.source_content_id;
