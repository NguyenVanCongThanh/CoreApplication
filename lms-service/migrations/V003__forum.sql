CREATE TABLE IF NOT EXISTS forum_posts (
    id            BIGSERIAL PRIMARY KEY,
    content_id    BIGINT NOT NULL REFERENCES section_content(id) ON DELETE CASCADE,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         VARCHAR(255) NOT NULL,
    body          TEXT NOT NULL,
    tags          VARCHAR(100)[] DEFAULT '{}',
    upvotes       INTEGER DEFAULT 0,
    downvotes     INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    view_count    INTEGER DEFAULT 0,
    is_pinned     BOOLEAN DEFAULT false,
    is_locked     BOOLEAN DEFAULT false,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forum_posts_content ON forum_posts(content_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_user    ON forum_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_created ON forum_posts(content_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forum_posts_pinned  ON forum_posts(content_id, is_pinned DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forum_posts_tags    ON forum_posts USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_forum_posts_search  ON forum_posts
    USING GIN(to_tsvector('english', title || ' ' || body));

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_forum_posts_updated_at'
                   AND tgrelid='forum_posts'::regclass) THEN
        CREATE TRIGGER update_forum_posts_updated_at
            BEFORE UPDATE ON forum_posts
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS forum_comments (
    id                BIGSERIAL PRIMARY KEY,
    post_id           BIGINT NOT NULL REFERENCES forum_posts(id) ON DELETE CASCADE,
    parent_comment_id BIGINT REFERENCES forum_comments(id) ON DELETE CASCADE,
    user_id           BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body              TEXT NOT NULL,
    upvotes           INTEGER DEFAULT 0,
    downvotes         INTEGER DEFAULT 0,
    is_accepted       BOOLEAN DEFAULT false,
    depth             INTEGER DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forum_comments_post     ON forum_comments(post_id);
CREATE INDEX IF NOT EXISTS idx_forum_comments_parent   ON forum_comments(parent_comment_id);
CREATE INDEX IF NOT EXISTS idx_forum_comments_user     ON forum_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_forum_comments_accepted ON forum_comments(post_id, is_accepted DESC);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_forum_comments_updated_at'
                   AND tgrelid='forum_comments'::regclass) THEN
        CREATE TRIGGER update_forum_comments_updated_at
            BEFORE UPDATE ON forum_comments
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS forum_votes (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    votable_type VARCHAR(20) NOT NULL CHECK (votable_type IN ('post', 'comment')),
    votable_id   BIGINT NOT NULL,
    vote_type    VARCHAR(10) NOT NULL CHECK (vote_type IN ('upvote', 'downvote')),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, votable_type, votable_id)
);

CREATE INDEX IF NOT EXISTS idx_forum_votes_votable ON forum_votes(votable_type, votable_id);
CREATE INDEX IF NOT EXISTS idx_forum_votes_user    ON forum_votes(user_id);

CREATE OR REPLACE FUNCTION update_post_comment_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE forum_posts SET comment_count = comment_count + 1 WHERE id = NEW.post_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE forum_posts SET comment_count = comment_count - 1 WHERE id = OLD.post_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trigger_update_post_comment_count'
                   AND tgrelid='forum_comments'::regclass) THEN
        CREATE TRIGGER trigger_update_post_comment_count
            AFTER INSERT OR DELETE ON forum_comments
            FOR EACH ROW EXECUTE FUNCTION update_post_comment_count();
    END IF;
END $$;

CREATE OR REPLACE FUNCTION update_vote_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.votable_type = 'post' THEN
            IF NEW.vote_type = 'upvote' THEN UPDATE forum_posts SET upvotes   = upvotes   + 1 WHERE id = NEW.votable_id;
            ELSE                              UPDATE forum_posts SET downvotes = downvotes + 1 WHERE id = NEW.votable_id; END IF;
        ELSE
            IF NEW.vote_type = 'upvote' THEN UPDATE forum_comments SET upvotes   = upvotes   + 1 WHERE id = NEW.votable_id;
            ELSE                              UPDATE forum_comments SET downvotes = downvotes + 1 WHERE id = NEW.votable_id; END IF;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.votable_type = 'post' THEN
            IF OLD.vote_type = 'upvote' THEN UPDATE forum_posts SET upvotes   = upvotes   - 1 WHERE id = OLD.votable_id;
            ELSE                              UPDATE forum_posts SET downvotes = downvotes - 1 WHERE id = OLD.votable_id; END IF;
        ELSE
            IF OLD.vote_type = 'upvote' THEN UPDATE forum_comments SET upvotes   = upvotes   - 1 WHERE id = OLD.votable_id;
            ELSE                              UPDATE forum_comments SET downvotes = downvotes - 1 WHERE id = OLD.votable_id; END IF;
        END IF;
    ELSIF TG_OP = 'UPDATE' AND OLD.vote_type <> NEW.vote_type THEN
        IF NEW.votable_type = 'post' THEN
            IF NEW.vote_type = 'upvote' THEN UPDATE forum_posts SET upvotes = upvotes + 1, downvotes = downvotes - 1 WHERE id = NEW.votable_id;
            ELSE                             UPDATE forum_posts SET upvotes = upvotes - 1, downvotes = downvotes + 1 WHERE id = NEW.votable_id; END IF;
        ELSE
            IF NEW.vote_type = 'upvote' THEN UPDATE forum_comments SET upvotes = upvotes + 1, downvotes = downvotes - 1 WHERE id = NEW.votable_id;
            ELSE                             UPDATE forum_comments SET upvotes = upvotes - 1, downvotes = downvotes + 1 WHERE id = NEW.votable_id; END IF;
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trigger_update_vote_counts'
                   AND tgrelid='forum_votes'::regclass) THEN
        CREATE TRIGGER trigger_update_vote_counts
            AFTER INSERT OR UPDATE OR DELETE ON forum_votes
            FOR EACH ROW EXECUTE FUNCTION update_vote_counts();
    END IF;
END $$;
