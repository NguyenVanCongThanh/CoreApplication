-- ── AI index status reset trigger ────────────────────────────

CREATE OR REPLACE FUNCTION reset_ai_index_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ai_index_status = 'processing' AND OLD.ai_index_status <> 'processing' THEN
        NEW.ai_indexed_at   := NULL;
        NEW.ai_index_job_id := NULL;
    END IF;
    IF NEW.ai_index_status = 'indexed' THEN
        NEW.ai_indexed_at := CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgname = 'trigger_reset_ai_index_timestamp'
                     AND tgrelid = 'section_content'::regclass) THEN
        CREATE TRIGGER trigger_reset_ai_index_timestamp
            BEFORE UPDATE OF ai_index_status ON section_content
            FOR EACH ROW EXECUTE FUNCTION reset_ai_index_timestamp();
    END IF;
END $$;

-- ── Convenience view ──────────────────────────────────────────

CREATE OR REPLACE VIEW v_content_ai_status AS
SELECT
    sc.id               AS content_id,
    sc.title,
    sc.type,
    sc.ai_index_status,
    sc.ai_indexed_at,
    sc.embedding_model,
    cs.course_id,
    c.title             AS course_title
FROM section_content sc
JOIN course_sections cs ON cs.id = sc.section_id
JOIN courses         c  ON c.id  = cs.course_id
WHERE sc.type NOT IN ('QUIZ', 'FORUM', 'ANNOUNCEMENT')
ORDER BY sc.ai_index_status, sc.updated_at DESC;
