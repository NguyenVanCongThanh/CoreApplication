-- =============================================================
-- V004: Chat History Persistence
-- Adds a title to sessions and a persistent message store.
-- =============================================================

ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(200);

CREATE TABLE IF NOT EXISTS agent_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content     TEXT NOT NULL DEFAULT '',
    metadata    JSONB DEFAULT '{}',    -- toolActivities, uiComponent, hitlRequest, etc.
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_am_session ON agent_messages(session_id, created_at);
