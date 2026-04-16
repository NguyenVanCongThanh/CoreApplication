---
name: bdc-lms-service
description: >
  Use when working in lms-service/ — Go 1.24 + Gin + PostgreSQL + Redis.
  Covers: courses, quizzes, enrollments, Event-Driven AI integration (Kafka).
triggers:
  - lms-service/
  - golang
  - gin
  - lms
  - kafka
version: "2.0"
authors:
  - BDC Team
requires:
  - bdc-core-orchestrator
---

# BDC LMS Service — Developer Skill

## Role & Scope
You are working on **`lms-service/`** — the Learning Management System backend. Built with Go 1.24 + Gin + PostgreSQL (pgvector) + Redis + Kafka. Handles courses, content, quizzes, forum, progress tracking, and orchestrates asynchronous AI workloads via Kafka event events.

**Entry point:** `cmd/api/main.go`
**Base URL:** `http://localhost:8081` | Docker internal: `http://lms-backend:8081`

---

## Architecture — Event-Driven AI Integration

We strictly use an Event-Driven Architecture via **Kafka** for all heavy AI workloads (diagnosing errors, generating quizzes, generating flashcards, processing documents) to prevent HTTP timeouts.

### Workflow: `LMS` -> `Kafka` -> `AI-Service` -> `LMS`
1. **Trigger:** The client hits an endpoint (e.g., `POST /ai/quiz`).
2. **Publish Command:** `lms-service` generates a UUID `job_id`, constructs an `AICommandEvent`, and pushes it to the `lms.ai.command` Kafka topic.
3. **Acceptance:** The endpoint immediately returns `202 Accepted` with the `job_id`.
4. **Processing (AI):** The AI-service processes the event and pushes continuous statuses to `ai.job.status`.
5. **Consume Status:** The `StartAIJobStatusConsumer` inside `lms-service` listens to `ai.job.status` and writes the exact payload into Redis via `redisClient.Set(ctx, "ai_job:" + job_id)`.
6. **Polling:** The client long-polls or interval-polls `GET /ai/jobs/:jobId/status` mapping directly to the Redis cache.

### Event Structs (pkg/kafka/events.go)
```go
type AICommandEvent struct {
    JobID       string                 `json:"job_id"`
    CommandType string                 `json:"command_type"`
    Payload     map[string]interface{} `json:"payload"`
    Timestamp   string                 `json:"timestamp"`
}

type AIJobStatusEvent struct {
    JobID     string      `json:"job_id"`
    Status    string      `json:"status"` // "pending", "processing", "completed", "failed"
    Result    interface{} `json:"result,omitempty"`
    Error     string      `json:"error,omitempty"`
}
```

---

## Project Structure

```
lms-service/
├── cmd/api/main.go               ← Init config, DI, Gin router, start Kafka consumers
├── internal/
│   ├── dto/                      ← Request/Response validation models
│   ├── handler/                  ← Gin HTTP handlers. Push to Kafka for AI tasks.
│   ├── middleware/               ← JWT auth, ratelimit
│   ├── repository/               ← Raw SQL queries (database/sql)
│   └── service/                  ← Business logic layer
├── pkg/
│   ├── ai/client.go              ← HTTP Client for fast, sync AI queries ONLY (e.g. gets)
│   ├── cache/redis.go            ← Redis methods (stores ai_job:<id>)
│   ├── kafka/consumer.go         ← Subscribes to ai.job.status and ai.document.processed.status
│   └── kafka/producer.go         ← Pushes Commands to lms.ai.command
└── docs/                         ← Swagger generated files
```

---

## Standard Development Workflows

### 1. Triggering Async AI Tasks
Do NOT use blocking HTTP requests for generative AI. 

```go
// internal/handler/ai_handler.go
func (h *AIHandler) GenerateFlashcards(c *gin.Context) {
    // 1. Generate ID
    jobID := uuid.New().String()
    
    // 2. Publish to Kafka
    event := kafka.AICommandEvent{
        JobID:       jobID,
        CommandType: "GENERATE_FLASHCARDS",
        Payload: map[string]interface{}{"node_id": nodeID},
    }
    kafka.PublishAICommand(c.Request.Context(), event)
    
    // 3. Set Initial State in Redis
    redisPayload := map[string]string{"job_id": jobID, "status": "pending"}
    data, _ := json.Marshal(redisPayload)
    h.redisCache.Set(c.Request.Context(), "ai_job:"+jobID, data, 24*time.Hour)
    
    // 4. Return Accepted
    c.JSON(http.StatusAccepted, dto.NewDataResponse(redisPayload))
}
```

### 2. Traditional CRUD Workflow
For generic LMS logic:
1. Define structures inside `internal/dto/`.
2. Add Database Access in `internal/repository/`. ALWAYS use explicit parameters (`$1, $2`).
3. Add Business Logic mapped inside `internal/service/`.
4. Expose the route via `internal/handler/`.
5. Register in `cmd/api/main.go`.

**Always run `swag init -g cmd/api/main.go` after adding an endpoint.**