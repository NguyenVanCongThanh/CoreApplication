---
name: bdc-core-orchestrator
description: >
  ALWAYS load this before any other skill.
  Covers: full microservices architecture, env vars, secrets, CORS, Docker Compose, CI/CD,
  inter-service API contracts, port assignments, user sync flow.
triggers:
  - docker
  - docker-compose
  - .env
  - github actions
  - ci/cd
  - deploy
  - architecture
  - cross-service
version: "1.0"
authors:
  - BDC Team
---

# BDC CoreApplication — Master Orchestrator Skill

## Role & Scope
You are operating inside the **BDC CoreApplication** monorepo — a microservices LMS platform built by Big Data Club (HCMUT). This skill governs cross-cutting decisions, DevOps, and inter-service contracts. Always read this file first, then load the relevant service-specific skill.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                     Browser / Client                        │
└─────────────────────────┬──────────────────────────────────┘
                          │ :3000
                          ▼
┌────────────────────────────────────────────────────────────┐
│              frontend/ — Next.js 14 (TypeScript)            │
│  /apiv1/*     → http://backend:8080  (proxy rewrite)        │
│  /lmsapiv1/*  → http://lms-backend:8081 (proxy rewrite)     │
│  /files/*     → http://lms-backend:8081/api/v1/files/serve  │
└───────────┬────────────────────────────────┬───────────────┘
            │ :8080                          │ :8081
            ▼                                ▼
┌──────────────────────┐        ┌────────────────────────────┐
│  auth-and-management │        │       lms-service/          │
│  -service/           │◄───────│  Go 1.24 + Gin              │
│  Spring Boot 3.x     │ sync   │  Courses, Quiz, Forum       │
│  Java 21             │        │  File Upload, Progress      │
└──────────┬───────────┘        └────────────┬───────────────┘
           │                                  │         │
           ▼                                  ▼         ▼
    ┌──────────────┐              ┌──────────────┐ ┌──────────┐
    │ PostgreSQL   │              │ PostgreSQL   │ │  Redis   │
    │ (Auth DB)    │              │ (LMS DB +    │ │  :6379   │
    │ :5433        │              │  pgvector)   │ └──────────┘
    └──────────────┘              │ :5434        │
                                  └──────────────┘
                                         │
                          ┌──────────────┴──────────────┐
                          ▼                             ▼
               ┌─────────────────┐           ┌──────────────────┐
               │  ai-service/    │           │     MinIO        │
               │  FastAPI+Celery │           │  :9000/:9001     │
               │  :8000          │           └──────────────────┘
               └─────────────────┘
```

## Service Inventory

| Service | Dir | Language | Port | DB |
|---------|-----|----------|------|-----|
| Frontend | `frontend/` | Next.js 14 / TS | 3000 | — |
| Auth & Management | `auth-and-management-service/` | Java 21 / Spring Boot 3.x | 8080 | PostgreSQL :5433 |
| LMS | `lms-service/` | Go 1.24 / Gin | 8081 | PostgreSQL :5434 + Redis |
| AI | `ai-service/` | Python 3.12 / FastAPI + Celery | 8000 | Shares LMS PostgreSQL |

---

## Golden Rules (Apply to ALL services)

### 1. Environment Variables — Single Source of Truth
- ALL secrets and configuration live in **root `.env`** (never committed)
- Template: **root `.env.example`** — MUST be updated whenever a new env var is added anywhere
- `docker-compose.yml` propagates vars to containers — MUST be updated too
- **Check this checklist before adding any new env var:**
  - [ ] Added to `.env.example` with `<TODO>` placeholder and comment
  - [ ] Added to correct service block in `docker-compose.yml`
  - [ ] Added to service's config loader / `application.yaml` / config.go / pydantic Settings

### 2. Critical Shared Secrets (Must Be Identical)

```
JWT_SECRET          → Used by: auth-service (sign) + lms-service (verify) + ai-service (if needed)
                      Minimum 32 characters. LMS will refuse to start if shorter.

LMS_API_SECRET      → auth-service sends this header: X-Sync-Secret
LMS_SYNC_SECRET     → lms-service validates this. Must equal LMS_API_SECRET.

AI_SERVICE_SECRET   → lms-service sends to ai-service as X-AI-Secret header
```

**If these secrets don't match, the symptom is silent 401/403 — very hard to debug.**

### 3. Port Assignments (Never Change Without Updating All 3 Places)

| Service | Container Port | Host Port (dev) |
|---------|---------------|-----------------|
| frontend | 3000 | 3000 |
| backend (auth) | 8080 | 8080 |
| lms-backend | 8081 | 8081 |
| ai-service | 8000 | 8000 |
| postgres (auth) | 5432 | **5433** |
| postgres (lms) | 5432 | **5434** |
| redis | 6379 | 6379 |
| minio API | 9000 | 9000 |
| minio Console | 9001 | 9001 |

### 4. CORS — 3 Places Must Be Updated Together

When adding a new domain/port to CORS whitelist:
1. `auth-and-management-service/src/main/java/.../config/CorsConfig.java` — `allowedOrigins()`
2. `auth-and-management-service/src/main/java/.../config/SecurityConfig.java` — `corsConfigurationSource()`
3. Root `.env` → `CORS_ALLOWED_ORIGINS` (consumed by lms-service `config.go`)

### 5. User Sync Flow (Auth → LMS)

```
bulkRegister() in AuthService
    → @Async UserSyncService.syncUsersToLms()
    → POST http://lms-backend:8081/api/v1/sync/users/bulk
    → Header: X-Sync-Secret: {LMS_API_SECRET}
    → lms-service validates: LMS_SYNC_SECRET
```

**Role mapping on sync:**
```
ROLE_ADMIN  → ["TEACHER", "STUDENT", "ADMIN"]
ROLE_USER   → ["TEACHER", "STUDENT"]
ROLE_MANAGER→ ["TEACHER", "STUDENT"]
```
All BDC members can both teach AND learn.

### 6. File Storage Modes

```
STORAGE_TYPE=local   → files saved to lms-service container at /app/uploads
                        Must have volume: lms_upload_data:/app/uploads in docker-compose.yml
STORAGE_TYPE=minio   → streamed directly to MinIO bucket "lms-files"
                        ai-service Celery worker uses minio-go SDK to download files
```

---

## Docker Compose Workflow

### Starting the Stack
```bash
# First time — builds all images (~5 min)
docker compose up -d --build

# Subsequent starts (no code changes)
docker compose up -d

# Check health — all should be "healthy"
docker compose ps

# Stream logs
docker compose logs -f lms-backend ai-service

# Rebuild only one service after code change
docker compose up -d --build lms-backend
```

### Database Access (Dev)
```bash
# Auth DB
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB

# LMS DB (pgvector enabled)
docker compose exec postgres-lms psql -U $LMS_POSTGRES_USER -d $LMS_POSTGRES_DB
```

### Useful Debugging Commands
```bash
# Test JWT round-trip between services
TOKEN=$(curl -s -X POST localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@test.com","password":"pass"}' | jq -r .token)
curl localhost:8081/api/v1/me/roles -H "Authorization: Bearer $TOKEN"
# → 200 means JWT_SECRET matches between services

# Trigger manual user sync
curl -X POST localhost:8081/api/v1/sync/users/bulk \
  -H "X-Sync-Secret: $LMS_SYNC_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"users":[{"user_id":1,"email":"a@b.com","full_name":"Test","roles":["TEACHER","STUDENT"]}]}'

# Check ai-service health + embedding model loaded
curl localhost:8000/health
```

---

## CI/CD Pipeline (GitHub Actions)

### Files
- `.github/workflows/ci.yml` — Build + Test + Push Docker image
- `.github/workflows/cd-production.yml` — SSH deploy to production

### CI Flow
```
Push / PR
  ├── Detect changed services (only build what changed)
  ├── [Backend] ./mvnw test
  ├── [Frontend] npm run test:ci
  ├── [LMS] go test ./...
  ├── Security scan (Trivy)
  └── Push images to Docker Hub (on merge to main/develop)
```

### Required GitHub Secrets
```
DOCKER_USERNAME, DOCKER_PASSWORD
SSH_HOST, SSH_USER, SSH_PRIVATE_KEY
```

### CD Flow
```
Merge to main
  → Pull new images on production server
  → docker compose pull && docker compose up -d
  → Zero-downtime rolling update
```

---

## API Contracts Between Services

### Auth → LMS (User Sync)
```
POST /api/v1/sync/user
POST /api/v1/sync/users/bulk
DELETE /api/v1/sync/user/{userId}
Header: X-Sync-Secret: {LMS_SYNC_SECRET}

Payload: {
  "user_id": 123,
  "email": "user@example.com",
  "full_name": "Nguyen Van A",
  "roles": ["TEACHER", "STUDENT"]
}
```

### LMS → AI Service (Document Processing)
```
POST /ai/process-document
Header: X-AI-Secret: {AI_SERVICE_SECRET}
→ Returns job_id, Celery processes async

GET /ai/process-document/{job_id}
→ Poll for completion status
```

### LMS → AI Service (Error Diagnosis)
```
POST /ai/diagnose
Header: X-AI-Secret: {AI_SERVICE_SECRET}
→ Returns explanation + deep_link for student
```

### LMS → AI Service (Quiz Generation)
```
POST /ai/quiz/generate
POST /ai/quiz/{gen_id}/approve
POST /ai/quiz/{gen_id}/reject
→ DRAFT → teacher reviews → PUBLISHED to quiz_questions
```

---

## Database Migrations

### LMS (Go) — SQL files in `lms-service/migrations/`
```
002_content_management.sql   — users, courses, sections, content
003_enrollment_management.sql — enrollments, bulk_enrollment_logs
004_quiz_management.sql       — quizzes, questions, attempts, answers
005_quiz_question_images.sql  — image support for questions
006_fill_blank_support.sql    — fill-blank question types
007_forum.sql                 — forum posts, comments, votes
008_content_progress.sql      — content_progress tracking
009_auto_mark_quiz_completion.sql — backfill quiz completions
010_ai_knowledge_graph.sql    — pgvector, knowledge_nodes, document_chunks, AI tables
011_unique_for_chunk_hash.sql — unique constraint on chunk_hash
```

**Server migration files live separately in `server/bdc_deploy/LMS/init-scripts/`**

### Auth (Spring Boot) — JPA DDL Auto
- Dev: `JPA_DDL_AUTO=update` (auto-migrate)
- Production: `JPA_DDL_AUTO=validate` (NEVER use `update` in prod)

---

## Health Check Endpoints

| Service | Endpoint | Expected |
|---------|----------|----------|
| Auth | `GET /actuator/health` | `{"status":"UP"}` |
| Auth (liveness) | `GET /actuator/health/liveness` | `{"status":"UP"}` |
| LMS | `GET /health` | `{"status":"healthy"}` |
| AI | `GET /health` | `{"status":"healthy"}` |
| Frontend | `GET /api/health` | 200 OK |

---

## Security Checklist Before Every Deploy

```
[ ] JWT_SECRET >= 32 chars, identical in auth-service + lms-service
[ ] LMS_API_SECRET === LMS_SYNC_SECRET
[ ] AI_SERVICE_SECRET set and non-default
[ ] MINIO_ROOT_PASSWORD >= 8 chars (MinIO requirement)
[ ] Default admin account email/password changed
[ ] JPA_DDL_AUTO=validate (not update) in production
[ ] System.out.println removed from JwtAuthFilter.java
[ ] Stack trace hidden in GlobalExceptionHandler for production env
[ ] CORS origins do not include wildcard (*) in production
[ ] LOG_LEVEL=WARN in production
```

---

## Common Anti-Patterns to Avoid

| Anti-Pattern | Fix |
|---|---|
| Hardcoding secrets in Java source | Read from `@Value("${...}")` or env var |
| Returning full stack trace to client | Catch in GlobalExceptionHandler, log server-side |
| Blocking Celery tasks in FastAPI request | Use `.delay()`, return job_id immediately |
| Buffering large files in RAM | Stream directly: `io.Reader` → `PutObject` / `ServeContent` |
| N+1 queries | Use `LEFT JOIN FETCH` (JPA) or batch queries (Go) |
| Not updating `.env.example` | Always update template when adding env vars |
| Using `update` DDL in production | Use `validate` — migrations only via SQL files |

---

## Service-Specific Skills

Load these for detailed conventions within each service:

| When working on... | Load skill at |
|---|---|
| `auth-and-management-service/` | `.agent/skills/bdc-auth-service/SKILL.md` |
| `lms-service/` | `.agent/skills/bdc-lms-service/SKILL.md` |
| `ai-service/` | `.agent/skills/bdc-ai-service/SKILL.md` |
| `frontend/` | `.agent/skills/bdc-frontend/SKILL.md` |
| Docker / CI / deployment | This file (orchestrator) is sufficient |