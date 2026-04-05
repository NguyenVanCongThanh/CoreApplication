from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"

    # ── LMS PostgreSQL (read-only access to LMS entities) ────────────────────
    # Used for: quiz_questions, section_content, quiz_attempts, users, courses
    db_host: str = "postgres-lms"
    db_port: int = 5432
    db_user: str = "lms_user"
    db_password: str = "lms_password"
    db_name: str = "lms_db"
    db_min_connections: int = 2
    db_max_connections: int = 10

    # ── AI PostgreSQL (read-write for all AI-domain data) ────────────────────
    # Used for: knowledge_nodes, document_chunks, ai_diagnoses, flashcards, …
    # Isolated instance — no shared state with LMS.
    ai_db_host: str = "postgres-ai"
    ai_db_port: int = 5432
    ai_db_user: str = "ai_user"
    ai_db_password: str = "ai_password"
    ai_db_name: str = "ai_db"
    ai_db_min_connections: int = 2
    ai_db_max_connections: int = 15  # AI service is write-heavy

    # Redis
    redis_host: str = "redis-lms"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 1

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "lms-files"
    minio_use_ssl: bool = False

    # Groq LLM
    groq_api_key: str = ""
    chat_model: str = "llama-3.1-8b-instant"
    quiz_model: str = "llama-3.3-70b-versatile"

    # Embedding
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024
    vlm_model: str = "llama-3.2-11b-vision-preview"
    vlm_enabled: bool = True
    embedding_prefix_mode: str = "bge"

    # Reranker
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    use_reranker: bool = True
    rerank_fetch_k: int = 15

    # RAG
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k_chunks: int = 3
    use_native_multilingual: bool = True

    # Celery
    celery_task_time_limit: int = 3600
    reindex_batch_size: int = 5

    # Internal
    lms_service_url: str = "http://lms-backend:8081"
    ai_service_secret: str = "ai-service-secret-change-me"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def lms_database_url(self) -> str:
        """asyncpg DSN for LMS PostgreSQL (entity reads)."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def ai_database_url(self) -> str:
        """asyncpg DSN for AI PostgreSQL (all AI data)."""
        return (
            f"postgresql+asyncpg://{self.ai_db_user}:{self.ai_db_password}"
            f"@{self.ai_db_host}:{self.ai_db_port}/{self.ai_db_name}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Legacy alias — kept for any code that reads settings.database_url
    @property
    def database_url(self) -> str:
        return self.lms_database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()