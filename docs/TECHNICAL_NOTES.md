# Technical Notes

| Field    | Value                          |
|----------|--------------------------------|
| Version  | 1.1.0                          |
| Status   | Living document                |
| Date     | 2025-01-01                     |
| Authors  | BDC Team                       |

This document captures non-obvious implementation details, known gotchas,
and operational knowledge that does not belong in code comments.

Read this before making changes to authentication, AI pipeline, or Docker setup.

---

## Section 1: Authentication & JWT

### TN-001: JWT_SECRET must be identical in two services

**Context:** Both `auth-and-management-service` (Spring Boot) and `lms-service`
(Go) verify JWT tokens independently. They do not call each other to validate.

**Detail:** `JWT_SECRET` in `.env` is read by both services. If they differ,
the Go LMS service will reject every token issued by the Java auth service with
a 401 error. This is silent — no log message explains the mismatch.

**Impact:** All authenticated LMS requests fail with `401 Unauthorized`.

**Fix:** Ensure `.env` has a single `JWT_SECRET` value and both services
read it. Minimum length: 32 characters.

---

### TN-002: Default admin credentials are hardcoded

**Context:** `DataInitializer.java` seeds the admin account on first startup.

**Detail:** Prior to Phase 1 fix, the email (`phucnhan289@gmail.com`) and
password (`hehehe`) were hardcoded. After the fix, they read from
`${ADMIN_EMAIL}` and `${ADMIN_PASSWORD}` environment variables.

**Impact:** If these env vars are not set, Spring Boot startup fails with a
`@Value` injection error.

**Fix:** Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env` before first run.
Change the password immediately after first login.

---

## Section 2: User Sync

### TN-003: User sync is async — silent failure on LMS downtime

**Context:** When `auth-service` creates a user via `bulkRegister()`, it calls
`UserSyncService.syncUsersToLms()` to replicate the user to the LMS database.
This call is `@Async` — it fires and does not block the HTTP response.

**Detail:** If `lms-service` is down or unreachable when users are created,
the sync silently fails. Users exist in the auth database but cannot enroll
in courses because their record does not exist in the LMS database.

**Impact:** Newly created users receive "user not found" errors when accessing LMS features.

**Fix:** Manual re-sync:
```bash
curl -X POST http://localhost:8081/api/v1/sync/users/bulk \
  -H "X-Sync-Secret: $LMS_SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"users":[{"user_id":1,"email":"a@b.com","full_name":"Name","roles":["TEACHER","STUDENT"]}]}'
```
Verify after bulk registration:
```bash
docker compose logs backend | grep -i "sync\|error"
```

---

### TN-004: LMS_API_SECRET and LMS_SYNC_SECRET must be equal

**Context:** `auth-service` sends sync requests to `lms-service` using the
`LMS_API_SECRET` value as the `X-Sync-Secret` header.
`lms-service` validates incoming sync requests against `LMS_SYNC_SECRET`.

**Detail:** These are two different environment variable names for the same
secret. If they differ, every sync request returns `401` and users cannot
access LMS features (see TN-003 impact).

---

## Section 3: File Storage

### TN-005: STORAGE_TYPE controls where uploads go

**Detail:** `lms-service` reads `STORAGE_TYPE` from environment.
`local` stores files in the container filesystem at `/app/uploads`.
`minio` stores files in the MinIO bucket `lms-files`.

The AI service always fetches files directly from MinIO using the MinIO SDK
(not via HTTP). It uses `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`.

**Impact:** If `STORAGE_TYPE=local` in production, the AI service cannot access
files because it reads from MinIO, not from the local filesystem.

**Fix:** Use `STORAGE_TYPE=minio` in any environment where ai-service processes documents.

---

## Section 4: AI Service

### TN-006: USE_QDRANT=false to rollback to pgvector

**Context:** Qdrant is the default vector backend. See ADR-002.

**Detail:** Set `USE_QDRANT=false` in the ai-service and ai-worker environment
to revert all vector operations to pgvector. The `embedding` column in
`document_chunks` is nullable but preserved for this purpose.

**Impact:** Semantic search will use pgvector. Performance degrades on large
corpora (>100k chunks). The pgvector fallback is fully functional.

---

### TN-007: NEO4J_ENABLED=false to run without knowledge graph

**Context:** Neo4j provides the cross-course knowledge graph. See ADR-003.

**Detail:** Set `NEO4J_ENABLED=false` to disable all Neo4j operations.
Graph endpoints (`GET /knowledge-graph/*`) will fall back to PostgreSQL queries.

**Impact:** Cross-course prerequisite discovery is unavailable.
Intra-course graphs still work via PG fallback.

---

### TN-008: Kafka consumer group names must not overlap

**Context:** `ai-service` (FastAPI HTTP server) and `ai-worker` (Kafka consumer)
are separate processes sharing the same Docker image.

**Detail:** The ai-worker uses `group_id="ai-worker-group"`. If any other process
joins this group, Kafka will rebalance partitions between them, and document
indexing events may be consumed by the HTTP server instead of the worker.

**Impact:** Document processing events are silently dropped (the HTTP server
does not process them).

**Fix:** Never set `group_id="ai-worker-group"` in anything other than the
Kafka worker process.

---

### TN-009: Embedding cache TTL is 7 days

**Context:** Phase 2 adds a Redis cache for computed embeddings.

**Detail:** The cache key is `emb:{model_prefix}:{sha256(text)[:16]}`.
TTL is 7 days. If the embedding model changes (e.g. upgrade from bge-m3 to
a new model), cached vectors from the old model will continue to be served
for up to 7 days.

**Fix:** After an embedding model upgrade, flush the embedding cache:
```bash
docker exec redis-lms redis-cli -a "$REDIS_PASSWORD" KEYS "emb:*" | \
  xargs docker exec redis-lms redis-cli -a "$REDIS_PASSWORD" DEL
```

---

### TN-010: YOUTUBE_WHISPER_FALLBACK=true costs 500 MB RAM per worker

**Context:** If a YouTube video has no captions, the worker falls back to
downloading the audio and running Whisper locally.

**Detail:** `faster-whisper` with `base` model loads approximately 500 MB of
model weights into RAM. With `ai-worker` memory limit at 2 GB, enabling this
feature reduces headroom for embeddings and LLM calls.

**Default:** `YOUTUBE_WHISPER_FALLBACK=false` (disabled). Enable only if
YouTube caption availability is insufficient for the course library.

---

### TN-011: Diagnosis cache invalidation after content re-index

**Context:** Phase 2 caches LLM diagnosis results in Redis (TTL 24h).

**Detail:** If a course document is re-indexed (new content, corrected errors),
cached diagnoses for questions from that content remain valid in Redis until TTL
expires. Students may receive stale explanations for up to 24 hours.

**Fix:** After a forced re-index, invalidate the diagnosis cache for affected
questions:
```python
from app.core.cache import diagnosis_cache
await diagnosis_cache.invalidate_question(question_id)
```
There is currently no automated invalidation on re-index. This is a known
limitation to be addressed in a future iteration.

---

## Section 5: Known Test Failures

### TN-012: AuthServiceTest.testBulkRegister_AssignsDefaultPassword is incorrect

**Context:** The test asserts a wrong password value.
**Status:** Not fixed — marked as a known issue.
**Fix:** Update the assertion to match the actual generated password logic
in `PasswordGenerator.java`.

---

### TN-013: EventControllerTest.testUpdateEvent_Success asserts wrong enum

**Context:** The test asserts `.status = "ONGOING"` but the enum value is `"IN_PROGRESS"`.
**Fix:**
```java
.andExpect(jsonPath("$.status").value("IN_PROGRESS"))
```

---

## Section 6: Operations

### TN-014: How to run migration scripts manually

```bash
# Apply AI DB schema (idempotent)
docker exec -i postgres-ai psql -U ai_user -d ai_db \
  < ai-service/migrations/001_ai_core.sql

# Apply performance indexes (Phase 2)
docker exec -i postgres-ai psql -U ai_user -d ai_db \
  < ai-service/migrations/003_performance_indexes.sql

# Migrate vectors from pgvector to Qdrant (one-time, after enabling USE_QDRANT)
docker exec ai-worker python scripts/migrate_to_qdrant.py

# Migrate knowledge graph from PG to Neo4j (one-time)
docker exec ai-worker python scripts/migrate_neo4j.py

# Re-sync all users from auth-service to lms-service
curl -X POST http://localhost:8081/api/v1/sync/users/bulk \
  -H "X-Sync-Secret: $LMS_SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d @<(docker exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
    -tAc "SELECT json_agg(json_build_object('user_id',id,'email',email,'full_name',full_name,'roles',ARRAY['TEACHER','STUDENT'])) FROM users")
```

---

### TN-015: Checking Kafka consumer lag

```bash
docker exec bdc-kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group ai-worker-group
```

LAG column should be 0 or near-zero in steady state.
LAG > 100: worker is falling behind — check worker logs.
LAG > 500: critical — scale the worker or check for errors.

Or use the HTTP endpoint (Phase 3):
```bash
curl http://localhost:8000/health/kafka
```
