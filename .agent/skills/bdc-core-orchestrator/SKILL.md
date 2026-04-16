---
name: bdc-core-orchestrator
description: >
  ALWAYS load this before any other skill.
  Covers: full microservices architecture, env vars, secrets, CORS, Docker Compose, CI/CD, Kafka event bus, inter-service API contracts.
triggers:
  - architecture
  - docker
  - compose
  - env
  - global
  - cors
  - secrets
  - kafka
version: "2.0"
authors:
  - BDC Team
---

# BDC Core Orchestrator — Global Vision

**CRITICAL INSTRUCTION: Read this file carefully before working on any specific microservice.**
You are modifying the **Big Data Club (BDC) Core Application**. It is a modern, modular Microservices architecture deployed via Docker Compose. 

## The Golden Rules
1. **Never mock the Auth Service in the LMS Service**: The LMS service relies heavily on the `UserSyncService` to replicate user data to avoid cross-service joins. 
2. **Never use Synchronous HTTP for AI tasks**: The system utilizes an Event-Driven Architecture over Kafka (`bdc-kafka`). All long-running AI requests must return an immediate HTTP `202 Accepted` alongside a `job_id`.
3. **Never hardcode credentials or endpoints**: Always use `.env` files and Docker environment references (e.g., `http://auth-service:8080`).

---

## Global System Architecture

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│                 │       │                 │       │                 │
│    Next.js      │──────▶│    Traefik      │──────▶│  Kafka Broker   │
│    Frontend     │       │  API Gateway    │       │  (Event Bus)    │
│    (:3000)      │       │     (:80)       │       │    (:9092)      │
│                 │       │                 │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│                 │       │                 │       │  AI Service     │
│ Auth & Mgmt     │       │ LMS Service     │──────▶│  FastAPI +      │
│ Java Spring Boot│──────▶│ Go 1.24 + Gin   │       │  AI Worker      │
│    (:8080)      │  JWT  │    (:8081)      │ Kafka │    (:8000)      │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Auth PostgreSQL │       │ LMS PostgreSQL  │       │ AI PostgreSQL   │
│                 │       │ + Redis Cache   │       │ + Qdrant DB     │
│                 │       │ + MinIO Storage │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

### Microservice Topology

| Service | Path | Stack | Port | Notes |
|---------|------|-------|------|-------|
| Frontend | `frontend/` | Next.js, React, Tailwind | 3000 | Consumer-facing app |
| Auth | `auth-service/` | Java 21, Spring Boot | 8080 | Global SSO, User Management, Email |
| LMS | `lms-service/` | Go 1.24, Gin | 8081 | Orchestrates courses, pushes to Kafka |
| AI | `ai-service/` | Python 3.12, FastAPI | 8000 | LLM integration, RAG, consumes Kafka |
| Kafka | N/A | KRaft Mode Broker | 9092 | Asynchronous communication bus |

---

## Core Operational Patterns

### 1. Data Synchronization (User Sync)
Given that `auth-service` and `lms-service` have distinct PostgreSQL instances, the `auth-service` sends HTTP Post payloads via `UserSyncService` to `/api/v1/sync/users` in `lms-service` whenever an account is created, updated, or blocked. 

### 2. Event-Driven GenerAI
To prevent connection timeouts, all generative AI logic (RAG Document Ingestion, Quizzes, Error Diagnosis) is offloaded to Kafka.
- **Topic `lms.ai.command`:** LMS produces a JSON event outlining the command type (`GENERATE_QUIZ`) and payload. 
- **Topic `ai.job.status`:** AI-Worker produces progressive updates (`pending` -> `processing` -> `completed`/`failed`) which are consumed by the LMS to update its associated Redis Job Cache for the frontend.

### 3. File Uplink Protocol
- The Frontend streams files directly to the LMS Service (`/files/upload`). 
- The LMS service uses an abstracted `Storage` interface currently bound to **MinIO** internally.
- The AI Service utilizes the same MinIO credentials to download context payloads directly from the bucket over the native docker-compose network `http://minio:9000`.

## Docker Compose Overview
The entire stack is configured inside the root `docker-compose.yml`. Wait for all dependencies (`depends_on: condition: service_healthy`) to boot correctly.

- To rebuild the LMS Go backend locally: `docker-compose up -d --build lms-backend`
- To rebuild the AI Worker locally: `docker-compose up -d --build ai-worker`