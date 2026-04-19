# AI Service API Reference

| Field    | Value                          |
|----------|--------------------------------|
| Version  | 2.2.0                          |
| Status   | Approved                       |
| Date     | 2025-01-01                     |
| Authors  | BDC Team                       |

**Base URL:** `http://ai-service:8000` (Docker internal)
**Authentication:** All endpoints require `X-AI-Secret: {AI_SERVICE_SECRET}` header.
This service is not exposed to the public internet.

---

## Health

### GET /health

Lightweight liveness probe. Used by Docker HEALTHCHECK.

**Authentication:** None required.

**Response — 200 OK**

```json
{
  "status": "ok",
  "service": "ai-service",
  "version": "2.2.0",
  "uptime_seconds": 3600
}
```

---

### GET /health/ready

Readiness probe. Checks all dependencies. Returns 503 if PostgreSQL or Qdrant
is unreachable.

**Authentication:** None required.

**Response — 200 OK**

```json
{
  "ready": true,
  "checks": {
    "postgres_ai": "ok",
    "redis": "ok",
    "qdrant": "ok",
    "neo4j": "ok"
  },
  "service": "ai-service"
}
```

**Response — 503 Service Unavailable** (when a critical dependency is down)

```json
{
  "ready": false,
  "checks": {
    "postgres_ai": "ok",
    "qdrant": "error: connection refused"
  }
}
```

---

### GET /health/kafka

Consumer lag for the ai-worker-group. High lag indicates the worker is falling behind.

**Response — 200 OK**

```json
{
  "group_id": "ai-worker-group",
  "total_lag": 0,
  "status": "ok",
  "topics": {
    "lms.document.uploaded": {"committed": 42, "latest": 42, "lag": 0, "status": "ok"},
    "lms.ai.command":        {"committed": 10, "latest": 10, "lag": 0, "status": "ok"}
  }
}
```

Status values: `ok` (lag < 100), `warning` (100–500), `critical` (> 500).

---

### GET /health/cache

Redis cache statistics.

**Response — 200 OK**

```json
{
  "status": "ok",
  "total_keys": 1247,
  "namespaces": {
    "embeddings": 1200,
    "diagnoses":  42,
    "graphs":     5
  },
  "hit_rate_pct": 87.3,
  "hits": 9821,
  "misses": 1426
}
```

---

## Document Processing

### POST /ai/process-document

Trigger document ingestion into the RAG pipeline via Kafka.

**Request body**

```json
{
  "content_id":   1,
  "course_id":    1,
  "node_id":      null,
  "file_url":     "courses/1/slide.pdf",
  "content_type": "application/pdf"
}
```

| Field          | Type    | Required | Description                                 |
|----------------|---------|----------|---------------------------------------------|
| `content_id`   | integer | Yes      | LMS content primary key                     |
| `course_id`    | integer | Yes      | Course the content belongs to               |
| `node_id`      | integer | No       | Pre-assign to a specific knowledge node     |
| `file_url`     | string  | Yes      | MinIO object key                            |
| `content_type` | string  | Yes      | MIME type                                   |

**Response — 200 OK**

```json
{
  "job_id":  "content-1",
  "status":  "pending",
  "message": "Document queued for processing (content_id=1)"
}
```

**Error responses**

| Status | Condition                             |
|--------|---------------------------------------|
| 403    | Missing or wrong `X-AI-Secret` header |

---

### GET /ai/process-document/{content_id}

Poll document processing status from AI DB.

**Response — 200 OK**

```json
{
  "content_id": 1,
  "course_id":  1,
  "status":     "indexed",
  "error":      null,
  "updated_at": "2025-01-01T00:00:00Z"
}
```

Status values: `pending`, `processing`, `indexed`, `failed`.

**Error responses**

| Status | Condition                      |
|--------|--------------------------------|
| 404    | No status record for content_id |

---

## Auto-Index

### POST /ai/auto-index

Trigger automatic knowledge node extraction + RAG indexing for a file.

**Request body**

```json
{
  "content_id":   1,
  "course_id":    1,
  "file_url":     "courses/1/lecture.pdf",
  "content_type": "application/pdf",
  "force":        false
}
```

When `force=true`, all existing chunks and nodes for `content_id` are deleted before re-indexing.

**Response — 200 OK**

```json
{
  "job_id":     "content-1",
  "content_id": 1,
  "status":     "queued",
  "message":    "Document queued for auto-indexing"
}
```

---

### POST /ai/auto-index/text

Trigger indexing for Markdown text content (no file download required).

**Request body**

```json
{
  "content_id":   1,
  "course_id":    1,
  "title":        "Lesson 1: Introduction",
  "text_content": "## Overview\n\nThis lesson covers...",
  "force":        false
}
```

**Response:** Same as `POST /ai/auto-index`.

---

### GET /ai/auto-index/{content_id}/status

Poll auto-index status.

**Response — 200 OK**

```json
{
  "content_id":    1,
  "status":        "indexed",
  "nodes_created": 5,
  "chunks_created": 42,
  "progress":      100,
  "stage":         "",
  "error":         null
}
```

---

## Error Diagnosis

### POST /ai/diagnose

Analyze a student's wrong answer and return an LLM-grounded explanation.

**Note:** Results are cached in Redis for 24 hours per `(question_id, wrong_answer)` pair.

**Request body**

```json
{
  "student_id":    15,
  "attempt_id":    200,
  "question_id":   88,
  "wrong_answer":  "B",
  "course_id":     1,
  "question_text": "Which design pattern uses a mediator?",
  "question_type": "SINGLE_CHOICE",
  "explanation":   "The mediator pattern...",
  "correct_answer": "A",
  "answer_options": [
    {"option_text": "A", "is_correct": true},
    {"option_text": "B", "is_correct": false}
  ],
  "node_id": 42
}
```

| Field           | Type    | Required | Description                            |
|-----------------|---------|----------|----------------------------------------|
| `student_id`    | integer | Yes      | Student who answered wrong             |
| `attempt_id`    | integer | Yes      | Quiz attempt ID for audit              |
| `question_id`   | integer | Yes      | Question ID (used for cache key)       |
| `wrong_answer`  | string  | Yes      | The wrong answer the student chose     |
| `course_id`     | integer | Yes      | Used to scope RAG retrieval            |
| `question_text` | string  | Yes      | Full question text for LLM context     |
| `node_id`       | integer | No       | Scopes RAG to a specific knowledge node|

**Response — 200 OK**

```json
{
  "explanation":      "The student confused the Mediator and Observer patterns...",
  "gap_type":         "misconception",
  "knowledge_gap":    "Mediator vs Observer distinction",
  "study_suggestion": "Review section 3.2 of the design patterns lecture",
  "confidence":       0.87,
  "source_chunk_id":  10,
  "suggested_documents": [
    {
      "content_id":   5,
      "source_type":  "document",
      "page_number":  12,
      "url_fragment": "#page=12",
      "snippet":      "The Mediator pattern defines an object...",
      "chunk_language": "vi"
    }
  ],
  "language": "vi"
}
```

`gap_type` values: `misconception`, `missing_prerequisite`, `careless`, `other`.

**Error responses**

| Status | Condition                                    |
|--------|----------------------------------------------|
| 403    | Missing or wrong `X-AI-Secret`               |
| 500    | LLM call failed (returns fallback explanation)|

---

## Quiz Generation

### POST /ai/quiz/generate

Generate Bloom's Taxonomy quiz questions for a knowledge node. Results are
DRAFT status and require instructor review before publishing to students.

**Request body**

```json
{
  "node_id":             42,
  "course_id":           1,
  "created_by":          7,
  "bloom_levels":        ["remember", "understand", "apply"],
  "language":            "vi",
  "questions_per_level": 1
}
```

**Response — 200 OK**

```json
{
  "generated": 3,
  "gen_ids":   [101, 102, 103],
  "status":    "DRAFT",
  "message":   "Generated 3 questions. Awaiting instructor review."
}
```

---

### GET /ai/quiz/drafts/{course_id}

List DRAFT questions for instructor review.

**Query parameters:** `node_id` (optional integer filter).

**Response — 200 OK** — array of quiz generation objects with full question data.

---

### POST /ai/quiz/{gen_id}/approve

Approve a DRAFT question. Returns full question data for LMS to create the
`quiz_question` record in its own database.

**Request body**

```json
{
  "reviewer_id": 7,
  "quiz_id":     3,
  "review_note": "Good question, approved as-is"
}
```

**Response — 200 OK** — full question data including `answer_options`.

---

### POST /ai/quiz/{gen_id}/reject

**Request body**

```json
{"reviewer_id": 7, "review_note": "Ambiguous wording"}
```

**Response — 200 OK** — `{"status": "REJECTED"}`

---

## Knowledge Graph

### GET /ai/knowledge-graph/{course_id}

Return all knowledge nodes and edges for a course.
Results are cached in Redis for 5 minutes.

**Query parameters:** `no_cache=true` to bypass Redis cache.

**Response — 200 OK**

```json
{
  "course_id": 1,
  "nodes": [
    {
      "id": 42, "name": "Design Patterns", "name_vi": "Mẫu thiết kế",
      "description": "...", "auto_generated": true,
      "source_content_id": 5, "chunk_count": 12, "level": 0
    }
  ],
  "edges": [
    {"source": 41, "target": 42, "relation_type": "prerequisite",
     "strength": 0.92, "auto_generated": true}
  ]
}
```

---

## Spaced Repetition

### POST /ai/spaced-repetition/record

Record a student's review response and update SM-2 schedule.

**Request body**

```json
{
  "student_id":  15,
  "question_id": 88,
  "course_id":   1,
  "node_id":     42,
  "quality":     4
}
```

`quality` is SM-2 scale 0–5 (0 = complete blackout, 5 = perfect recall).

**Response — 200 OK**

```json
{
  "next_review_date": "2025-01-08",
  "interval_days":    6,
  "easiness_factor":  2.6,
  "repetitions":      2
}
```

---

### GET /ai/spaced-repetition/due/student/{student_id}/course/{course_id}

Get questions due for review today. Used for the login warm-up session.

**Query parameters:** `limit` (default 20).

**Response — 200 OK** — array of `{question_id, node_id, next_review_date, interval_days, node_name}`.
