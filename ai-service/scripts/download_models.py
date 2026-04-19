"""
Chạy một lần khi container start (nếu chưa có model trong volume).
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = os.getenv("SENTENCE_TRANSFORMERS_HOME", "/app/.cache/models")
EMBED_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
USE_RERANKER  = os.getenv("USE_RERANKER", "true").lower() == "true"


def model_exists(name: str) -> bool:
    # sentence-transformers lưu theo tên folder (dấu / thành __)
    folder = name.replace("/", "__")
    path = os.path.join(CACHE_DIR, folder)
    return os.path.isdir(path) and any(
        f.endswith(".safetensors") or f.endswith(".bin")
        for f in os.listdir(path)
    )


def download_embed():
    if model_exists(EMBED_MODEL):
        logger.info(f"✓ Embed model đã có: {EMBED_MODEL}")
        return
    logger.info(f"⬇ Downloading embed model: {EMBED_MODEL}")
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(EMBED_MODEL, cache_folder=CACHE_DIR)
    logger.info("✓ Embed model OK")


def download_reranker():
    if not USE_RERANKER:
        logger.info("Reranker disabled, skip.")
        return
    if model_exists(RERANKER_MODEL):
        logger.info(f"✓ Reranker model đã có: {RERANKER_MODEL}")
        return
    logger.info(f"⬇ Downloading reranker: {RERANKER_MODEL}")
    from sentence_transformers.cross_encoder import CrossEncoder
    CrossEncoder(RERANKER_MODEL, cache_dir=CACHE_DIR)
    logger.info("✓ Reranker OK")


if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)
    download_embed()
    download_reranker()
    logger.info("Tất cả model đã sẵn sàng.")