-- ============================================================
-- Migration 015: AI Auto-Index & Knowledge Graph
-- Thêm tự động phân chia tài liệu thành nhiều knowledge nodes
-- và xây dựng knowledge graph giữa các nodes.
-- ============================================================

-- 1. Thêm trạng thái index vào section_content
ALTER TABLE section_content
    ADD COLUMN IF NOT EXISTS ai_index_status VARCHAR(20) DEFAULT 'not_indexed'
        CHECK (ai_index_status IN ('not_indexed', 'processing', 'indexed', 'failed')),
    ADD COLUMN IF NOT EXISTS ai_index_job_id BIGINT,
    ADD COLUMN IF NOT EXISTS ai_indexed_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_content_ai_status ON section_content(ai_index_status)
    WHERE ai_index_status IN ('processing', 'indexed');

-- 2. Thêm embedding cho knowledge_nodes (để tìm node liên quan qua pgvector)
--    Dùng để tự động build edges trong knowledge graph
ALTER TABLE knowledge_nodes
    ADD COLUMN IF NOT EXISTS description_embedding VECTOR(768),
    ADD COLUMN IF NOT EXISTS source_content_id BIGINT REFERENCES section_content(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS auto_generated BOOLEAN DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_embedding
    ON knowledge_nodes USING hnsw (description_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_source_content
    ON knowledge_nodes(source_content_id)
    WHERE source_content_id IS NOT NULL;

-- 3. Bảng quan hệ giữa các knowledge nodes (Knowledge Graph edges)
CREATE TABLE IF NOT EXISTS knowledge_node_relations (
    id              BIGSERIAL PRIMARY KEY,
    course_id       BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    source_node_id  BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_node_id  BIGINT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,

    -- Loại quan hệ:
    -- prerequisite: source là kiến thức nền cần hiểu trước target
    -- related:      hai node liên quan, không nhất thiết có thứ tự
    -- extends:      target mở rộng/nâng cao từ source
    relation_type   VARCHAR(30) DEFAULT 'related'
                        CHECK (relation_type IN ('prerequisite', 'related', 'extends')),
    strength        FLOAT DEFAULT 1.0       -- 0.0-1.0, tính từ cosine similarity
        CHECK (strength BETWEEN 0.0 AND 1.0),
    auto_generated  BOOLEAN DEFAULT true,   -- true = do AI tạo, false = do người tạo

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source_node_id, target_node_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_node_relations_source ON knowledge_node_relations(source_node_id);
CREATE INDEX IF NOT EXISTS idx_node_relations_target ON knowledge_node_relations(target_node_id);
CREATE INDEX IF NOT EXISTS idx_node_relations_course  ON knowledge_node_relations(course_id);

-- ============================================================
-- 4. Trigger: khi re-index content → tự động xóa nodes/chunks cũ
--    và reset status. Nodes do người tạo (auto_generated=false) KHÔNG bị xóa.
-- ============================================================
CREATE OR REPLACE FUNCTION reset_content_ai_index()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ai_index_status = 'processing' AND OLD.ai_index_status != 'processing' THEN
        -- Xóa document chunks cũ của content này
        DELETE FROM document_chunks WHERE content_id = NEW.id;

        -- Xóa các AI-generated nodes từ content này (giữ nodes do người tạo)
        DELETE FROM knowledge_nodes
        WHERE source_content_id = NEW.id AND auto_generated = true;

        NEW.ai_indexed_at := NULL;
    END IF;

    IF NEW.ai_index_status = 'indexed' THEN
        NEW.ai_indexed_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_reset_content_ai_index
    BEFORE UPDATE OF ai_index_status ON section_content
    FOR EACH ROW
    EXECUTE FUNCTION reset_content_ai_index();

-- ============================================================
-- 5. View: Knowledge graph toàn khóa học để visualize
-- ============================================================
CREATE OR REPLACE VIEW knowledge_graph_view AS
SELECT
    kn.id               AS node_id,
    kn.course_id,
    kn.name,
    kn.name_vi,
    kn.level,
    kn.auto_generated,
    kn.source_content_id,
    sc.title            AS source_content_title,
    COUNT(DISTINCT dc.id)           AS chunk_count,
    COUNT(DISTINCT knr_out.id)      AS out_edges,
    COUNT(DISTINCT knr_in.id)       AS in_edges
FROM knowledge_nodes kn
LEFT JOIN section_content sc ON sc.id = kn.source_content_id
LEFT JOIN document_chunks dc ON dc.node_id = kn.id
LEFT JOIN knowledge_node_relations knr_out ON knr_out.source_node_id = kn.id
LEFT JOIN knowledge_node_relations knr_in  ON knr_in.target_node_id  = kn.id
GROUP BY kn.id, kn.course_id, kn.name, kn.name_vi, kn.level, kn.auto_generated,
         kn.source_content_id, sc.title;