-- =============================================================
-- V005: Multi-model LLM configuration
--
-- Replaces the single-provider (Groq) hardcoded setup with a
-- runtime-configurable registry of providers, API keys, models,
-- task→model bindings and per-call usage logs.
--
-- Design notes
--   * Keys are stored encrypted at the application layer (Fernet).
--     The DB only ever sees base64 ciphertext in `encrypted_key`.
--   * `task_model_bindings.priority` defines the fallback chain
--     for a given task_code. Lower = higher priority. Gateway will
--     iterate priority ASC, skipping rows where enabled = false.
--   * `llm_api_keys.status` is the single source of truth for
--     runtime health. Cooldowns are written by the gateway on 429.
--   * Usage rows are append-only; aggregations happen at read time
--     (plus materialised views can be added later for the admin UI).
-- =============================================================
 
-- ── Providers ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_providers (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(40)  NOT NULL UNIQUE,      -- 'groq' | 'anthropic' | 'gemini' | 'ollama' | 'openai_compat'
    display_name   VARCHAR(120) NOT NULL,
    adapter_type   VARCHAR(40)  NOT NULL,             -- which adapter class to instantiate
    base_url       VARCHAR(255),                      -- override (Ollama / custom OpenAI-compatible)
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    config         JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
 
-- ── API keys (many per provider) ──────────────────────────────
CREATE TABLE IF NOT EXISTS llm_api_keys (
    id                      BIGSERIAL PRIMARY KEY,
    provider_id             BIGINT      NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    alias                   VARCHAR(80) NOT NULL,                 -- admin-facing label e.g. "groq-key-prod-01"
    encrypted_key           TEXT        NOT NULL,                 -- Fernet ciphertext; never logged
    key_fingerprint         VARCHAR(32) NOT NULL,                 -- first 4 + last 4 of plaintext, for admin display
    status                  VARCHAR(20) NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active','cooldown','disabled','invalid')),
    rpm_limit               INTEGER,                              -- requests / minute (NULL = unlimited)
    tpm_limit               INTEGER,                              -- tokens / minute
    daily_token_limit       BIGINT,                               -- tokens / day (NULL = unlimited)
    used_today_requests     BIGINT      NOT NULL DEFAULT 0,
    used_today_tokens       BIGINT      NOT NULL DEFAULT 0,
    used_window_start       TIMESTAMPTZ NOT NULL DEFAULT NOW(),   -- rolling 24h window anchor
    cooldown_until          TIMESTAMPTZ,                          -- NULL or future = usable
    consecutive_failures    INTEGER     NOT NULL DEFAULT 0,
    last_error              TEXT,
    last_used_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider_id, alias)
);
 
CREATE INDEX IF NOT EXISTS idx_llm_api_keys_pool
    ON llm_api_keys (provider_id, status, cooldown_until);
 
-- ── Models offered by providers ───────────────────────────────
CREATE TABLE IF NOT EXISTS llm_models (
    id                  BIGSERIAL PRIMARY KEY,
    provider_id         BIGINT       NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    model_name          VARCHAR(120) NOT NULL,     -- provider identifier e.g. 'llama-3.3-70b-versatile'
    display_name        VARCHAR(160),
    family              VARCHAR(40),               -- 'llama' | 'claude' | 'gemini' | 'gemma' | 'qwen' ...
    context_window      INTEGER      NOT NULL DEFAULT 8192,
    supports_json       BOOLEAN      NOT NULL DEFAULT TRUE,
    supports_tools      BOOLEAN      NOT NULL DEFAULT FALSE,
    supports_streaming  BOOLEAN      NOT NULL DEFAULT TRUE,
    supports_vision     BOOLEAN      NOT NULL DEFAULT FALSE,
    input_cost_per_1k   NUMERIC(10,6) NOT NULL DEFAULT 0,
    output_cost_per_1k  NUMERIC(10,6) NOT NULL DEFAULT 0,
    default_temperature NUMERIC(4,3) NOT NULL DEFAULT 0.3,
    default_max_tokens  INTEGER      NOT NULL DEFAULT 1024,
    enabled             BOOLEAN      NOT NULL DEFAULT TRUE,
    config              JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (provider_id, model_name)
);
 
CREATE INDEX IF NOT EXISTS idx_llm_models_provider ON llm_models (provider_id, enabled);
 
-- ── Task → model bindings (with fallback chain via priority) ──
CREATE TABLE IF NOT EXISTS task_model_bindings (
    id                  BIGSERIAL PRIMARY KEY,
    task_code           VARCHAR(80)  NOT NULL,      -- 'chat' | 'quiz_gen' | 'diagnosis' | 'flashcard_gen'
                                                    -- | 'agent_react' | 'agent_router' | 'clarification'
                                                    -- | 'graph_link' | 'memory_compress' | 'language_detect'
    model_id            BIGINT       NOT NULL REFERENCES llm_models(id) ON DELETE CASCADE,
    priority            INTEGER      NOT NULL DEFAULT 100,   -- lower = tried first
    temperature         NUMERIC(4,3),                       -- NULL = use model default
    max_tokens          INTEGER,                             -- NULL = use model default
    json_mode           BOOLEAN      NOT NULL DEFAULT FALSE,
    pinned              BOOLEAN      NOT NULL DEFAULT FALSE, -- admin override: only this row wins
    enabled             BOOLEAN      NOT NULL DEFAULT TRUE,
    notes               TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (task_code, model_id)
);
 
CREATE INDEX IF NOT EXISTS idx_task_bindings_chain
    ON task_model_bindings (task_code, enabled, priority);
 
-- ── Usage log (append-only) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_usage_log (
    id                BIGSERIAL PRIMARY KEY,
    task_code         VARCHAR(80)  NOT NULL,
    model_id          BIGINT       REFERENCES llm_models(id) ON DELETE SET NULL,
    api_key_id        BIGINT       REFERENCES llm_api_keys(id) ON DELETE SET NULL,
    provider_code     VARCHAR(40),                          -- denormalised for fast grouping
    model_name        VARCHAR(120),                         -- denormalised
    prompt_tokens     INTEGER      NOT NULL DEFAULT 0,
    completion_tokens INTEGER      NOT NULL DEFAULT 0,
    total_tokens      INTEGER      NOT NULL DEFAULT 0,
    latency_ms        INTEGER      NOT NULL DEFAULT 0,
    success           BOOLEAN      NOT NULL,
    fallback_used     BOOLEAN      NOT NULL DEFAULT FALSE,  -- true if we retried after a failed primary
    attempt_no        INTEGER      NOT NULL DEFAULT 1,
    error_code        VARCHAR(60),
    error_message     TEXT,
    request_id        VARCHAR(120),                         -- correlation id if caller supplies one
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
 
CREATE INDEX IF NOT EXISTS idx_usage_log_created ON llm_usage_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_log_task    ON llm_usage_log (task_code, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_log_model   ON llm_usage_log (model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_log_key     ON llm_usage_log (api_key_id, created_at DESC);
 
-- ── updated_at trigger helper ─────────────────────────────────
CREATE OR REPLACE FUNCTION trg_llm_touch_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
 
DROP TRIGGER IF EXISTS trg_llm_providers_updated  ON llm_providers;
DROP TRIGGER IF EXISTS trg_llm_api_keys_updated   ON llm_api_keys;
DROP TRIGGER IF EXISTS trg_llm_models_updated     ON llm_models;
DROP TRIGGER IF EXISTS trg_task_bindings_updated  ON task_model_bindings;
 
CREATE TRIGGER trg_llm_providers_updated  BEFORE UPDATE ON llm_providers
    FOR EACH ROW EXECUTE FUNCTION trg_llm_touch_updated_at();
CREATE TRIGGER trg_llm_api_keys_updated   BEFORE UPDATE ON llm_api_keys
    FOR EACH ROW EXECUTE FUNCTION trg_llm_touch_updated_at();
CREATE TRIGGER trg_llm_models_updated     BEFORE UPDATE ON llm_models
    FOR EACH ROW EXECUTE FUNCTION trg_llm_touch_updated_at();
CREATE TRIGGER trg_task_bindings_updated  BEFORE UPDATE ON task_model_bindings
    FOR EACH ROW EXECUTE FUNCTION trg_llm_touch_updated_at();