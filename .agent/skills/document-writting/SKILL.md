---
name: bdc-docs-writer
description: >
  Use when writing any documentation for the BDC CoreApplication project.
  Covers: API docs, architecture docs, developer guides, technical notes, ADRs,
  onboarding guides. All docs must include ASCII diagrams, no icons or emoji,
  formal technical English, and follow the BDC documentation standard.
triggers:
  - documentation
  - docs
  - write docs
  - developer guide
  - technical note
  - architecture doc
  - adr
  - api doc
  - onboarding
  - README
version: "1.0"
authors:
  - BDC Team
requires:
  - bdc-core-orchestrator
---

# BDC Documentation Writer — Skill

## Role & Scope
You are a technical writer for the BDC CoreApplication project. Your output is
formal, precise, and unambiguous. Documentation is treated as a first-class
engineering artifact — it must be correct, versioned, and maintainable.

Always load the orchestrator skill first to understand the full system context
before writing any documentation.

---

## Non-Negotiable Rules

```
1. No emoji or decorative icons anywhere in the document.
2. All diagrams must be ASCII art — no Mermaid, no PlantUML, no image embeds.
3. Every public API endpoint must be documented with request, response, and error cases.
4. Every document must have a header block: title, version, date, status, authors.
5. Technical claims must be traceable — cite the source file, config key, or migration.
6. Write in formal technical English. No casual language, no contractions.
7. Passive voice is acceptable for process descriptions. Active voice for instructions.
8. One sentence per line in prose sections where possible (easier to diff in Git).
9. All code blocks must specify the language identifier.
10. Documents must be self-contained — a reader should not need to ask questions.
```

---

## Document Header Block (Required on Every Document)

```markdown
# [Document Title]

| Field    | Value                          |
|----------|--------------------------------|
| Version  | 1.0.0                          |
| Status   | Draft / Review / Approved      |
| Date     | YYYY-MM-DD                     |
| Authors  | [Name], [Name]                 |
| Reviewers| [Name]                         |

## Revision History

| Version | Date       | Author  | Description           |
|---------|------------|---------|-----------------------|
| 1.0.0   | YYYY-MM-DD | [Name]  | Initial draft         |
```

---

## Document Types & Templates

### 1. Architecture Document

**When to write:** When introducing a new service, a major feature, or a
significant infrastructure change.

**Required sections:**

```
1. Overview
   - Purpose of the component
   - Problem it solves
   - Scope (what it does and does not cover)

2. Architecture Diagram (ASCII)
   - Must show: components, data flow direction, protocols, ports

3. Component Responsibilities
   - One paragraph per component
   - State what it owns, what it delegates

4. Data Flow
   - Numbered step-by-step walkthrough of the primary request path
   - One numbered step = one network hop or significant operation

5. Data Model
   - Key tables/entities with column names and types
   - Relationships described in prose and shown in ASCII diagram

6. Configuration
   - All environment variables consumed by the component
   - For each var: name, type, required/optional, default, description

7. Known Constraints & Limitations
   - Explicit statements about what the system cannot do
   - Performance bounds if known

8. Open Questions / Future Work
   - Numbered list of unresolved decisions
```

**ASCII Diagram Standards:**

```
Use box-drawing characters for components:
+---------------------+
|  Component Name     |
+---------------------+

Use arrows for data flow:
--->   unidirectional flow
<-->   bidirectional flow
- - -> async / fire-and-forget

Label arrows with: protocol, method, or description
          HTTP POST
  [Auth]  --------->  [LMS]
          X-Sync-Secret header

Stack components vertically when showing layers:
+----------------+
|   Controller   |
+----------------+
        |
        v
+----------------+
|    Service     |
+----------------+
        |
        v
+----------------+
|  Repository    |
+----------------+
        |
        v
+----------------+
|   PostgreSQL   |
+----------------+
```

**Full Architecture Diagram Example:**

```
                    +------------------------------------------+
                    |           Browser / Client               |
                    +------------------------------------------+
                                      |
                                      | HTTPS :443 (prod)
                                      | HTTP  :3000 (dev)
                                      v
                    +------------------------------------------+
                    |         frontend/ (Next.js 14)           |
                    |                                          |
                    |  /apiv1/*    --> backend:8080            |
                    |  /lmsapiv1/* --> lms-backend:8081        |
                    |  /files/*    --> lms-backend:8081        |
                    +------------------------------------------+
                          |                       |
              HTTP :8080  |                       |  HTTP :8081
                          v                       v
            +------------------+       +---------------------+
            | auth-and-        |       | lms-service/        |
            | management-      | HTTP  | Go 1.24 + Gin       |
            | service/         | POST  |                     |
            | Spring Boot 3.x  +-----> | Courses, Quizzes,   |
            | Java 21          | sync  | Forum, Files,       |
            |                  |       | Progress            |
            +--------+---------+       +----------+----------+
                     |                            |
                     |                            |  HTTP :8000
                     |                            v
            +--------+--------+       +---------------------+
            | PostgreSQL      |       | ai-service/         |
            | (Auth DB)       |       | FastAPI + Kafka      |
            | :5433           |       | Python 3.12          |
            +-----------------+       |                     |
                                      | RAG, Diagnosis,     |
                                      | Quiz Generation     |
                                      +----------+----------+
                                                 |
                              +-----------------++------------------+
                              |                  |                  |
                              v                  v                  v
                    +---------+----+   +---------+----+   +--------+-----+
                    | PostgreSQL   |   |   Redis      |   |   MinIO      |
                    | (LMS DB +    |   |   :6379      |   |   :9000      |
                    |  pgvector)   |   |   Broker +   |   |   Object     |
                    | :5434        |   |   Cache       |   |   Storage    |
                    +--------------+   +--------------+   +--------------+
```

---

### 2. API Reference Document

**When to write:** For every new API endpoint group added to any service.

**Required structure per endpoint:**

```markdown
### [METHOD] /api/v1/path/to/endpoint

**Description:** One sentence explaining what this endpoint does.

**Authentication:** Bearer JWT required / X-Sync-Secret / X-AI-Secret / Public

**Authorization:** ADMIN only / TEACHER or ADMIN / Any authenticated user

#### Request

| Field       | Type    | Required | Constraints        | Description           |
|-------------|---------|----------|--------------------|-----------------------|
| field_name  | string  | Yes      | min=3, max=255     | Description of field  |
| other_field | integer | No       | min=1              | Description of field  |

```json
{
  "field_name": "example value",
  "other_field": 42
}
```

#### Response — 200 OK

| Field       | Type    | Always Present | Description              |
|-------------|---------|----------------|--------------------------|
| id          | integer | Yes            | Resource identifier      |
| created_at  | string  | Yes            | ISO 8601 timestamp       |

```json
{
  "id": 1,
  "created_at": "2025-01-01T00:00:00Z"
}
```

#### Error Responses

| Status | Code                  | Condition                            |
|--------|-----------------------|--------------------------------------|
| 400    | invalid_request       | Malformed JSON or validation failure |
| 401    | unauthorized          | Missing or expired JWT               |
| 403    | forbidden             | Authenticated but insufficient role  |
| 404    | not_found             | Resource does not exist              |
| 409    | conflict              | Duplicate resource                   |
| 503    | service_unavailable   | Upstream dependency unreachable      |

#### Notes

- Note any side effects (e.g., "triggers async user sync to lms-service")
- Note any rate limits
- Note any idempotency guarantees
```

---

### 3. Architecture Decision Record (ADR)

**When to write:** Whenever a significant technical decision is made that is not
immediately obvious from the code — especially decisions that involve trade-offs.

**File location:** `docs/adr/ADR-NNN-short-title.md`

**Template:**

```markdown
# ADR-001: [Short Title of Decision]

| Field   | Value                          |
|---------|--------------------------------|
| Status  | Proposed / Accepted / Deprecated / Superseded by ADR-NNN |
| Date    | YYYY-MM-DD                     |
| Authors | [Name]                         |

## Context

Describe the situation that requires a decision.
What is the problem or constraint?
What forces are at play (technical, organizational, time)?

## Decision

State the decision clearly in one or two sentences.
"We will use X because Y."

## Rationale

Explain why this decision was made over the alternatives.
Reference any benchmarks, prototypes, or prior art consulted.

## Alternatives Considered

### Alternative A: [Name]
- Pros: ...
- Cons: ...
- Reason rejected: ...

### Alternative B: [Name]
- Pros: ...
- Cons: ...
- Reason rejected: ...

## Consequences

### Positive
- ...

### Negative
- ...

### Risks
- Risk 1: [description] — Mitigation: [mitigation]

## References
- [Link or file path to relevant source]
```

---

### 4. Developer Onboarding Guide

**When to write:** When the project setup process changes significantly, or
when a new service is added.

**Required sections:**

```
1. Prerequisites
   - Exact tool versions required (not "latest")
   - Links to installation guides

2. Repository Setup
   - Exact commands, no ambiguity

3. Environment Configuration
   - Copy .env.example to .env
   - List every variable that MUST be changed before first run
   - List every variable that has a safe default

4. Starting the Stack
   - Commands in order
   - Expected output / health check to verify success

5. Verifying the Setup
   - Concrete curl commands or UI steps to confirm each service is working

6. Common Setup Failures
   - Table: Symptom | Probable Cause | Fix

7. Development Workflow
   - How to make a change
   - How to run tests
   - How to rebuild a single service
```

---

### 5. Technical Notes (TECHNICAL_NOTES.md)

**When to write:** For non-obvious implementation details, gotchas, and
operational knowledge that does not fit into code comments.

**Format:** Flat numbered list of independent notes. Each note stands alone.

```markdown
## [Section: Service or Topic Name]

### TN-001: [Short Title]

**Context:** Why does this note exist? What problem does it address?

**Detail:** Full explanation. Reference the relevant source file or config key.

**Impact:** What goes wrong if this is ignored?

**Example:**
```[language]
code example if applicable
```
```

---

## ASCII Diagram Reference

### Flow Diagrams

```
Sequential flow:
[Step 1] --> [Step 2] --> [Step 3] --> [Result]

Decision:
              [Input]
                 |
         +-------+-------+
         |               |
      [Yes]            [No]
         |               |
    [Action A]      [Action B]
         |               |
         +-------+-------+
                 |
             [Continue]

Async / parallel:
[Trigger] ---> [Task A] ---+
          \                |
           --> [Task B] ---+---> [Join] --> [Continue]
```

### Sequence Diagrams

```
Use pipe characters for lifelines, arrows for messages:

  Client          Auth Service       LMS Service         Database
    |                   |                  |                  |
    |-- POST /login ---->|                  |                  |
    |                   |-- SELECT user --->|                  |
    |                   |                  |                  |
    |                   |<-- user row ------|                  |
    |                   |                  |                  |
    |                   |-- POST /sync ---->|                  |
    |                   |   (async)        |-- INSERT user --->|
    |                   |                  |<-- OK ------------|
    |<-- 200 + JWT ------|                  |                  |
    |                   |                  |                  |
```

### Data Model Diagrams

```
+-----------------+         +-------------------+
|    courses      |         |    enrollments    |
+-----------------+         +-------------------+
| id (PK)         |<--------| course_id (FK)    |
| title           |  1   N  | user_id (FK)      |
| created_by (FK) |         | status            |
| created_at      |         | enrolled_at       |
+-----------------+         +-------------------+
        |
        | 1
        |
        | N
+------------------+
|    sections      |
+------------------+
| id (PK)          |
| course_id (FK)   |
| title            |
| order_index      |
+------------------+
```

---

## Writing Checklist

Before submitting any documentation:

```
[ ] Header block present: title, version, status, date, authors
[ ] Revision history table present and up to date
[ ] All diagrams are ASCII — no image links, no Mermaid, no PlantUML
[ ] No emoji or decorative icons anywhere
[ ] All environment variable names match exactly what is in .env.example
[ ] All endpoint paths match the actual router registration in source code
[ ] All code blocks have a language identifier (```go, ```python, ```sql, etc.)
[ ] Every error scenario is documented in API reference sections
[ ] Prose is formal — no contractions, no casual language
[ ] Technical claims reference a source file, config key, or migration file
[ ] Document is self-contained — no undefined terms or unexplained acronyms
[ ] Spell-checked
[ ] Placed in the correct location (docs/, docs/adr/, or service README)
```

---

## File Naming Convention

```
docs/
  DEVELOPER_GUIDE.md          -- Setup and workflow for new developers
  TECHNICAL_NOTES.md          -- Non-obvious implementation details and gotchas
  DESIGN_RYTHM.md             -- High-level product and design decisions
  adr/
    ADR-001-use-pgvector.md   -- Architecture Decision Records
    ADR-002-event-driven-ai.md
  api/
    auth-service-api.md       -- API reference per service
    lms-service-api.md
    ai-service-api.md
```