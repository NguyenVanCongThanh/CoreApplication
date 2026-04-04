from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"

    # PostgreSQL
    db_host: str = "postgres-lms"
    db_port: int = 5432
    db_user: str = "lms_user"
    db_password: str = "lms_password"
    db_name: str = "lms_db"
    db_min_connections: int = 2
    db_max_connections: int = 10

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
    chat_model: str = "llama-3.1-8b-instant"   # fast, for diagnosis
    quiz_model: str = "llama-3.3-70b-versatile" # smart, for quiz/node extraction

    # Embedding 
    # BAAI/bge-m3: natively multilingual (VI+EN in same vector space),
    # eliminates the translation round-trip from multilingual.py.
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024   # bge-m3 output dim

    vlm_model: str = "llama-3.2-11b-vision-preview"
    vlm_enabled: bool = True

    # E5-style prefix mode — set "e5" for intfloat/multilingual-e5-* models,
    # "bge" for BAAI/bge-m3 (uses "query: " / "passage: " prefixes),
    # "none" for nomic (no prefix needed).
    embedding_prefix_mode: str = "bge"

    # Reranker 
    # bge-reranker-v2-m3 is a cross-encoder that re-scores (query, passage)
    # pairs for much higher precision than cosine alone.
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    use_reranker: bool = True

    # Fetch this many candidates from pgvector, then rerank down to top_k_chunks.
    # Higher = better recall but slower reranking. 15 is a good trade-off.
    rerank_fetch_k: int = 15

    # RAG 
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k_chunks: int = 3

    # When True (bge-m3), skip LLM translation — model handles cross-lingual natively.
    # Set to False only if you revert to nomic-ai model.
    use_native_multilingual: bool = True

    # Celery 
    celery_task_time_limit: int = 3600
    # How many content items to re-embed per batch during migration
    reindex_batch_size: int = 5

    # Internal 
    lms_service_url: str = "http://lms-backend:8081"
    ai_service_secret: str = "ai-service-secret-change-me"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()