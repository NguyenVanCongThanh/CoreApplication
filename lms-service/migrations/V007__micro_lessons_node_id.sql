ALTER TABLE micro_lessons
ADD COLUMN node_id BIGINT;

-- Add an index for fast lookups by node_id
CREATE INDEX IF NOT EXISTS idx_micro_lessons_node_id ON micro_lessons(node_id);
