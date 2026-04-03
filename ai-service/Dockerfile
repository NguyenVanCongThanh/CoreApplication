FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN pip install --no-cache-dir --upgrade "pip==24.3.1"

RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appuser \
 && useradd  --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

COPY --from=builder /wheels          /tmp/wheels
COPY                requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir \
        --no-index \
        --find-links=/tmp/wheels \
        -r /tmp/requirements.txt \
 && rm -rf /tmp/wheels /tmp/requirements.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/models \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    TOKENIZERS_PARALLELISM=false

RUN mkdir -p /app/.cache/models \
 && chown -R appuser:appuser /app/.cache

RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('BAAI/bge-m3', cache_folder='/app/.cache/models'); \
    CrossEncoder('BAAI/bge-reranker-v2-m3', cache_folder='/app/.cache/models')" \
 && chown -R appuser:appuser /app/.cache

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--loop", "uvloop", \
     "--workers", "2"]