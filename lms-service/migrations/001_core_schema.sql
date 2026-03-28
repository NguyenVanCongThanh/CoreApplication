-- ============================================================
-- SHARED TRIGGER FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id         BIGSERIAL PRIMARY KEY,
    email      VARCHAR(255) UNIQUE NOT NULL,
    full_name  VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- USER ROLES
-- ============================================================

CREATE TABLE IF NOT EXISTS user_roles (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       VARCHAR(50) NOT NULL CHECK (role IN ('STUDENT', 'TEACHER', 'ADMIN')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, role)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role);

-- ============================================================
-- COURSES
-- ============================================================

CREATE TABLE IF NOT EXISTS courses (
    id            BIGSERIAL PRIMARY KEY,
    title         VARCHAR(255) NOT NULL,
    description   TEXT,
    category      VARCHAR(100),
    level         VARCHAR(50) CHECK (level IN ('BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'ALL_LEVELS')),
    thumbnail_url VARCHAR(500),
    status        VARCHAR(50) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
    created_by    BIGINT NOT NULL REFERENCES users(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at  TIMESTAMP
);

CREATE INDEX idx_courses_status     ON courses(status);
CREATE INDEX idx_courses_category   ON courses(category);
CREATE INDEX idx_courses_created_by ON courses(created_by);
CREATE INDEX idx_courses_level      ON courses(level);

CREATE TRIGGER update_courses_updated_at
    BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- COURSE SECTIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS course_sections (
    id           BIGSERIAL PRIMARY KEY,
    course_id    BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    order_index  INTEGER NOT NULL,
    is_published BOOLEAN DEFAULT false,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sections_course ON course_sections(course_id);
CREATE INDEX idx_sections_order  ON course_sections(course_id, order_index);

CREATE TRIGGER update_course_sections_updated_at
    BEFORE UPDATE ON course_sections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- SECTION CONTENT
-- ============================================================

CREATE TABLE IF NOT EXISTS section_content (
    id              BIGSERIAL PRIMARY KEY,
    section_id      BIGINT NOT NULL REFERENCES course_sections(id) ON DELETE CASCADE,
    type            VARCHAR(50) NOT NULL CHECK (type IN (
                        'TEXT', 'VIDEO', 'DOCUMENT', 'IMAGE', 'QUIZ', 'FORUM', 'ANNOUNCEMENT'
                    )),
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    order_index     INTEGER NOT NULL,
    metadata        JSONB,
    is_published    BOOLEAN DEFAULT false,
    is_mandatory    BOOLEAN DEFAULT false,
    file_path       VARCHAR(1000),
    file_size       BIGINT,
    file_type       VARCHAR(100),
    -- AI indexing state (used by 004_ai_system.sql)
    ai_index_status VARCHAR(20) DEFAULT 'not_indexed'
                        CHECK (ai_index_status IN ('not_indexed', 'processing', 'indexed', 'failed')),
    ai_index_job_id BIGINT,
    ai_indexed_at   TIMESTAMP,
    created_by      BIGINT NOT NULL REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_content_section   ON section_content(section_id);
CREATE INDEX idx_content_type      ON section_content(type);
CREATE INDEX idx_content_order     ON section_content(section_id, order_index);
CREATE INDEX idx_content_ai_status ON section_content(ai_index_status)
    WHERE ai_index_status IN ('processing', 'indexed');

CREATE TRIGGER update_section_content_updated_at
    BEFORE UPDATE ON section_content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- ENROLLMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS enrollments (
    id          BIGSERIAL PRIMARY KEY,
    course_id   BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    student_id  BIGINT NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACCEPTED',
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rejected_at TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(course_id, student_id)
);

CREATE INDEX idx_enrollments_course         ON enrollments(course_id);
CREATE INDEX idx_enrollments_student        ON enrollments(student_id);
CREATE INDEX idx_enrollments_status         ON enrollments(status);
CREATE INDEX idx_enrollments_course_status  ON enrollments(course_id, status);
CREATE INDEX idx_enrollments_student_status ON enrollments(student_id, status);

CREATE TRIGGER update_enrollments_updated_at
    BEFORE UPDATE ON enrollments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Guarantee every INSERT is ACCEPTED, regardless of the caller's value
CREATE OR REPLACE FUNCTION auto_accept_enrollment()
RETURNS TRIGGER AS $$
BEGIN
    NEW.status      := 'ACCEPTED';
    NEW.accepted_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_accept_enrollment
    BEFORE INSERT ON enrollments
    FOR EACH ROW EXECUTE FUNCTION auto_accept_enrollment();

-- ============================================================
-- BULK ENROLLMENT LOGS
-- ============================================================

CREATE TABLE IF NOT EXISTS bulk_enrollment_logs (
    id            BIGSERIAL PRIMARY KEY,
    course_id     BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    teacher_id    BIGINT NOT NULL,
    total_count   INT NOT NULL,
    success_count INT DEFAULT 0,
    failed_count  INT DEFAULT 0,
    status        VARCHAR(20) DEFAULT 'PROCESSING',  -- PROCESSING | COMPLETED | FAILED
    error_message TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP
);

CREATE INDEX idx_bulk_logs_course  ON bulk_enrollment_logs(course_id);
CREATE INDEX idx_bulk_logs_teacher ON bulk_enrollment_logs(teacher_id);
CREATE INDEX idx_bulk_logs_status  ON bulk_enrollment_logs(status);
