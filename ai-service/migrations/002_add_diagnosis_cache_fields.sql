-- Migration: Add missing fields for diagnosis caching and shared results
-- Applied to postgres-ai database

ALTER TABLE ai_diagnoses ADD COLUMN IF NOT EXISTS knowledge_gap TEXT;
ALTER TABLE ai_diagnoses ADD COLUMN IF NOT EXISTS study_suggestion TEXT;
ALTER TABLE ai_diagnoses ADD COLUMN IF NOT EXISTS suggested_docs_json JSONB;

-- Index for fast lookup by question and wrong answer text
-- We hash the wrong_answer text if it's potentially very long, or just index it.
-- Using md5 index is a safe way to handle long text values in PostgreSQL.
CREATE INDEX IF NOT EXISTS idx_ad_cache_lookup 
ON ai_diagnoses (question_id, md5(wrong_answer)) 
WHERE question_id IS NOT NULL;
