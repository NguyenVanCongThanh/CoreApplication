---
name: bdc-lms-service
description: >
  Use when working in lms-service/ — Go 1.24 + Gin + PostgreSQL + Redis.
  Covers: courses, quizzes, enrollments, forum, file upload, AI integration layer.
triggers:
  - lms-service/
  - golang
  - go
  - gin
  - lms
version: "1.0"
authors:
  - BDC Team
requires:
  - bdc-core-orchestrator
---

# BDC LMS Service — Developer Skill

## Role & Scope
You are working on **`lms-service/`** — the Learning Management System backend. Built with Go 1.24 + Gin + PostgreSQL (pgvector) + Redis. Handles courses, sections, content, quizzes, enrollments, forum, progress tracking, and the AI integration layer. Always load the orchestrator skill first, then use this file.

**Module:** `example/hello` (see `go.mod`)
**Entry point:** `cmd/api/main.go`
**Base URL:** `http://localhost:8081` | Docker internal: `http://lms-backend:8081`

---

## Project Structure

```
lms-service/
├── cmd/api/main.go               ← Entry point: config, DI wiring, Gin router, graceful shutdown
├── internal/
│   ├── config/config.go          ← Loads all env vars via godotenv, validates, exposes typed structs
│   ├── dto/                      ← Request/Response structs (no DB logic)
│   │   ├── analytics_dto.go
│   │   ├── common_dto.go         ← SuccessResponse, ErrorResponse, PaginationRequest, helper funcs
│   │   ├── course_dto.go
│   │   ├── enrollment_dto.go
│   │   ├── forum_dto.go
│   │   ├── progress_dto.go
│   │   ├── quiz_dto.go
│   │   ├── quiz_history_dto.go
│   │   ├── sync_dto.go
│   │   └── user_dto.go
│   ├── handler/                  ← HTTP handlers (Gin context) — thin layer, call service
│   │   ├── ai_handler.go
│   │   ├── analytics_handler.go
│   │   ├── course_handler.go
│   │   ├── enrollment_handler.go
│   │   ├── file_handler.go
│   │   ├── forum_handler.go
│   │   ├── progress_handler.go
│   │   ├── quiz_handler.go
│   │   ├── quiz_history_handler.go
│   │   ├── sync_handler.go
│   │   └── user_handler.go
│   ├── middleware/               ← Gin middleware
│   │   ├── auth.go               ← JWT validation, sets user_id/user_email/user_roles in context
│   │   ├── cors.go               ← CORS — special handling for /files/serve/* (wildcard)
│   │   ├── logger.go             ← Request logging
│   │   └── ratelimit.go          ← Redis-backed rate limiting
│   ├── models/                   ← DB structs (database/sql types, NOT GORM)
│   │   ├── course.go
│   │   ├── enrollment.go
│   │   ├── forum.go
│   │   ├── quiz.go
│   │   └── user.go
│   ├── repository/               ← Raw SQL queries via database/sql
│   │   ├── analytics_repo.go
│   │   ├── course_repo.go
│   │   ├── enrollment_repo.go
│   │   ├── forum_repo.go
│   │   ├── progress_repo.go
│   │   ├── quiz_history_repo.go  ← Methods on QuizRepository (quiz_repo.go)
│   │   ├── quiz_repo.go
│   │   └── user_repo.go
│   └── service/                  ← Business logic — calls repositories, returns DTOs
│       ├── analytics_service.go
│       ├── course_service.go
│       ├── enrollment_service.go
│       ├── forum_service.go
│       ├── progress_service.go
│       ├── quiz_history_service.go ← Methods on QuizService
│       ├── quiz_service.go
│       ├── sync_service.go
│       └── user_service.go
├── migrations/                   ← SQL migration files (run in order, do NOT modify existing)
├── pkg/
│   ├── ai/client.go              ← HTTP client for ai-service (all AI API calls go here)
│   ├── cache/redis.go            ← Redis client wrapper + key generators
│   ├── database/postgres.go      ← *sql.DB connection pool setup
│   ├── logger/logger.go          ← Simple structured logger
│   └── storage/                  ← Storage abstraction
│       ├── storage.go            ← Storage interface + ObjectResult type
│       ├── local.go              ← Local filesystem implementation
│       └── minio.go              ← MinIO implementation (streaming, no RAM buffering)
└── docs/                         ← Swagger generated files (DO NOT hand-edit)
```

---

## Architecture — Layered Design

```
HTTP Request (Gin)
    ↓
Middleware (auth.go → sets user_id, user_email, user_roles in Gin context)
    ↓
Handler (handler/*.go) → Parse params, bind JSON, call Service, return JSON
    ↓
Service (service/*.go) → Business logic, authorization checks, calls Repository
    ↓
Repository (repository/*.go) → Raw SQL via *sql.DB, returns models or DTOs
    ↓
PostgreSQL / Redis
```

**Strict rules:**
- Handlers **never** write SQL — always call Service
- Services **never** directly write HTTP responses
- Repositories return `models.*` or primitive types — never `dto.*`
- Services convert `models.*` → `dto.*` before returning

---

## Go Idioms — Required Style

### Error Handling — Always Explicit
```go
// ✅ Correct — always check and handle errors
rows, err := r.db.QueryContext(ctx, query, args...)
if err != nil {
    return nil, fmt.Errorf("MyRepo.ListAll: %w", err)
}
defer rows.Close()

// ❌ Wrong — never discard errors
rows, _ := r.db.QueryContext(ctx, query)
```

### Error Wrapping — Always Add Context
```go
// ✅ Wrap with context so stack is readable
if err != nil {
    return nil, fmt.Errorf("CourseService.CreateCourse: failed to save: %w", err)
}

// ✅ Sentinel error check
if err == sql.ErrNoRows {
    return nil, fmt.Errorf("course not found")
}
if errors.Is(err, sql.ErrNoRows) { ... }  // preferred for wrapped errors
```

### Naming Conventions
```go
// Packages: lowercase, short, no underscore
package repository  // ✅
package user_repo   // ❌

// Exported functions: PascalCase
func (r *CourseRepository) GetByID(...)  // ✅

// Unexported: camelCase
func buildWhereClause(...)  // ✅

// Error variables: ErrSomething
var ErrCourseNotFound = errors.New("course not found")

// Interface implementations — explicit check at compile time
var _ Storage = (*LocalStorage)(nil)
var _ Storage = (*MinIOStorage)(nil)
```

### Context — Always First Parameter
```go
func (r *CourseRepository) GetByID(ctx context.Context, id int64) (*models.Course, error) {
    // Always pass ctx to database calls
    row := r.db.QueryRowContext(ctx, query, id)
}
```

---

## Adding a New Feature — Standard Workflow

### Step 1: Database Migration
```sql
-- migrations/012_my_feature.sql
CREATE TABLE IF NOT EXISTS my_things (
    id          BIGSERIAL PRIMARY KEY,
    course_id   BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_my_things_course ON my_things(course_id);

CREATE TRIGGER update_my_things_updated_at
    BEFORE UPDATE ON my_things
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Step 2: Model
```go
// internal/models/my_thing.go
package models

import (
    "database/sql"
    "time"
)

type MyThing struct {
    ID        int64          `json:"id"         db:"id"`
    CourseID  int64          `json:"course_id"  db:"course_id"`
    Title     string         `json:"title"      db:"title"`
    IsActive  bool           `json:"is_active"  db:"is_active"`
    CreatedAt time.Time      `json:"created_at" db:"created_at"`
    UpdatedAt time.Time      `json:"updated_at" db:"updated_at"`
}
```

### Step 3: DTO
```go
// internal/dto/my_thing_dto.go
package dto

import "time"

type CreateMyThingRequest struct {
    Title    string `json:"title"     binding:"required,min=3,max=255"`
    IsActive *bool  `json:"is_active"`
}

type MyThingResponse struct {
    ID        int64     `json:"id"`
    CourseID  int64     `json:"course_id"`
    Title     string    `json:"title"`
    IsActive  bool      `json:"is_active"`
    CreatedAt time.Time `json:"created_at"`
}
```

### Step 4: Repository
```go
// internal/repository/my_thing_repo.go
package repository

import (
    "context"
    "database/sql"
    "fmt"
    "example/hello/internal/models"
)

type MyThingRepository struct {
    db *sql.DB
}

func NewMyThingRepository(db *sql.DB) *MyThingRepository {
    return &MyThingRepository{db: db}
}

func (r *MyThingRepository) Create(ctx context.Context, thing *models.MyThing) error {
    query := `
        INSERT INTO my_things (course_id, title, is_active)
        VALUES ($1, $2, $3)
        RETURNING id, created_at, updated_at
    `
    return r.db.QueryRowContext(ctx, query, thing.CourseID, thing.Title, thing.IsActive).
        Scan(&thing.ID, &thing.CreatedAt, &thing.UpdatedAt)
}

func (r *MyThingRepository) GetByCourse(ctx context.Context, courseID int64) ([]models.MyThing, error) {
    rows, err := r.db.QueryContext(ctx,
        `SELECT id, course_id, title, is_active, created_at, updated_at
         FROM my_things WHERE course_id = $1 ORDER BY created_at DESC`,
        courseID)
    if err != nil {
        return nil, fmt.Errorf("MyThingRepo.GetByCourse: %w", err)
    }
    defer rows.Close()

    var result []models.MyThing
    for rows.Next() {
        var t models.MyThing
        if err := rows.Scan(&t.ID, &t.CourseID, &t.Title, &t.IsActive, &t.CreatedAt, &t.UpdatedAt); err != nil {
            return nil, fmt.Errorf("MyThingRepo.GetByCourse scan: %w", err)
        }
        result = append(result, t)
    }
    return result, rows.Err()
}
```

### Step 5: Service
```go
// internal/service/my_thing_service.go
package service

import (
    "context"
    "fmt"
    "example/hello/internal/dto"
    "example/hello/internal/models"
    "example/hello/internal/repository"
)

type MyThingService struct {
    repo       *repository.MyThingRepository
    courseRepo *repository.CourseRepository
}

func NewMyThingService(repo *repository.MyThingRepository, courseRepo *repository.CourseRepository) *MyThingService {
    return &MyThingService{repo: repo, courseRepo: courseRepo}
}

func (s *MyThingService) Create(ctx context.Context, courseID int64, req *dto.CreateMyThingRequest, userID int64, role string) (*dto.MyThingResponse, error) {
    // Authorization check
    course, err := s.courseRepo.GetByID(ctx, courseID)
    if err != nil {
        return nil, fmt.Errorf("course not found")
    }
    if role != "ADMIN" && course.CreatedBy != userID {
        return nil, fmt.Errorf("permission denied")
    }

    isActive := true
    if req.IsActive != nil {
        isActive = *req.IsActive
    }

    thing := &models.MyThing{
        CourseID: courseID,
        Title:    req.Title,
        IsActive: isActive,
    }

    if err := s.repo.Create(ctx, thing); err != nil {
        return nil, fmt.Errorf("MyThingService.Create: %w", err)
    }

    return &dto.MyThingResponse{
        ID:        thing.ID,
        CourseID:  thing.CourseID,
        Title:     thing.Title,
        IsActive:  thing.IsActive,
        CreatedAt: thing.CreatedAt,
    }, nil
}
```

### Step 6: Handler
```go
// internal/handler/my_thing_handler.go
package handler

import (
    "net/http"
    "strconv"
    "example/hello/internal/dto"
    "example/hello/internal/service"
    "github.com/gin-gonic/gin"
)

type MyThingHandler struct {
    service *service.MyThingService
}

func NewMyThingHandler(s *service.MyThingService) *MyThingHandler {
    return &MyThingHandler{service: s}
}

func (h *MyThingHandler) Create(c *gin.Context) {
    courseID, err := strconv.ParseInt(c.Param("courseId"), 10, 64)
    if err != nil {
        c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_course_id", "Invalid course ID"))
        return
    }

    var req dto.CreateMyThingRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
        return
    }

    userID := c.MustGet("user_id").(int64)
    role := c.GetString("user_role")

    result, err := h.service.Create(c.Request.Context(), courseID, &req, userID, role)
    if err != nil {
        c.JSON(http.StatusBadRequest, dto.NewErrorResponse("create_failed", err.Error()))
        return
    }

    c.JSON(http.StatusCreated, dto.NewDataResponse(result))
}
```

### Step 7: Wire in main.go
```go
// In main.go — add to initialization section:
myThingRepo := repository.NewMyThingRepository(db)
myThingService := service.NewMyThingService(myThingRepo, courseRepo)
myThingHandler := handler.NewMyThingHandler(myThingService)

// In router section:
courses := auth.Group("/courses")
{
    courses.POST("/:courseId/my-things", myThingHandler.Create)
    // ...
}
```

---

## Authentication & Authorization

### JWT Middleware — Sets Context Values
```go
// middleware/auth.go sets these in Gin context:
c.Set("user_id", claims.UserID)      // int64
c.Set("user_email", claims.Email)    // string
c.Set("user_roles", claims.Roles)    // []string — e.g., ["TEACHER", "STUDENT", "ADMIN"]
c.Set("user_role", claims.Roles[0])  // string — primary role for backward compat

// JWT Claims struct:
type Claims struct {
    UserID int64    `json:"user_id"`
    Email  string   `json:"email"`
    Roles  []string `json:"roles"`
    jwt.RegisteredClaims
}
```

### Extracting User in Handler
```go
// ✅ MustGet panics if key missing — use when middleware guarantees the value
userID := c.MustGet("user_id").(int64)

// ✅ Get returns (value, bool) — use when value might be absent
userID, exists := c.Get("user_id")
if !exists { /* handle */ }

// ✅ GetString is convenient but returns "" if missing
role := c.GetString("user_role")

// ✅ For multi-role checks
rolesIface, _ := c.Get("user_roles")
roles, _ := rolesIface.([]string)
```

### Role-Based Middleware
```go
// Require single role
router.POST("/something", middleware.RequireRole("ADMIN"), handler.Create)

// Require any of multiple roles
router.DELETE("/:id", middleware.RequireRoles("ADMIN", "TEACHER"), handler.Delete)

// In service layer — always double-check (defense in depth)
if role != "ADMIN" && course.CreatedBy != userID {
    return nil, fmt.Errorf("permission denied: you don't own this course")
}
```

---

## File Upload & Serving

### Storage Interface
```go
// All file operations go through pkg/storage/storage.go interface
type Storage interface {
    Upload(ctx context.Context, filename string, reader io.Reader, size int64, contentType string) (string, error)
    GetObject(ctx context.Context, filename string) (*ObjectResult, error)
    Delete(ctx context.Context, filename string) error
}
```

### Upload Pattern — Stream, Never Buffer
```go
// ✅ Stream from multipart reader directly to storage (no RAM buffering)
src, _ := file.Open()
defer src.Close()
_, err = h.storage.Upload(ctx, filename, src, file.Size, contentType)

// ❌ Never do this — buffers entire file in RAM
data, _ := io.ReadAll(src)  // BAD for large files
```

### File Serving — Use http.ServeContent
```go
// ✅ ServeContent handles Range requests, ETag, If-Modified-Since automatically
result, _ := h.storage.GetObject(ctx, filename)
defer result.Body.Close()
c.Writer.Header().Set("Content-Type", contentType)
http.ServeContent(c.Writer, c.Request, filepath.Base(filename), result.LastModified, result.Body)
// → Enables video seeking, browser caching, partial downloads
```

### Path Security — sanitizeFilePath
```go
// Always sanitize file paths to prevent path traversal
// "/document/../../../etc/passwd" → rejected
filename, ok := sanitizeFilePath(c.Param("filepath"))
if !ok {
    c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_filename", "Invalid file path"))
    return
}
```

---

## Database Patterns

### sql.NullXxx — Handle Nullable Columns
```go
// Models use sql.Null* for nullable DB columns
type Course struct {
    Description  sql.NullString  `db:"description"`
    PassingScore sql.NullFloat64 `db:"passing_score"`
    SubmittedAt  sql.NullTime    `db:"submitted_at"`
}

// Convert to pointer for DTO (nil if invalid)
func fromNullString(ns sql.NullString) string {
    if ns.Valid { return ns.String }
    return ""
}
func fromNullFloat64Ptr(nf sql.NullFloat64) *float64 {
    if nf.Valid { return &nf.Float64 }
    return nil
}
```

### Dynamic WHERE Clause Pattern
```go
// Build dynamic queries safely (no string interpolation — use $N params)
conditions := []string{"status = 'ready'"}
params := []interface{}{embeddingStr, topK}
idx := 3

if courseID != nil {
    conditions = append(conditions, fmt.Sprintf("course_id = $%d", idx))
    params = append(params, *courseID)
    idx++
}

where := strings.Join(conditions, " AND ")
sql := fmt.Sprintf(`SELECT * FROM chunks WHERE %s LIMIT $2`, where)
rows, err := r.db.QueryContext(ctx, sql, params...)
```

### pgvector Queries (AI feature)
```go
// Cosine similarity search — use <=> operator
// embedding must be passed as "[0.1,0.2,...]"::vector
embeddingStr := "[" + strings.Join(floatSliceToStrings(embedding), ",") + "]"

rows, err := r.db.QueryContext(ctx, `
    SELECT id, chunk_text,
           1 - (embedding <=> $1::vector) AS similarity
    FROM document_chunks
    WHERE course_id = $2
      AND status = 'ready'
      AND 1 - (embedding <=> $1::vector) >= 0.30
    ORDER BY embedding <=> $1::vector
    LIMIT $3
`, embeddingStr, courseID, topK)
```

---

## Redis Cache

### Key Naming Convention
```go
// Use pkg/cache/redis.go KeyXxx() functions — never raw strings
cache.KeyCourse(courseID)            // "course:123"
cache.KeyCourseStats(courseID)       // "course:123:stats"
cache.KeyStudentProgress(enrollID)   // "progress:enrollment:456"
```

### Cache-Aside Pattern
```go
func (s *CourseService) GetCourse(ctx context.Context, id int64) (*dto.CourseResponse, error) {
    cacheKey := cache.KeyCourse(id)

    // 1. Try cache
    if cached, err := s.cache.Get(ctx, cacheKey); err == nil {
        var course dto.CourseResponse
        if err := json.Unmarshal([]byte(cached), &course); err == nil {
            return &course, nil
        }
    }

    // 2. Query DB
    course, err := s.courseRepo.GetByID(ctx, id)
    if err != nil { return nil, err }

    resp := toCourseResponse(course)

    // 3. Populate cache
    if data, err := json.Marshal(resp); err == nil {
        s.cache.Set(ctx, cacheKey, data, 10*time.Minute)
    }

    return resp, nil
}

// Invalidate on update/delete
s.cache.Delete(ctx, cache.KeyCourse(id))
```

---

## Routing Structure in main.go

```go
// Public
router.GET("/health", healthHandler)
router.GET("/swagger/*any", ginSwagger.WrapHandler(...))

// Sync (internal only — protected by X-Sync-Secret header)
sync := v1.Group("/sync")
sync.Use(syncHandler.SyncSecret())
{
    sync.POST("/user", ...)
    sync.POST("/users/bulk", ...)
    sync.DELETE("/user/:userId", ...)
}

// Files — public GET, protected POST/DELETE
files := v1.Group("/files")
files.GET("/serve/*filepath", fileHandler.ServeFile)    // public
files.GET("/download/*filepath", fileHandler.DownloadFile) // public
protected := files.Group("")
protected.Use(middleware.AuthMiddleware(cfg.JWT.Secret))
protected.POST("/upload", fileHandler.UploadFile)

// All other routes — JWT required
auth := v1.Group("")
auth.Use(middleware.AuthMiddleware(cfg.JWT.Secret))
{
    // Add new route groups here
    // courses, sections, content, enrollments, quizzes, etc.
}
```

---

## AI Integration (pkg/ai/client.go)

All LMS → AI communication goes through `pkg/ai/Client`:

```go
aiClient := ai.NewClient()  // reads AI_SERVICE_URL, AI_SERVICE_SECRET from env

// Trigger document ingestion (async via Celery)
resp, err := aiClient.ProcessDocument(ctx, ai.ProcessDocumentRequest{
    ContentID:   contentID,
    CourseID:    courseID,
    FileURL:     filePath,   // MinIO object key
    ContentType: "application/pdf",
})

// Diagnose wrong answer
diag, err := aiClient.DiagnoseError(ctx, ai.DiagnoseRequest{
    StudentID:   studentID,
    AttemptID:   attemptID,
    QuestionID:  questionID,
    WrongAnswer: wrongAnswer,
    CourseID:    courseID,
})

// AI generates quiz questions (DRAFT → teacher reviews → PUBLISHED)
result, err := aiClient.GenerateQuiz(ctx, ai.GenerateQuizRequest{
    NodeID:            nodeID,
    CourseID:          courseID,
    CreatedBy:         userID,
    BloomLevels:       []string{"remember", "understand", "apply"},
    Language:          "vi",
    QuestionsPerLevel: 1,
})
```

---

## Swagger Documentation

```go
// Regenerate after changing handler godoc comments:
swag init -g cmd/api/main.go -o docs

// Swagger UI available at (through Next.js proxy):
// http://localhost:3000/lmsapidocs/swagger/index.html

// Godoc comment format for handlers:
// CreateCourse godoc
// @Summary Create a course
// @Description Create a new course (Teacher/Admin only)
// @Tags courses
// @Accept json
// @Produce json
// @Param course body dto.CreateCourseRequest true "Course data"
// @Security BearerAuth
// @Success 201 {object} dto.CourseResponse
// @Failure 400 {object} dto.ErrorResponse
// @Router /courses [post]
```

---

## Testing

```bash
go test ./...                          # Run all tests
go test ./internal/service/...        # Run specific package
go test -v -run TestCreateCourse      # Run specific test
go test ./... -coverprofile=cov.out   # With coverage
go tool cover -html=cov.out           # View HTML coverage report
go vet ./...                          # Static analysis — always run before commit
```

---

## Build & Run

```bash
# Development
go run cmd/api/main.go

# Generate swagger docs
swag init -g cmd/api/main.go -o docs

# Build binary
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s" \
    -o lms-server ./cmd/api

# Docker
docker compose up -d --build lms-backend
docker compose logs -f lms-backend
```

---

## Code Quality Checklist

```
[ ] All errors checked — no `_, _` discarding errors that matter
[ ] All error messages wrapped with fmt.Errorf("Package.FuncName: %w", err)
[ ] ctx passed to all DB calls and downstream calls
[ ] go vet ./... passes with no warnings
[ ] New env vars added to config/config.go + .env.example + docker-compose.yml
[ ] New route registered in cmd/api/main.go with correct middleware
[ ] Swagger godoc comment added to new handlers
[ ] swag init run after godoc changes
[ ] SQL migrations use IF NOT EXISTS / ON CONFLICT DO NOTHING (idempotent)
[ ] File paths sanitized before storage operations
[ ] Large files streamed (never io.ReadAll into RAM for uploads > 1MB)
[ ] Nullable DB columns use sql.NullXxx in models
[ ] No hardcoded strings for error messages — define sentinel errors or const
[ ] Rate limiting considered for public endpoints
```

---

## Known Issues & TODOs

1. **`testBulkRegister_AssignsDefaultPassword`** in auth service tests — test assertion is wrong (unrelated to LMS but affects cross-service understanding)
2. **MinIO `depends_on`** — if using `STORAGE_TYPE=minio`, add `minio: {condition: service_healthy}` to `lms-backend` in `docker-compose.yml`
3. **`quiz_summary_view`** — the `ListQuizzesByCourse` method in `quiz_repo.go` scans only a subset of view columns; update scan if view schema changes
4. **`GetStudentQuizScores` query** — uses window function in aggregation that may behave unexpectedly on some PostgreSQL versions; test thoroughly