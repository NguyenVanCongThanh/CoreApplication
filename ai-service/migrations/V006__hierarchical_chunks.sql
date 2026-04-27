-- ── Hierarchical chunking ─────────────────────────────────────────
-- Adds parent/child relationship to document_chunks so RAG can do:
--    1. ANN search over fine-grained CHILD chunks (better recall)
--    2. Hydrate the matched chunk's PARENT for LLM context window
--       (better precision — the LLM sees the full surrounding section
--       instead of an isolated 300-token window).
--
-- Levels:
--   chunk_level = 'child'   → embedded, indexed in Qdrant, used for search
--   chunk_level = 'parent'  → stored in PG only (no embedding), holds
--                             the surrounding section text for hydration
--
-- Existing rows are migrated to chunk_level='child' with parent_chunk_id NULL.

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS parent_chunk_id BIGINT
        REFERENCES document_chunks(id) ON DELETE CASCADE;

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS chunk_level VARCHAR(10) DEFAULT 'child'
        CHECK (chunk_level IN ('parent', 'child'));

UPDATE document_chunks
SET chunk_level = 'child'
WHERE chunk_level IS NULL;

CREATE INDEX IF NOT EXISTS idx_dc_parent ON document_chunks(parent_chunk_id);
CREATE INDEX IF NOT EXISTS idx_dc_level  ON document_chunks(chunk_level);

-- Cascade delete: if a parent is removed, its children go with it.
-- (`source_type` check constraint already permits 'document' / 'video';
-- keep parents inheriting source_type='document'.)