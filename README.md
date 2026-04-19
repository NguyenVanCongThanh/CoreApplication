# BDC Application

| Field     | Value                     |
|-----------|---------------------------|
| Version   | 1.1.0                     |
| Status    | Approved                  |
| Date      | 2026-04-19                |
| Authors   | BDC Team                  |
| Reviewers | —                         |

## Revision History

| Version | Date       | Author   | Description                                   |
|---------|------------|----------|-----------------------------------------------|
| 1.0.0   | 2024-12-20 | BDC Team | Initial English draft                         |
| 1.1.0   | 2026-04-19 | BDC Team | Standardized version; removed emojis; ASCII diagrams |

---

## Developer Documentation

Read these documents in order before commencing development:

| Document | Description |
|---|---|
| **[DEVELOPER_GUIDE](./docs/DEVELOPER_GUIDE.md)** | Environment setup, local development, contribution workflow |
| **[TECHNICAL_NOTES](./docs/TECHNICAL_NOTES.md)** | Critical technical issues and operational constraints |
| **[.env.example](./.env.example)** | Annotated environment variable template |

---

## Overview

BDC Application is a microservices-based Learning Management System (LMS) designed for academic organizations and student clubs. The platform provides a complete set of core features for course management, enrollment, assessment, and user administration.

The current development focus is the integration of Artificial Intelligence to transform BDC from a traditional LMS into an adaptive learning ecosystem. In this system, every student follows a personalized learning path guided by actual learning behavior data.

### Current Features

*   **Course Management** — Create, edit, and organize courses with multimedia content.
*   **Course Enrollment** — Flexible enrollment system with an approval workflow.
*   **Quiz and Assessment** — Multiple question types, result tracking, and attempt history.
*   **User Management** — Role-based access control: Admin, Manager, Teacher, Student.
*   **Announcements** — System-wide and course-specific notifications.
*   **Event Management** — Track club events, assignments, and deadlines.
*   **File Management** — Upload and serve videos, documents, images via Local or MinIO storage.
*   **Secure Authentication** — JWT-based authentication with HTTP-only cookies.
*   **User Synchronization** — Automatic synchronization between Auth Service and LMS Service.

---

## System Architecture

```
+--------------------------------------------------------------+
|                      Browser / Client                        |
+--------------------------+-----------------------------------+
                           | Port 3000
                           v
+--------------------------------------------------------------+
|              Frontend — Next.js 14                           |
|   /apiv1/*  -----------> Auth Backend  (proxy)               |
|   /lmsapiv1/*  --------> LMS Backend   (proxy)               |
|   /files/*  -----------> LMS (file serving)                  |
+----------+------------------------------+--------------------+
           | :8080                         | :8081
           v                               v
+----------------------+     +---------------------------------+
|   Auth Backend       |     |   LMS Backend                   |
|   Spring Boot 3.x    |<----|   Go 1.21 + Gin                 |
|   - Auth & Users     |     |   - Courses & Quizzes           |
|   - Events           |     |   - User Sync Client            |
+----------+-----------+     +----------+----------------------+
           |                             |         |
           v                             v         v
+----------------------+  +---------------------+  +----------+
|  PostgreSQL (Auth)   |  |  PostgreSQL (LMS)   |  |  Redis   |
+----------------------+  +---------------------+  +----------+
                                                   +----------+
                                                   |  MinIO   |
                                                   +----------+
```

### Technology Stack

| Component | Technology | Version |
|---|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, NextAuth.js | 14+ |
| Auth Backend | Spring Boot, Spring Security, JWT | 3.x (Java 21) |
| LMS Backend | Go, Gin framework, GORM | 1.21+ |
| Database | PostgreSQL | 15 |
| Cache | Redis | 7 |
| Object Storage | MinIO | Latest |
| Container | Docker, Docker Compose | 24+ / 2.0+ |

---

## Quick Start

### Prerequisites

*   **Docker Desktop** 24.0+ and **Docker Compose** 2.0+
*   **Git**
*   Minimum **4GB RAM** allocated to Docker

### Up and running in 3 steps

1.  **Clone the repository**
    ```bash
    git clone https://github.com/Big-Data-Club/CoreApplication.git
    cd CoreApplication
    ```

2.  **Create configuration from template**
    ```bash
    cp .env.example .env
    ```
    Open `.env` and fill in the required values. Reference `docs/TECHNICAL_NOTES.md` for critical variables.

3.  **Build and launch the stack**
    ```bash
    docker compose up -d --build
    ```

### Accessing the Application

Service availability is reached after approximately 2 minutes of container initialization.

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Auth API + Swagger | http://localhost:8080/swagger-ui.html |
| LMS API + Swagger | http://localhost:3000/lmsapidocs/swagger/index.html |
| MinIO Console | http://localhost:9001 |

**Default Admin Account:**
*   Email: `phucnhan289@gmail.com`
*   Password: `hehehe`
*   Reference: `docs/TECHNICAL_NOTES.md` Section 6 for details.

---

## API Documentation

### Auth Service (`/apiv1`)

Base URL: `http://localhost:8080/api`

| Method | Endpoint | Description | Role |
|---|---|---|---|
| POST | `/auth/login` | Log in, receive JWT token | Public |
| POST | `/auth/logout` | Log out, clear session cookie | Authenticated |
| POST | `/auth/register/bulk` | Bulk create users with email notification | Admin |
| GET | `/users` | Paginated user list | Admin/Manager |
| GET | `/events` | Event list | Authenticated |
| GET | `/tasks` | Task list | Authenticated |
| GET | `/announcements` | System-wide announcements | Authenticated |

### LMS Service (`/lmsapiv1`)

Base URL: `http://localhost:8081/api/v1`

| Method | Endpoint | Description | Role |
|---|---|---|---|
| GET | `/courses` | List all available courses | Authenticated |
| POST | `/courses` | Create a new course | Teacher/Admin |
| POST | `/enrollments` | Enroll in a specific course | Student |
| GET | `/quizzes` | List available quizzes | Authenticated |
| POST | `/files/upload` | Upload multimedia file | Authenticated |
| GET | `/files/serve/:path` | Serve a stored file | Public |

---

## Roadmap — AI4Education

The next development phase focuses on bridging learning gaps through AI integration.

| Gap | Description |
|---|---|
| **Navigation Gap** | Students lack clarity on learning sequences |
| **Practice Gap** | Static content lacks interactive feedback loops |
| **Trust Gap** | Verification of AI-generated accuracy is required |

### Phase 1 — AI Error Diagnosis and Deep Linking
*   **Error Pattern Analysis** — Diagnose conceptual confusion or prerequisite gaps.
*   **Deep Link to Source** — Direct links to specific PDF pages or video timestamps.
*   **Weakness Heatmap** — Visualization of most-missed Knowledge Nodes.

### Phase 2 — AI Smart Quiz and Active Recall
*   **Auto Quiz Generator** — Generate questions following Bloom's Taxonomy.
*   **Source-cited Answers** — Justifications with clear citations.
*   **Spaced Repetition Engine** — Review reminders based on SM-2 algorithm.

### Phase 3 — AI Micro-Video Creator
*   **Auto Summarizer** — Summarize documents into concise Knowledge Node summaries.
*   **Script Generator** — Generate micro-video scripts for concise learning.
*   **AI Voice Generation** — Automated narration for slide-based videos.

---

## Contributing

Reference the full contribution guide and coding standards at `docs/DEVELOPER_GUIDE.md`.

```bash
git checkout -b feature/your-feature-name
# ... development ...
git commit -m "feat(lms): brief description"
git push origin feature/your-feature-name
```

---

## License

This project is licensed under the [MIT License](./LICENSE).

---

Built with formal standards by **BDC Team**