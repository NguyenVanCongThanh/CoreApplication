-- ============================================================
-- Migration 014: Flashcards & Spaced Repetition (SM-2)
-- Tracking weak knowledge nodes and spaced repetition flashcards.
-- ============================================================

-- 1. FLASHCARDS TABLE
-- Stores AI-generated flashcards for a specific student and knowledge node
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

CREATE INDEX IF NOT EXISTS idx_flashcards_student_node ON flashcards(student_id, node_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_course ON flashcards(course_id);

-- 2. FLASHCARD REPETITIONS (SM-2 Algorithm State)
-- Tracks the spaced repetition progress of each flashcard
CREATE TABLE IF NOT EXISTS flashcard_repetitions (
    id                  BIGSERIAL PRIMARY KEY,
    student_id          BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flashcard_id        BIGINT NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    course_id           BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    
    -- SM-2 Algorithm Fields
    easiness_factor     FLOAT DEFAULT 2.5,       -- E-factor (minimum 1.3)
    interval_days       INTEGER DEFAULT 1,       -- Days until next review
    repetitions         INTEGER DEFAULT 0,       -- Consecutive correct answers
    quality_last        INTEGER DEFAULT 0,       -- Last response quality (0-5)
    
    next_review_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    last_reviewed_at    TIMESTAMP,
    
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(student_id, flashcard_id)
);

CREATE INDEX IF NOT EXISTS idx_flashcard_rep_due_date ON flashcard_repetitions(student_id, course_id, next_review_date);

-- 3. TRIGGERS
CREATE TRIGGER update_flashcards_updated_at
    BEFORE UPDATE ON flashcards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_flashcard_rep_updated_at
    BEFORE UPDATE ON flashcard_repetitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Analytics indexes for the heatmaps
CREATE INDEX IF NOT EXISTS idx_skp_student_course ON student_knowledge_progress(student_id, course_id);
