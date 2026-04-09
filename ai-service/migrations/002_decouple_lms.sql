-- Migration: Create content_index_status table in AI DB
-- This replaces the ai_index_status column in LMS DB's section_content table
-- AI Service now tracks its own indexing status independently

CREATE TABLE IF NOT EXISTS content_index_status (
    content_id   BIGINT PRIMARY KEY,
    course_id    BIGINT NOT NULL,
    title        TEXT DEFAULT '',
    status       VARCHAR(20) NOT NULL DEFAULT 'pending',
    error        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cis_course ON content_index_status(course_id);
CREATE INDEX IF NOT EXISTS idx_cis_status ON content_index_status(status);

-- Add source_content_title to knowledge_nodes for denormalized title lookup
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS source_content_title TEXT DEFAULT '';
