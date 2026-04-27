-- =============================================================
-- V003: Agent Memory Tables
-- Supports the 5-tier memory architecture for Virtual TA
-- and Virtual Mentor chat agents.
--
-- Tables:
--   agent_sessions   — MTM: compressed context per user-agent pair
--   agent_episodes   — LTM metadata (vectors stored in Qdrant)
-- =============================================================

-- agent_sessions: Medium-Term Memory storage
-- Stores compressed conversation context (JSONB) that survives
-- beyond the Redis STM window. Updated after every N turns via
-- the LLM context compressor.
CREATE TABLE IF NOT EXISTS agent_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL,
    agent_type      VARCHAR(20) NOT NULL
                        CHECK (agent_type IN ('teacher', 'mentor')),
    course_id       BIGINT,
    compressed_ctx  JSONB NOT NULL DEFAULT '{}',
    -- compressed_ctx schema:
    -- {
    --   "active_course": {...},
    --   "recent_quiz_ids": [...],
    --   "identified_gaps": [...],
    --   "content_created": [...],
    --   "pending_actions": [...],
    --   "student_progress": {...},
    --   "decisions_made": [...],
    --   "key_facts": {...}
    -- }
    turn_count      INTEGER DEFAULT 0,
    last_active_at  TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_as_user
    ON agent_sessions(user_id, agent_type);
CREATE INDEX IF NOT EXISTS idx_as_active
    ON agent_sessions(last_active_at);
CREATE INDEX IF NOT EXISTS idx_as_course
    ON agent_sessions(course_id)
    WHERE course_id IS NOT NULL;

-- agent_episodes: Long-Term Memory metadata
-- Each episode is a compressed summary of a completed session.
-- The vector embedding lives in Qdrant (collection: agent_episodes).
-- This table stores metadata for auditability and joins.
CREATE TABLE IF NOT EXISTS agent_episodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES agent_sessions(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL,
    agent_type      VARCHAR(20) NOT NULL
                        CHECK (agent_type IN ('teacher', 'mentor')),
    summary         TEXT NOT NULL,
    qdrant_point_id BIGINT,
    course_id       BIGINT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ae_user
    ON agent_episodes(user_id, agent_type);
CREATE INDEX IF NOT EXISTS idx_ae_session
    ON agent_episodes(session_id);
CREATE INDEX IF NOT EXISTS idx_ae_user_course
    ON agent_episodes(user_id, agent_type, course_id)
    WHERE course_id IS NOT NULL;
