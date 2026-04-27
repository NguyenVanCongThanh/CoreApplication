-- ── MICRO LESSONS ────────────────────────────────────────────────
-- Auto-generated bite-sized lessons (~5 min read) created from
-- a source file/video. Each lesson stores Markdown content with
-- inline image references already uploaded to MinIO.
-- Lessons start as DRAFT; teachers can edit Markdown then publish.
-- On publish, a SectionContent of type TEXT is created and routed
-- through the existing auto-index pipeline.

CREATE TABLE IF NOT EXISTS micro_lesson_jobs (
    id                BIGSERIAL PRIMARY KEY,
    course_id         BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    section_id        BIGINT REFERENCES course_sections(id) ON DELETE SET NULL,
    source_content_id BIGINT REFERENCES section_content(id) ON DELETE SET NULL,
    source_file_path  VARCHAR(1000),
    source_file_type  VARCHAR(100),
    source_url        VARCHAR(1000),
    target_minutes    INT NOT NULL DEFAULT 5,
    language          VARCHAR(10) NOT NULL DEFAULT 'vi',
    status            VARCHAR(20) NOT NULL DEFAULT 'queued'
                          CHECK (status IN ('queued','processing','completed','failed')),
    progress          INT DEFAULT 0,
    stage             VARCHAR(64) DEFAULT '',
    lessons_count     INT DEFAULT 0,
    error             TEXT,
    created_by        BIGINT NOT NULL REFERENCES users(id),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_micro_jobs_course  ON micro_lesson_jobs(course_id);
CREATE INDEX IF NOT EXISTS idx_micro_jobs_status  ON micro_lesson_jobs(status);
CREATE INDEX IF NOT EXISTS idx_micro_jobs_creator ON micro_lesson_jobs(created_by);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_micro_lesson_jobs_updated_at'
                   AND tgrelid='micro_lesson_jobs'::regclass) THEN
        CREATE TRIGGER update_micro_lesson_jobs_updated_at
            BEFORE UPDATE ON micro_lesson_jobs
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;


CREATE TABLE IF NOT EXISTS micro_lessons (
    id                  BIGSERIAL PRIMARY KEY,
    job_id              BIGINT NOT NULL REFERENCES micro_lesson_jobs(id) ON DELETE CASCADE,
    course_id           BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    section_id          BIGINT REFERENCES course_sections(id) ON DELETE SET NULL,
    source_content_id   BIGINT REFERENCES section_content(id) ON DELETE SET NULL,
    title               VARCHAR(500) NOT NULL,
    summary             TEXT,
    objectives          JSONB DEFAULT '[]'::jsonb,
    markdown_content    TEXT NOT NULL,
    estimated_minutes   INT DEFAULT 5,
    order_index         INT NOT NULL DEFAULT 0,
    status              VARCHAR(20) NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft','published','archived')),
    published_content_id BIGINT REFERENCES section_content(id) ON DELETE SET NULL,
    image_urls          JSONB DEFAULT '[]'::jsonb,
    language            VARCHAR(10) DEFAULT 'vi',
    created_by          BIGINT NOT NULL REFERENCES users(id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at        TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_micro_lessons_job        ON micro_lessons(job_id);
CREATE INDEX IF NOT EXISTS idx_micro_lessons_course     ON micro_lessons(course_id);
CREATE INDEX IF NOT EXISTS idx_micro_lessons_section    ON micro_lessons(section_id);
CREATE INDEX IF NOT EXISTS idx_micro_lessons_source     ON micro_lessons(source_content_id);
CREATE INDEX IF NOT EXISTS idx_micro_lessons_status     ON micro_lessons(status);
CREATE INDEX IF NOT EXISTS idx_micro_lessons_order      ON micro_lessons(job_id, order_index);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_micro_lessons_updated_at'
                   AND tgrelid='micro_lessons'::regclass) THEN
        CREATE TRIGGER update_micro_lessons_updated_at
            BEFORE UPDATE ON micro_lessons
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;