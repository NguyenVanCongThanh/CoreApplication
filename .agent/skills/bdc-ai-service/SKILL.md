---
name: bdc-ai-service
description: >
  Use when working in ai-service/ — Kafka Worker + FastAPI + RAG pipeline.
  Covers: asynchronous document ingestion, error diagnosis, quiz generation, pgvector, MinIO.
triggers:
  - ai-service/
  - fastapi
  - kafka
  - python
  - rag
  - embedding
  - pgvector
  - quiz gen
  - diagnose
version: "2.0"
authors:
  - BDC Team
requires:
  - bdc-core-orchestrator
---

# BDC AI Service — Developer Skill

## Role & Scope
You are working on **`ai-service/`** — the AI/ML backend for the BDC LMS. Built with Python 3.12 + Event-Driven Kafka Workers. Handles RAG (Retrieval-Augmented Generation) document ingestion, error diagnosis, and AI-powered quiz generation.

**Framework:** FastAPI (HTTP sync polling) + `aiokafka` (Async event consumer/producer)
**Entry point:** `main.py` (FastAPI app) | `app/worker/kafka_worker.py` (Kafka worker loop)
**Base URL:** `http://localhost:8000` | Docker internal: `http://ai-service:8000`
**Auth:** Endpoints protected by `X-AI-Secret` header (`AI_SERVICE_SECRET`)

---

## Architecture — Event-Driven Workflow

We strictly use an Event-Driven Architecture via Kafka for all heavy AI workloads to prevent HTTP timeouts.

### Event Loop Workflow
1. **Trigger:** `lms-service` pushes a command event (e.g., `GENERATE_QUIZ`) to the `lms.ai.command` Kafka topic.
2. **Consume:** `app/worker/kafka_worker.py` continuously polls this topic using `aiokafka.AIOKafkaConsumer`.
3. **Execute:** The worker dispatches to the relevant service (`rag_service.py`, `quiz_service.py`), which uses the LLM/DB.
4. **Publish:** Upon completion (or failure), `publish_ai_job_status` (in `app/worker/kafka_producer.py`) pushes the result back to the `ai.job.status` Kafka topic for `lms-service` to ingest into Redis.

**Crucial Rules:**
- NEVER use synchronous HTTP requests for tasks taking > 2 seconds.
- ALL long-running features must be executed within `kafka_worker.py`.

---

## Project Structure

```
ai-service/
├── main.py                        ← FastAPI app (No Celery routers anymore)
├── requirements.txt               ← Dependencies (aiokafka, asyncpg, etc.)
└── app/
    ├── api/endpoints/             ← Health endpoints and synchronous queries
    ├── core/
    │   ├── database.py            ← SQLAlchemy async engine (asyncpg)
    │   ├── llm.py                 ← LLM/Embedding model initialization (singleton)
    │   └── config.py              ← Pydantic environment configurations
    ├── schemas/                   ← Pydantic data structures
    ├── services/
    │   ├── rag_service.py         ← Embedding + pgvector upserts
    │   ├── diagnosis_service.py   ← RAG retrieval + LLM
    │   └── quiz_service.py        ← LLM chain + PG writes requests
    └── worker/
        ├── kafka_worker.py        ← MAIN Event Loop (Subscribes to lms.ai.command)
        └── kafka_producer.py      ← Publishes to ai.job.status
```

---

## Adding a New AI Worker Feature — Standard Workflow

### Step 1: Define the Payload Schema
Define the generic data structure that `lms-service` will serialize to Kafka.

### Step 2: Implement the Core AI Service
```python
# app/services/my_feature.py
async def process_my_feature(node_id: int):
    # Perform pgvector fetch, build prompt, call LLM...
    return {"message": "Success", "data": [...]}
```

### Step 3: Register Command in `kafka_worker.py`
Inside the main `consume_loop`, add a dispatch block for the new `command_type`:

```python
# app/worker/kafka_worker.py
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(consume_loop())

async def process_ai_command(payload: dict):
    command_type = payload.get("command_type")
    job_id = payload.get("job_id")
    
    try:
        if command_type == "MY_NEW_FEATURE":
            await publish_ai_job_status(job_id, "processing")
            result = await process_my_feature(payload["node_id"])
            await publish_ai_job_status(job_id, "completed", result=result)
    except Exception as e:
        await publish_ai_job_status(job_id, "failed", error=str(e))
```

---

## Python Best Practices
- **Singleton Initialization:** Utilize `app.core.llm.get_llm()` to prevent out-of-memory errors. The model must load exactly once.
- **Async Database Sessions:** Always use `asyncpg` within `AsyncSession Local`. Never run synchronous database operations on the main event loop.
- **Error Handling in Workers:** Wrap worker blocks in `try-except` blocks. Never let an isolated task crash the entire `consume_loop`. Always broadcast failures back to `ai.job.status`.