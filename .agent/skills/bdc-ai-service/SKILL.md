---
name: bdc-ai-service
description: >
  Use when working in ai-service/ — FastAPI + Celery + RAG pipeline.
  Covers: document ingestion, error diagnosis, quiz generation, pgvector, MinIO, Celery tasks.
triggers:
  - ai-service/
  - fastapi
  - celery
  - python
  - rag
  - embedding
  - pgvector
  - quiz gen
  - diagnose
version: "1.0"
authors:
  - BDC Team
requires:
  - bdc-core-orchestrator
---

# BDC AI Service — Developer Skill

## Role & Scope
You are working on **`ai-service/`** — the AI/ML backend for the BDC LMS. Built with Python 3.12 + FastAPI + Celery. Handles RAG (Retrieval-Augmented Generation) document ingestion, error diagnosis for students, and AI-powered quiz generation. Always load the orchestrator skill first, then use this file.

**Framework:** FastAPI (HTTP API) + Celery (async task queue)
**Entry point:** `main.py` (FastAPI app) | `app/worker/celery_app.py` (Celery worker)
**Base URL:** `http://localhost:8000` | Docker internal: `http://ai-service:8000`
**Shares:** LMS PostgreSQL (pgvector) — same DB as lms-service, different connection
**Auth:** All endpoints protected by `X-AI-Secret` header (validated against `AI_SERVICE_SECRET` env var)

---

## Project Structure

```
ai-service/
├── main.py                        ← FastAPI app factory, routers included, /health endpoint
├── requirements.txt               ← ALL dependencies pinned here — update when adding packages
├── Dockerfile
└── app/
    ├── __init__.py
    ├── api/
    │   └── endpoints/
    │       ├── process.py         ← POST /ai/process-document (trigger ingestion)
    │       │                         GET  /ai/process-document/{job_id} (poll status)
    │       ├── diagnose.py        ← POST /ai/diagnose (explain wrong answer)
    │       └── quiz_gen.py        ← POST /ai/quiz/generate
    │                                 POST /ai/quiz/{gen_id}/approve
    │                                 POST /ai/quiz/{gen_id}/reject
    ├── core/
    │   ├── config.py              ← Pydantic Settings — reads all env vars, validates types
    │   ├── database.py            ← SQLAlchemy async engine (asyncpg) + get_db() dependency
    │   └── llm.py                 ← LLM + Embedding model initialization (singleton)
    ├── schemas/
    │   └── __init__.py            ← Pydantic request/response schemas (all public types here)
    ├── services/
    │   ├── chunker.py             ← Text chunking strategy (split PDFs/docs into chunks)
    │   ├── rag_service.py         ← Embedding + vector store upsert (pgvector)
    │   ├── diagnosis_service.py   ← RAG retrieval + LLM prompt for error diagnosis
    │   └── quiz_service.py        ← LLM prompt chain for quiz generation + DB write
    └── worker/
        └── celery_app.py          ← Celery app + all task definitions
```

---

## Architecture — Request Flow

### Synchronous Endpoints (FastAPI)
```
HTTP Request (from lms-service)
    ↓
main.py router
    ↓
api/endpoints/*.py
    ├─ Validate X-AI-Secret header
    ├─ Parse + validate request (Pydantic)
    ├─ For heavy tasks → task.delay() → return {job_id} immediately  ← NEVER BLOCK
    └─ For light tasks → call service → return result
```

### Asynchronous Tasks (Celery)
```
Celery Task (triggered via .delay())
    ↓
app/worker/celery_app.py
    ↓
services/*.py (chunker → rag_service → DB write)
    ↓
PostgreSQL pgvector / Redis result backend
```

**Critical rule: ANY task taking > 2 seconds MUST use Celery. Never block the FastAPI event loop.**

---

## Environment Variables

All read via `app/core/config.py` (Pydantic `BaseSettings`):

```python
# Database (shared with lms-service — same PostgreSQL, different connection pool)
DATABASE_URL          # postgresql+asyncpg://user:pass@postgres-lms:5432/lmsdb
                      # Note: asyncpg driver, NOT psycopg2

# Redis (broker for Celery + result backend)
REDIS_URL             # redis://redis:6379/0

# LLM / Embedding (self-hosted or API)
LLM_MODEL             # e.g., "gpt-4o", "local/mistral-7b"
EMBEDDING_MODEL       # e.g., "text-embedding-3-small", "local/bge-m3"
OPENAI_API_KEY        # if using OpenAI

# MinIO (for downloading uploaded content files)
MINIO_ENDPOINT        # minio:9000 (internal Docker hostname)
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
MINIO_BUCKET          # lms-files

# Security
AI_SERVICE_SECRET     # Must match lms-service AI_SERVICE_SECRET env var

# Celery
CELERY_BROKER_URL     # Same as REDIS_URL
CELERY_RESULT_BACKEND # redis://redis:6379/1  (separate DB from broker)
```

**When adding a new env var:**
1. Add field to `app/core/config.py` Settings class
2. Add to root `.env.example` with `<TODO>` placeholder
3. Add to `ai-service` block in root `docker-compose.yml`

---

## Adding a New Feature — Standard Workflow

### Step 1: Define Pydantic Schemas
```python
# app/schemas/__init__.py (or a dedicated file imported here)
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class MyFeatureRequest(BaseModel):
    content_id: int = Field(..., description="LMS content ID")
    course_id: int = Field(..., description="LMS course ID")
    language: str = Field(default="vi", description="Language code: 'vi' or 'en'")

class MyFeatureResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    message: str = "Task queued"
```

### Step 2: Write the Service
```python
# app/services/my_feature_service.py
from app.core.config import settings
from app.core.database import get_db_session
from app.core.llm import get_embedding_model, get_llm
import logging

logger = logging.getLogger(__name__)

async def process_my_feature(content_id: int, course_id: int, language: str) -> dict:
    """
    Core logic for my feature.
    Called from Celery task — must be async-safe.
    """
    async with get_db_session() as db:
        try:
            # 1. Fetch data from DB
            # 2. Call LLM / embedding
            # 3. Write results to DB
            # 4. Return result dict
            pass
        except Exception as e:
            logger.error(f"my_feature failed content_id={content_id}: {e}", exc_info=True)
            raise  # Celery will mark task as FAILURE
```

### Step 3: Register as Celery Task
```python
# app/worker/celery_app.py — add to existing tasks

@celery.task(
    bind=True,
    name="tasks.my_feature",
    max_retries=3,
    default_retry_delay=60,   # seconds between retries
    acks_late=True,           # only ack after task completes (no message loss on crash)
)
def run_my_feature(self, content_id: int, course_id: int, language: str):
    """
    Celery task wrapper — always sync wrapper around async logic.
    Use asyncio.run() to call async service functions.
    """
    import asyncio
    try:
        result = asyncio.run(process_my_feature(content_id, course_id, language))
        return {"status": "completed", "result": result}
    except Exception as exc:
        logger.error(f"run_my_feature failed: {exc}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### Step 4: Create the Endpoint
```python
# app/api/endpoints/my_feature.py
from fastapi import APIRouter, Header, HTTPException, Depends
from app.core.config import settings
from app.schemas import MyFeatureRequest, MyFeatureResponse
from app.worker.celery_app import run_my_feature

router = APIRouter()

def verify_secret(x_ai_secret: str = Header(..., alias="X-AI-Secret")):
    """Dependency — validates shared secret from lms-service."""
    if x_ai_secret != settings.AI_SERVICE_SECRET:
        raise HTTPException(status_code=403, detail="Invalid AI service secret")

@router.post("/my-feature", response_model=MyFeatureResponse)
async def start_my_feature(
    req: MyFeatureRequest,
    _: None = Depends(verify_secret),
):
    """
    Trigger async processing. Returns job_id immediately.
    Client polls GET /my-feature/{job_id} for status.
    """
    task = run_my_feature.delay(req.content_id, req.course_id, req.language)
    return MyFeatureResponse(job_id=task.id, status="pending")

@router.get("/my-feature/{job_id}", response_model=MyFeatureResponse)
async def get_my_feature_status(
    job_id: str,
    _: None = Depends(verify_secret),
):
    """Poll task status. lms-service polls every 5s."""
    from celery.result import AsyncResult
    result = AsyncResult(job_id)

    if result.state == "PENDING":
        return MyFeatureResponse(job_id=job_id, status="pending")
    elif result.state == "SUCCESS":
        return MyFeatureResponse(job_id=job_id, status="completed", message="Done")
    elif result.state == "FAILURE":
        return MyFeatureResponse(job_id=job_id, status="failed", message=str(result.info))
    else:
        return MyFeatureResponse(job_id=job_id, status="processing")
```

### Step 5: Register Router in main.py
```python
# main.py
from app.api.endpoints.my_feature import router as my_feature_router

app.include_router(my_feature_router, prefix="/ai", tags=["my-feature"])
```

---

## Security — X-AI-Secret Validation

**Every endpoint MUST use the `verify_secret` dependency. No exceptions.**

```python
# Correct pattern — always as a dependency
@router.post("/endpoint")
async def my_endpoint(
    req: MyRequest,
    _: None = Depends(verify_secret),   # ← Required on all routes
):
    ...

# The dependency (defined once, reused everywhere):
def verify_secret(x_ai_secret: str = Header(..., alias="X-AI-Secret")):
    if x_ai_secret != settings.AI_SERVICE_SECRET:
        raise HTTPException(status_code=403, detail="Invalid AI service secret")
```

**Missing this on any endpoint = unauthenticated access to AI capabilities and DB.**

---

## Core Feature: Document Processing (RAG Ingestion)

### What it does
When a teacher uploads a PDF/document to LMS, lms-service calls `/ai/process-document`. The Celery worker:
1. Downloads the file from MinIO
2. Extracts text
3. Chunks the text (chunker.py)
4. Embeds each chunk (embedding model)
5. Upserts into `document_chunks` table (pgvector)
6. Updates `knowledge_nodes` in `ai_knowledge_graph` table
7. Updates content `status = 'ready'` in LMS DB

### Key tables written to (defined in lms-service migration 010)
```sql
document_chunks (
    id, content_id, course_id, chunk_index,
    chunk_text, chunk_hash,        -- chunk_hash has UNIQUE constraint (migration 011)
    embedding vector(1536),        -- pgvector
    status, created_at
)

knowledge_nodes (
    id, course_id, label, description,
    node_type, parent_id
)
```

### Chunking Strategy (chunker.py)
```python
# Correct pattern: fixed-size with overlap to preserve context
CHUNK_SIZE = 1000      # characters
CHUNK_OVERLAP = 200    # characters overlap between chunks

def chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks.
    Overlap ensures context isn't lost at chunk boundaries.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP  # slide with overlap
    return chunks

# chunk_hash = SHA256(chunk_text) — use for deduplication
import hashlib
chunk_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
```

### Upsert Pattern (idempotent — safe to re-run)
```python
# Use INSERT ... ON CONFLICT DO UPDATE to handle re-processing
await db.execute("""
    INSERT INTO document_chunks
        (content_id, course_id, chunk_index, chunk_text, chunk_hash, embedding, status)
    VALUES ($1, $2, $3, $4, $5, $6::vector, 'ready')
    ON CONFLICT (chunk_hash)
    DO UPDATE SET
        embedding = EXCLUDED.embedding,
        status = 'ready',
        updated_at = CURRENT_TIMESTAMP
""", content_id, course_id, idx, chunk, chunk_hash, embedding_str)
```

---

## Core Feature: Error Diagnosis (RAG + LLM)

### What it does
When a student gets a wrong answer, the frontend shows a "diagnose" button. lms-service calls `/ai/diagnose`, which:
1. Retrieves question context from LMS DB
2. Performs cosine similarity search on `document_chunks` to find relevant content
3. Builds a prompt with retrieved context + wrong answer
4. Calls LLM for explanation
5. Returns explanation + `deep_link` (URL for relevant course content)

### Response Schema
```python
class DiagnoseResponse(BaseModel):
    explanation: str           # LLM explanation in student's language
    deep_link: Optional[str]   # URL to the content section that covers this topic
    confidence: float          # 0.0 - 1.0, based on retrieval similarity score
    sources: list[str]         # chunk_text snippets used as context
```

### Retrieval Pattern (RAG)
```python
async def retrieve_relevant_chunks(
    query_embedding: list[float],
    course_id: int,
    top_k: int = 5,
    min_similarity: float = 0.30,
) -> list[dict]:
    """
    Cosine similarity search via pgvector <=> operator.
    min_similarity filters out irrelevant chunks.
    """
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    rows = await db.fetch("""
        SELECT chunk_text, content_id,
               1 - (embedding <=> $1::vector) AS similarity
        FROM document_chunks
        WHERE course_id = $2
          AND status = 'ready'
          AND 1 - (embedding <=> $1::vector) >= $3
        ORDER BY embedding <=> $1::vector
        LIMIT $4
    """, embedding_str, course_id, min_similarity, top_k)
    return rows

# WRONG: Do NOT use <-> (L2 distance) for text similarity
# CORRECT: Use <=> (cosine distance) — better for normalized embeddings
```

### LLM Prompt Pattern
```python
DIAGNOSIS_PROMPT = """
Bạn là giáo viên đang giải thích lỗi sai cho học sinh.

**Câu hỏi:** {question_text}
**Câu trả lời của học sinh:** {wrong_answer}
**Đáp án đúng:** {correct_answer}

**Tài liệu liên quan:**
{context_chunks}

Hãy giải thích ngắn gọn (tối đa 3 đoạn):
1. Tại sao câu trả lời của học sinh sai
2. Khái niệm đúng cần nhớ
3. Gợi ý để không mắc lỗi này lần sau

Trả lời bằng tiếng Việt, thân thiện và khuyến khích.
"""

# Always use f-strings or .format() — never concatenate user input directly into prompt
prompt = DIAGNOSIS_PROMPT.format(
    question_text=question.text,
    wrong_answer=wrong_answer,
    correct_answer=correct_answer,
    context_chunks="\n\n".join(f"[{i+1}] {c['chunk_text']}" for i, c in enumerate(chunks)),
)
```

---

## Core Feature: Quiz Generation (LLM + Human-in-the-Loop)

### What it does
Teacher clicks "AI Generate Quiz" in LMS frontend. lms-service calls `/ai/quiz/generate`. The Celery worker:
1. Retrieves `knowledge_node` context from DB
2. Fetches relevant `document_chunks` via vector search
3. Calls LLM to generate questions at specified Bloom's Taxonomy levels
4. Saves questions as `status = 'DRAFT'` in `quiz_questions` table
5. Teacher reviews + approves/rejects via `/ai/quiz/{gen_id}/approve` or `/reject`
6. On approval: status → `'PUBLISHED'`

### Bloom's Taxonomy Levels Supported
```python
BLOOM_LEVELS = {
    "remember":    "Nhớ lại thông tin — câu hỏi MCQ cơ bản",
    "understand":  "Giải thích khái niệm — câu hỏi phân biệt/mô tả",
    "apply":       "Áp dụng vào tình huống — câu hỏi thực tế",
    "analyze":     "Phân tích — so sánh, tìm nguyên nhân",
    "evaluate":    "Đánh giá — lý giải quan điểm",
    "create":      "Sáng tạo — tổng hợp giải pháp",
}
```

### Quiz Generation Request/Response
```python
class QuizGenerateRequest(BaseModel):
    node_id: int                           # knowledge_node ID to generate for
    course_id: int
    created_by: int                        # teacher's user_id
    bloom_levels: list[str] = ["remember", "understand", "apply"]
    language: str = "vi"                   # "vi" or "en"
    questions_per_level: int = Field(default=1, ge=1, le=5)

class QuizGenerateResponse(BaseModel):
    gen_id: str                            # Celery task ID — use to poll + approve
    status: str = "pending"
    questions_count: int = 0
```

### LLM Output Schema (Structured JSON)
```python
# Prompt the LLM to return ONLY valid JSON — no markdown backticks, no prose
QUIZ_SYSTEM_PROMPT = """
Bạn là chuyên gia tạo câu hỏi trắc nghiệm học thuật.
Trả lời CHỈ bằng JSON hợp lệ theo schema sau, không có text khác:
{
  "questions": [
    {
      "question_text": "...",
      "question_type": "multiple_choice",
      "bloom_level": "remember",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct_answer": "A",
      "explanation": "Giải thích tại sao đáp án đúng...",
      "difficulty": "easy|medium|hard"
    }
  ]
}
"""

# Always strip and parse carefully — LLMs sometimes add backticks
import json, re

def parse_llm_json(raw: str) -> dict:
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")
```

---

## Database Access Pattern

The AI service uses **SQLAlchemy async** (asyncpg driver), NOT the same sync connection as lms-service.

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# DATABASE_URL must use postgresql+asyncpg:// scheme
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # auto-reconnect on stale connections
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Context manager for clean resource management
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# FastAPI Dependency (for endpoints)
async def get_db():
    async with get_db_session() as session:
        yield session
```

### Raw SQL with asyncpg (preferred for complex queries)
```python
# For pgvector queries and complex joins, use raw SQL via execute()
async with get_db_session() as db:
    result = await db.execute(
        text("""
            SELECT id, chunk_text,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM document_chunks
            WHERE course_id = :course_id AND status = 'ready'
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """),
        {"embedding": embedding_str, "course_id": course_id, "limit": top_k}
    )
    rows = result.fetchall()
```

### Celery Task DB Access (sync context)
```python
# Celery tasks are sync — use asyncio.run() to call async DB functions
@celery.task(bind=True)
def my_task(self, content_id: int):
    import asyncio
    asyncio.run(_async_task_body(content_id))

async def _async_task_body(content_id: int):
    async with get_db_session() as db:
        # ... your logic
```

---

## MinIO File Download (in Celery Tasks)

When processing uploaded documents, download from MinIO before extracting text:

```python
from minio import Minio
from app.core.config import settings
import io

def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,   # HTTP inside Docker network
    )

def download_file_from_minio(object_key: str) -> bytes:
    """Download file to memory. Only for files < 50MB."""
    client = get_minio_client()
    response = client.get_object(settings.MINIO_BUCKET, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()

# For large files — stream instead of loading all into RAM
def stream_file_from_minio(object_key: str):
    client = get_minio_client()
    response = client.get_object(settings.MINIO_BUCKET, object_key)
    try:
        for chunk in response.stream(amt=8192):
            yield chunk
    finally:
        response.close()
        response.release_conn()
```

---

## LLM & Embedding Initialization (app/core/llm.py)

```python
# Singleton pattern — models load once at startup, reused across requests
_llm = None
_embedding_model = None

def get_llm():
    global _llm
    if _llm is None:
        # Initialize based on settings.LLM_MODEL
        # e.g., OpenAI, local Ollama, etc.
        _llm = _init_llm()
    return _llm

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = _init_embedding_model()
    return _embedding_model

# Always check model is loaded in health endpoint:
@app.get("/health")
async def health():
    try:
        emb = get_embedding_model()
        return {"status": "healthy", "embedding_model": settings.EMBEDDING_MODEL}
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)
```

---

## Celery Configuration

```python
# app/worker/celery_app.py
from celery import Celery
from app.core.config import settings

celery = Celery(
    "bdc_ai_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=86400,          # task results kept 24h in Redis
    task_track_started=True,       # enables STARTED state (visible to polling)
    worker_prefetch_multiplier=1,  # process one task at a time (memory safety for LLM)
    task_acks_late=True,           # ack only after completion — no data loss on crash
    worker_max_tasks_per_child=50, # restart worker every 50 tasks (prevents memory leak)
)
```

### Celery Task States — What lms-service polls for
```
PENDING    → task is queued, not started yet
STARTED    → worker picked it up (visible because task_track_started=True)
SUCCESS    → completed successfully
FAILURE    → exception raised, result.info contains the exception
RETRY      → being retried after transient failure
```

### Starting Workers
```bash
# Development — 1 worker, verbose logging
celery -A app.worker.celery_app worker --loglevel=DEBUG --concurrency=1

# Production — more concurrency (careful with LLM memory)
celery -A app.worker.celery_app worker --loglevel=INFO --concurrency=2

# Monitor tasks (flower web UI — optional)
celery -A app.worker.celery_app flower --port=5555
```

---

## Error Handling Patterns

### FastAPI Endpoints — Always Return Structured Errors
```python
from fastapi import HTTPException
from fastapi.responses import JSONResponse

# For expected errors (bad input, not found)
raise HTTPException(status_code=400, detail="content_id not found in LMS DB")

# For auth errors
raise HTTPException(status_code=403, detail="Invalid AI service secret")

# For service errors (LLM failure, etc.)
raise HTTPException(status_code=503, detail="LLM service unavailable")

# Global exception handler in main.py
@app.exception_handler(Exception)
async def generic_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)
    # NEVER expose stack traces or internal error details to clients
```

### Celery Tasks — Retry on Transient Failures
```python
@celery.task(bind=True, max_retries=3)
def run_task(self, *args):
    try:
        # ... task logic
    except (ConnectionError, TimeoutError) as exc:
        # Transient failures → retry
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
    except ValueError as exc:
        # Logic errors → do NOT retry (will always fail)
        logger.error(f"Non-retryable task failure: {exc}")
        raise  # marks task as FAILURE immediately
```

---

## Python Code Style

### Naming Conventions
```python
# Files: snake_case
rag_service.py          # ✅
ragService.py           # ❌

# Classes: PascalCase
class DiagnosisService:  # ✅
class diagnosis_service: # ❌

# Functions/variables: snake_case
async def process_document(content_id: int) -> dict:  # ✅
async def processDocument(contentId):                  # ❌

# Constants: SCREAMING_SNAKE_CASE
CHUNK_SIZE = 1000       # ✅
chunkSize = 1000        # ❌

# Async functions: always use async/await properly
async def fetch_data():           # ✅ correctly async
    return await db.fetch(...)

def fetch_data():                 # ❌ sync function calling async code = deadlock
    return asyncio.run(db.fetch(...))
```

### Type Hints — Always Required
```python
# ✅ All function signatures must have type hints
async def embed_text(text: str, model: str = "default") -> list[float]:
    ...

# ✅ Pydantic for all request/response models — no raw dicts crossing API boundaries
class ProcessRequest(BaseModel):
    content_id: int
    file_url: str

# ❌ Never accept/return untyped dicts in public APIs
async def process(data: dict) -> dict:  # BAD
    ...
```

### Logging — Structured, Never print()
```python
import logging
logger = logging.getLogger(__name__)  # one per module

# ✅ Correct log levels
logger.debug(f"Embedding chunk {idx}/{total}, length={len(chunk)}")
logger.info(f"Document processing completed content_id={content_id}, chunks={n_chunks}")
logger.warning(f"Low similarity score {score:.2f} for diagnosis query")
logger.error(f"Failed to process document content_id={content_id}: {exc}", exc_info=True)

# ❌ Never use print() in production code — it doesn't go to log files
print(f"Processing done")  # BAD
```

---

## Dependencies Management

`requirements.txt` is the single source of truth. **Always pin exact versions.**

```
# Pattern: package==x.y.z
fastapi==0.115.0
uvicorn[standard]==0.30.0
celery==5.4.0
redis==5.0.8
sqlalchemy[asyncio]==2.0.36
asyncpg==0.29.0
pydantic==2.9.0
pydantic-settings==2.5.0
minio==7.2.9
openai==1.50.0           # if using OpenAI
sentence-transformers==3.2.0  # if using local embeddings
pypdf2==3.0.1            # PDF text extraction
python-multipart==0.0.12
```

**Workflow when adding a dependency:**
```bash
pip install new-package          # Install locally
pip freeze | grep new-package    # Get exact pinned version
# Add pinned version to requirements.txt
# Test: docker compose up -d --build ai-service
```

---

## Build & Run

```bash
# Local development (without Docker)
cd ai-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Start Celery worker locally
celery -A app.worker.celery_app worker --loglevel=DEBUG --concurrency=1

# Docker (preferred)
docker compose up -d --build ai-service
docker compose logs -f ai-service

# Test endpoints manually
curl localhost:8000/health
curl -X POST localhost:8000/ai/diagnose \
  -H "X-AI-Secret: $AI_SERVICE_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"student_id": 1, "attempt_id": 1, "question_id": 1, "wrong_answer": "A", "course_id": 1}'
```

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_diagnosis.py -v

# Test Celery tasks (use CELERY_TASK_ALWAYS_EAGER=True for sync execution in tests)
```

### Testing Celery Tasks Synchronously
```python
# conftest.py
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def celery_eager(settings):
    """Run Celery tasks synchronously in tests — no broker needed."""
    with patch.dict("os.environ", {"CELERY_TASK_ALWAYS_EAGER": "True"}):
        yield

# test_processing.py
def test_process_document():
    result = run_document_processing.delay(content_id=1, course_id=1, file_url="test.pdf")
    assert result.get(timeout=10)["status"] == "completed"
```

### Mock LLM in Tests
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_diagnosis():
    with patch("app.services.diagnosis_service.get_llm") as mock_llm:
        mock_llm.return_value.agenerate = AsyncMock(return_value=mock_llm_response)
        result = await diagnose_error(student_id=1, question_id=1, wrong_answer="A")
        assert result["explanation"]
        assert 0.0 <= result["confidence"] <= 1.0
```

---

## Code Quality Checklist

```
[ ] Every endpoint has X-AI-Secret validation via Depends(verify_secret)
[ ] No blocking calls in async FastAPI endpoints (no time.sleep, no sync DB queries)
[ ] All heavy work (> 2s) delegated to Celery via .delay()
[ ] Celery tasks have max_retries and acks_late=True
[ ] LLM JSON output parsed with parse_llm_json() (handles markdown fences)
[ ] All new env vars added to config.py + .env.example + docker-compose.yml
[ ] requirements.txt updated with pinned version for any new dependency
[ ] New router registered in main.py with correct prefix
[ ] No print() statements — use logging module
[ ] Type hints on all function signatures
[ ] Pydantic schemas for all request/response types
[ ] Error responses never expose stack traces or internal details
[ ] Embedding uses cosine distance (<=> operator), not L2 (<->)
[ ] chunk_hash used for deduplication (ON CONFLICT DO UPDATE)
[ ] MinIO files streamed for large files — not loaded entirely into RAM
[ ] Worker configured with worker_max_tasks_per_child to prevent memory leaks
```

---

## Known Issues & TODOs

1. **No `app/schemas/` files** beyond `__init__.py` — all schemas currently live in endpoint files. Should be refactored to `app/schemas/process.py`, `app/schemas/diagnosis.py`, etc.
2. **Celery worker memory** — LLM models can use 4–8GB RAM. Set `worker_max_tasks_per_child=50` to reclaim memory, and `concurrency=1` unless you have enough VRAM for multiple instances.
3. **Missing retry logic on MinIO download** — add exponential backoff for transient MinIO connection errors.
4. **`DATABASE_URL` scheme** — must use `postgresql+asyncpg://` NOT `postgresql://`. Wrong scheme causes silent import-time failure.
5. **Celery result expiry** — set `result_expires=86400` (24h). Results for completed tasks auto-delete from Redis. lms-service should not poll after > 24h.
6. **Language support** — prompts currently mixed Vietnamese/English. Standardize: always use `language` param to select prompt template.