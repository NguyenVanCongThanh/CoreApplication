---
name: bdc-test-writer
description: >
  Use when writing, reviewing, or expanding test cases for any BDC service.
  Covers: unit tests, integration tests, repository tests, service tests,
  controller tests, and Celery task tests across Java (JUnit 5), Go (testing),
  and Python (pytest). Enforces formal test naming, AAA structure, coverage
  requirements, and service-specific test conventions.
triggers:
  - test
  - testing
  - unit test
  - integration test
  - test case
  - junit
  - pytest
  - go test
  - coverage
  - mock
  - testcontainers
version: "1.0"
authors:
  - BDC Team
requires:
  - bdc-core-orchestrator
---

# BDC Test Writer — Skill

## Role & Scope
You are a test engineer for the BDC CoreApplication project.
Your responsibility is to produce test cases that are correct, isolated,
deterministic, and maintainable.
Tests are not an afterthought — they are specifications.
A test that passes for the wrong reason is worse than no test at all.

Always load the orchestrator skill first, then load the relevant service skill
before writing tests for that service.

---

## Universal Rules (Apply to All Services)

```
1.  Every test must follow AAA structure: Arrange, Act, Assert.
    Label each section with a comment if the block is longer than 5 lines.

2.  Test names must be descriptive enough to diagnose a failure without
    reading the test body.
    Format: [method]_[scenario]_[expectedOutcome]
    Example: createCourse_withDuplicateTitle_throwsConflictException

3.  One logical assertion per test. Multiple assert statements are permitted
    only when they verify a single logical outcome (e.g., verifying all fields
    of a returned object).

4.  Tests must be fully isolated. No shared mutable state between tests.
    No dependency on test execution order.

5.  No real external services in unit tests. All I/O — database, HTTP, email,
    Redis, MinIO — must be mocked or replaced with an in-memory substitute.

6.  Integration tests that require a real database must use Testcontainers
    or an equivalent isolated container — never a shared dev/staging database.

7.  Tests must be deterministic. Any use of random data, timestamps, or UUIDs
    must be seeded or fixed in the Arrange phase.

8.  Test code is production code. Apply the same naming conventions, style
    rules, and review standards as application code.

9.  Do not test framework behavior. Test only code you own.

10. Every bug fix must be accompanied by a regression test that reproduces
    the bug before the fix is applied.
```

---

## Test Taxonomy

```
+------------------+----------------------------------------------------------+
| Level            | Description                                              |
+------------------+----------------------------------------------------------+
| Unit             | Single class/function in isolation. All deps mocked.     |
| Integration      | Multiple real components (e.g., service + real DB).      |
| Controller/API   | Full HTTP request/response cycle. DB may be mocked.      |
| End-to-End       | Full stack. Scope: outside this skill.                   |
+------------------+----------------------------------------------------------+

Coverage targets (minimum, enforced in CI):
  - Service layer:     80% line coverage
  - Repository layer:  70% line coverage
  - Controller layer:  70% line coverage
  - Overall per service: 70% line coverage
```

---

## Java / Spring Boot (auth-and-management-service)

### Test Stack
```
JUnit 5          -- test runner and assertions
Mockito          -- mocking dependencies
MockMvc          -- controller layer HTTP simulation
@DataJpaTest     -- repository layer with embedded H2
@SpringBootTest  -- full application context (integration)
Testcontainers   -- real PostgreSQL for integration tests
AssertJ          -- fluent assertions (preferred over JUnit assertEquals)
```

### Naming Convention
```java
// Class name: [ClassUnderTest]Test
class AuthServiceTest { ... }
class CourseRepositoryTest { ... }
class UserControllerTest { ... }

// Method name: [method]_[scenario]_[expectedOutcome]
@Test
void login_withValidCredentials_returnsJwtToken() { ... }

@Test
void login_withWrongPassword_throwsAuthenticationException() { ... }

@Test
void bulkRegister_withDuplicateEmail_skipsExistingUser() { ... }
```

### Unit Test — Service Layer
```java
// src/test/java/.../service/AuthServiceTest.java

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private JwtService jwtService;

    @Mock
    private PasswordEncoder passwordEncoder;

    @InjectMocks
    private AuthService authService;

    // -------------------------------------------------------------------------
    // login()
    // -------------------------------------------------------------------------

    @Test
    void login_withValidCredentials_returnsAuthResponseWithToken() {
        // Arrange
        LoginRequest request = LoginRequest.builder()
            .email("student@bdc.com")
            .password("correct-password")
            .build();

        User user = User.builder()
            .id(1L)
            .email("student@bdc.com")
            .password("$2a$encoded")
            .role(UserRole.ROLE_USER)
            .build();

        when(userRepository.findByEmail("student@bdc.com"))
            .thenReturn(Optional.of(user));
        when(passwordEncoder.matches("correct-password", "$2a$encoded"))
            .thenReturn(true);
        when(jwtService.generateToken(user))
            .thenReturn("mock.jwt.token");

        // Act
        AuthResponse response = authService.login(request);

        // Assert
        assertThat(response.getToken()).isEqualTo("mock.jwt.token");
        assertThat(response.getEmail()).isEqualTo("student@bdc.com");
        verify(jwtService, times(1)).generateToken(user);
    }

    @Test
    void login_withNonExistentEmail_throwsResourceNotFoundException() {
        // Arrange
        LoginRequest request = LoginRequest.builder()
            .email("ghost@bdc.com")
            .password("any-password")
            .build();

        when(userRepository.findByEmail("ghost@bdc.com"))
            .thenReturn(Optional.empty());

        // Act & Assert
        assertThatThrownBy(() -> authService.login(request))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasMessageContaining("ghost@bdc.com");

        verify(jwtService, never()).generateToken(any());
    }

    @Test
    void login_withWrongPassword_throwsAuthenticationException() {
        // Arrange
        User user = User.builder().password("$2a$encoded").build();

        when(userRepository.findByEmail(any())).thenReturn(Optional.of(user));
        when(passwordEncoder.matches(any(), any())).thenReturn(false);

        // Act & Assert
        assertThatThrownBy(() -> authService.login(
            LoginRequest.builder().email("a@b.com").password("wrong").build()
        )).isInstanceOf(BadCredentialsException.class);
    }

    // -------------------------------------------------------------------------
    // bulkRegister()
    // -------------------------------------------------------------------------

    @Test
    void bulkRegister_withNewUsers_savesAllUsersAndTriggersSync() {
        // Arrange
        List<RegisterRequest> requests = List.of(
            RegisterRequest.builder().email("a@bdc.com").fullName("User A").build(),
            RegisterRequest.builder().email("b@bdc.com").fullName("User B").build()
        );

        when(userRepository.existsByEmail(any())).thenReturn(false);
        when(userRepository.save(any())).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            u.setId(ThreadLocalRandom.current().nextLong(1, 1000));
            return u;
        });

        // Act
        authService.bulkRegister(BulkRegisterRequest.builder().users(requests).build());

        // Assert
        verify(userRepository, times(2)).save(any(User.class));
        // Sync is @Async — verify the trigger, not the HTTP call
        verify(userSyncService, times(1)).syncUsersToLms(anyList());
    }

    @Test
    void bulkRegister_withExistingEmail_skipsExistingAndSavesNewOnly() {
        // Arrange
        when(userRepository.existsByEmail("existing@bdc.com")).thenReturn(true);
        when(userRepository.existsByEmail("new@bdc.com")).thenReturn(false);

        List<RegisterRequest> requests = List.of(
            RegisterRequest.builder().email("existing@bdc.com").build(),
            RegisterRequest.builder().email("new@bdc.com").build()
        );

        // Act
        authService.bulkRegister(BulkRegisterRequest.builder().users(requests).build());

        // Assert
        verify(userRepository, times(1)).save(any());
    }
}
```

### Repository Test — @DataJpaTest
```java
// src/test/java/.../repository/UserRepositoryTest.java

@DataJpaTest
@ActiveProfiles("test")  // loads application-test.yaml (H2)
class UserRepositoryTest {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void findByEmail_withExistingEmail_returnsUser() {
        // Arrange
        User user = User.builder()
            .email("test@bdc.com")
            .fullName("Test User")
            .password("encoded-password")
            .role(UserRole.ROLE_USER)
            .build();
        entityManager.persistAndFlush(user);

        // Act
        Optional<User> result = userRepository.findByEmail("test@bdc.com");

        // Assert
        assertThat(result).isPresent();
        assertThat(result.get().getFullName()).isEqualTo("Test User");
    }

    @Test
    void findByEmail_withNonExistentEmail_returnsEmpty() {
        // Act
        Optional<User> result = userRepository.findByEmail("nobody@bdc.com");

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    void existsByEmail_withExistingEmail_returnsTrue() {
        // Arrange
        entityManager.persistAndFlush(
            User.builder().email("check@bdc.com").password("x").role(UserRole.ROLE_USER).build()
        );

        // Act & Assert
        assertThat(userRepository.existsByEmail("check@bdc.com")).isTrue();
        assertThat(userRepository.existsByEmail("absent@bdc.com")).isFalse();
    }
}
```

### Controller Test — MockMvc
```java
// src/test/java/.../controller/AuthControllerTest.java

@WebMvcTest(AuthController.class)
@ActiveProfiles("test")
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private AuthService authService;

    @MockBean
    private JwtService jwtService;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void login_withValidBody_returns200WithToken() throws Exception {
        // Arrange
        LoginRequest request = LoginRequest.builder()
            .email("user@bdc.com")
            .password("secret")
            .build();

        AuthResponse response = AuthResponse.builder()
            .token("mock.jwt.token")
            .email("user@bdc.com")
            .build();

        when(authService.login(any(LoginRequest.class))).thenReturn(response);

        // Act & Assert
        mockMvc.perform(
            post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request))
        )
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.token").value("mock.jwt.token"))
        .andExpect(jsonPath("$.email").value("user@bdc.com"));
    }

    @Test
    void login_withMissingEmail_returns400() throws Exception {
        // Arrange
        String body = """
            { "password": "secret" }
            """;

        // Act & Assert
        mockMvc.perform(
            post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body)
        )
        .andExpect(status().isBadRequest());

        verify(authService, never()).login(any());
    }

    @Test
    void login_withServiceException_returns401() throws Exception {
        // Arrange
        when(authService.login(any()))
            .thenThrow(new BadCredentialsException("Invalid credentials"));

        String body = objectMapper.writeValueAsString(
            LoginRequest.builder().email("a@b.com").password("wrong").build()
        );

        // Act & Assert
        mockMvc.perform(
            post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body)
        )
        .andExpect(status().isUnauthorized());
    }
}
```

### test application-test.yaml
```yaml
# src/test/resources/application-test.yaml
spring:
  datasource:
    url: jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1;MODE=PostgreSQL
    driver-class-name: org.h2.Driver
  jpa:
    hibernate:
      ddl-auto: create-drop
    database-platform: org.hibernate.dialect.H2Dialect

jwt:
  secret: test-secret-key-must-be-at-least-32-chars-long
  expiration: 3600000

lms:
  api:
    url: http://localhost:8081  # will be mocked in tests
    secret: test-sync-secret
```

---

## Go (lms-service)

### Test Stack
```
testing          -- standard library test runner
testify/assert   -- assertion helpers (github.com/stretchr/testify)
testify/mock     -- interface mocking
sqlmock          -- database/sql mock (github.com/DATA-DOG/go-sqlmock)
httptest         -- net/http/httptest for handler tests
```

### Naming Convention
```go
// File name: [file_under_test]_test.go (same package)
// Function name: Test[FunctionName]_[Scenario]_[ExpectedOutcome]

func TestCourseService_CreateCourse_WithValidInput_ReturnsCourse(t *testing.T) { ... }
func TestCourseService_CreateCourse_WithDuplicateTitle_ReturnsError(t *testing.T) { ... }
func TestCourseRepository_GetByID_WithNonExistentID_ReturnsErrNoRows(t *testing.T) { ... }
```

### Unit Test — Service Layer (with sqlmock)
```go
// internal/service/course_service_test.go
package service_test

import (
    "context"
    "database/sql"
    "testing"

    "github.com/DATA-DOG/go-sqlmock"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"

    "example/hello/internal/dto"
    "example/hello/internal/models"
    "example/hello/internal/repository"
    "example/hello/internal/service"
)

func TestCourseService_CreateCourse_WithValidInput_ReturnsCourse(t *testing.T) {
    // Arrange
    db, mock, err := sqlmock.New()
    require.NoError(t, err)
    defer db.Close()

    mock.ExpectQuery(`INSERT INTO courses`).
        WithArgs("Go Fundamentals", "Introduction to Go", int64(1)).
        WillReturnRows(sqlmock.NewRows([]string{"id", "created_at", "updated_at"}).
            AddRow(int64(42), fixedTime, fixedTime))

    courseRepo := repository.NewCourseRepository(db)
    svc := service.NewCourseService(courseRepo)

    req := &dto.CreateCourseRequest{
        Title:       "Go Fundamentals",
        Description: "Introduction to Go",
    }

    // Act
    result, err := svc.CreateCourse(context.Background(), req, int64(1), "TEACHER")

    // Assert
    require.NoError(t, err)
    assert.Equal(t, int64(42), result.ID)
    assert.Equal(t, "Go Fundamentals", result.Title)
    assert.NoError(t, mock.ExpectationsWereMet())
}

func TestCourseService_CreateCourse_WithDatabaseError_PropagatesError(t *testing.T) {
    // Arrange
    db, mock, err := sqlmock.New()
    require.NoError(t, err)
    defer db.Close()

    mock.ExpectQuery(`INSERT INTO courses`).
        WillReturnError(sql.ErrConnDone)

    courseRepo := repository.NewCourseRepository(db)
    svc := service.NewCourseService(courseRepo)

    // Act
    result, err := svc.CreateCourse(
        context.Background(),
        &dto.CreateCourseRequest{Title: "Test"},
        int64(1),
        "TEACHER",
    )

    // Assert
    assert.Nil(t, result)
    assert.Error(t, err)
    assert.ErrorIs(t, err, sql.ErrConnDone)
}

// Table-driven test — use when testing multiple input variations
func TestCourseService_GetCourse_Authorization(t *testing.T) {
    tests := []struct {
        name        string
        role        string
        courseOwner int64
        callerID    int64
        expectError bool
    }{
        {
            name:        "admin can access any course",
            role:        "ADMIN",
            courseOwner: 99,
            callerID:    1,
            expectError: false,
        },
        {
            name:        "teacher can access own course",
            role:        "TEACHER",
            courseOwner: 1,
            callerID:    1,
            expectError: false,
        },
        {
            name:        "teacher cannot access other's course",
            role:        "TEACHER",
            courseOwner: 99,
            callerID:    1,
            expectError: true,
        },
    }

    for _, tc := range tests {
        t.Run(tc.name, func(t *testing.T) {
            // Arrange
            db, mock, _ := sqlmock.New()
            defer db.Close()

            mock.ExpectQuery(`SELECT .* FROM courses WHERE id`).
                WillReturnRows(sqlmock.NewRows([]string{"id", "title", "created_by"}).
                    AddRow(int64(1), "Test Course", tc.courseOwner))

            svc := service.NewCourseService(repository.NewCourseRepository(db))

            // Act
            _, err := svc.GetCourse(context.Background(), 1, tc.callerID, tc.role)

            // Assert
            if tc.expectError {
                assert.Error(t, err)
            } else {
                assert.NoError(t, err)
            }
        })
    }
}
```

### Handler Test — httptest
```go
// internal/handler/course_handler_test.go
package handler_test

import (
    "bytes"
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "testing"

    "github.com/gin-gonic/gin"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/require"

    "example/hello/internal/dto"
    "example/hello/internal/handler"
)

// MockCourseService satisfies the service interface for testing
type MockCourseService struct {
    mock.Mock
}

func (m *MockCourseService) CreateCourse(
    ctx context.Context,
    req *dto.CreateCourseRequest,
    userID int64,
    role string,
) (*dto.CourseResponse, error) {
    args := m.Called(ctx, req, userID, role)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*dto.CourseResponse), args.Error(1)
}

func setupTestRouter(h *handler.CourseHandler) *gin.Engine {
    gin.SetMode(gin.TestMode)
    r := gin.New()
    // Inject test auth values — bypass real JWT middleware
    r.Use(func(c *gin.Context) {
        c.Set("user_id", int64(1))
        c.Set("user_role", "TEACHER")
        c.Set("user_roles", []string{"TEACHER", "STUDENT"})
        c.Next()
    })
    r.POST("/api/v1/courses", h.Create)
    return r
}

func TestCourseHandler_Create_WithValidBody_Returns201(t *testing.T) {
    // Arrange
    mockSvc := new(MockCourseService)
    h := handler.NewCourseHandler(mockSvc)
    router := setupTestRouter(h)

    expectedResponse := &dto.CourseResponse{
        ID:    42,
        Title: "Go Fundamentals",
    }
    mockSvc.On("CreateCourse", mock.Anything, mock.Anything, int64(1), "TEACHER").
        Return(expectedResponse, nil)

    body, _ := json.Marshal(dto.CreateCourseRequest{
        Title:       "Go Fundamentals",
        Description: "Introduction to Go",
    })

    req := httptest.NewRequest(http.MethodPost, "/api/v1/courses", bytes.NewReader(body))
    req.Header.Set("Content-Type", "application/json")
    w := httptest.NewRecorder()

    // Act
    router.ServeHTTP(w, req)

    // Assert
    assert.Equal(t, http.StatusCreated, w.Code)

    var resp dto.CourseResponse
    err := json.Unmarshal(w.Body.Bytes(), &resp)
    require.NoError(t, err)
    assert.Equal(t, int64(42), resp.ID)

    mockSvc.AssertExpectations(t)
}

func TestCourseHandler_Create_WithMissingTitle_Returns400(t *testing.T) {
    // Arrange
    mockSvc := new(MockCourseService)
    h := handler.NewCourseHandler(mockSvc)
    router := setupTestRouter(h)

    body := []byte(`{"description": "no title provided"}`)
    req := httptest.NewRequest(http.MethodPost, "/api/v1/courses", bytes.NewReader(body))
    req.Header.Set("Content-Type", "application/json")
    w := httptest.NewRecorder()

    // Act
    router.ServeHTTP(w, req)

    // Assert
    assert.Equal(t, http.StatusBadRequest, w.Code)
    mockSvc.AssertNotCalled(t, "CreateCourse")
}
```

### Run Commands
```bash
go test ./...                            # All tests
go test ./internal/service/...          # Specific package
go test -v -run TestCourseService       # Specific test function prefix
go test -race ./...                     # Detect race conditions (always run in CI)
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out        # Visual coverage report
go vet ./...                            # Must pass before every commit
```

---

## Python / FastAPI (ai-service)

### Test Stack
```
pytest              -- test runner
pytest-asyncio      -- async test support
pytest-cov          -- coverage reporting
httpx               -- async HTTP client for FastAPI test client
unittest.mock       -- mocking (standard library)
AsyncMock           -- async function mocking (Python 3.8+)
fakeredis           -- in-memory Redis for Celery tests
```

### Naming Convention
```python
# File name: test_[module_under_test].py
# Class name: Test[ClassOrModule] (optional, for grouping)
# Function name: test_[method]_[scenario]_[expected_outcome]

def test_process_document_with_valid_pdf_queues_celery_task(): ...
def test_process_document_without_auth_returns_403(): ...
def test_diagnose_with_no_matching_chunks_returns_low_confidence(): ...
def test_parse_llm_json_with_markdown_fence_strips_and_parses(): ...
```

### conftest.py — Shared Fixtures
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.core.config import settings

@pytest.fixture
def ai_secret_header():
    """Valid auth header for all protected endpoints."""
    return {"X-AI-Secret": settings.AI_SERVICE_SECRET}

@pytest.fixture
async def client():
    """Async HTTPX test client — no real server started."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(autouse=True)
def patch_llm(monkeypatch):
    """
    Auto-applied to all tests.
    Prevents LLM model from loading during test collection.
    """
    with patch("app.core.llm.get_llm") as mock_llm, \
         patch("app.core.llm.get_embedding_model") as mock_embed:
        mock_llm.return_value = AsyncMock()
        mock_embed.return_value = AsyncMock()
        yield mock_llm, mock_embed

@pytest.fixture(autouse=True)
def celery_eager(settings):
    """
    Forces Celery tasks to execute synchronously in tests.
    Eliminates the need for a running broker.
    """
    with patch.dict("os.environ", {"CELERY_TASK_ALWAYS_EAGER": "True"}):
        yield
```

### Unit Test — Endpoint (Auth + Response)
```python
# tests/test_diagnose_endpoint.py
import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


async def test_diagnose_with_valid_request_returns_explanation(
    client, ai_secret_header
):
    # Arrange
    expected = {
        "explanation": "The correct concept is X because Y.",
        "confidence": 0.87,
        "deep_link": "/lms/courses/1/content/5",
        "sources": ["Chunk text A", "Chunk text B"],
    }

    with patch("app.api.endpoints.diagnose.diagnose_error", new_callable=AsyncMock) as mock_svc:
        mock_svc.return_value = expected

        # Act
        response = await client.post(
            "/ai/diagnose",
            headers=ai_secret_header,
            json={
                "student_id": 1,
                "attempt_id": 10,
                "question_id": 3,
                "wrong_answer": "A",
                "course_id": 1,
            },
        )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["explanation"] == expected["explanation"]
    assert 0.0 <= body["confidence"] <= 1.0
    mock_svc.assert_called_once()


async def test_diagnose_without_auth_header_returns_403(client):
    # Arrange / Act
    response = await client.post(
        "/ai/diagnose",
        json={"student_id": 1, "attempt_id": 1, "question_id": 1,
              "wrong_answer": "A", "course_id": 1},
        # Deliberately omit X-AI-Secret header
    )

    # Assert
    assert response.status_code == 403


async def test_diagnose_with_wrong_secret_returns_403(client):
    # Act
    response = await client.post(
        "/ai/diagnose",
        headers={"X-AI-Secret": "definitely-wrong-secret"},
        json={"student_id": 1, "attempt_id": 1, "question_id": 1,
              "wrong_answer": "A", "course_id": 1},
    )

    # Assert
    assert response.status_code == 403


async def test_diagnose_with_missing_required_field_returns_422(client, ai_secret_header):
    # Act — omit required field "wrong_answer"
    response = await client.post(
        "/ai/diagnose",
        headers=ai_secret_header,
        json={"student_id": 1, "attempt_id": 1, "question_id": 1, "course_id": 1},
    )

    # Assert
    assert response.status_code == 422  # FastAPI validation error
```

### Unit Test — Service Layer
```python
# tests/test_rag_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


async def test_retrieve_relevant_chunks_returns_sorted_by_similarity():
    # Arrange
    mock_rows = [
        {"chunk_text": "Most relevant chunk", "content_id": 1, "similarity": 0.92},
        {"chunk_text": "Less relevant chunk", "content_id": 2, "similarity": 0.45},
    ]

    with patch("app.services.rag_service.get_db_session") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db.fetch.return_value = mock_rows
        mock_db_ctx.return_value.__aenter__.return_value = mock_db

        from app.services.rag_service import retrieve_relevant_chunks
        embedding = [0.1] * 1536  # 1536-dim embedding vector

        # Act
        result = await retrieve_relevant_chunks(
            query_embedding=embedding,
            course_id=1,
            top_k=5,
            min_similarity=0.30,
        )

    # Assert
    assert len(result) == 2
    assert result[0]["similarity"] == 0.92
    assert result[0]["chunk_text"] == "Most relevant chunk"


async def test_retrieve_relevant_chunks_filters_below_min_similarity():
    # This tests that the SQL query is called with correct min_similarity param.
    # The filtering itself is done by PostgreSQL — we verify the param is passed.
    with patch("app.services.rag_service.get_db_session") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db.fetch.return_value = []
        mock_db_ctx.return_value.__aenter__.return_value = mock_db

        from app.services.rag_service import retrieve_relevant_chunks

        await retrieve_relevant_chunks(
            query_embedding=[0.0] * 1536,
            course_id=1,
            top_k=5,
            min_similarity=0.75,
        )

        # Verify min_similarity was passed to the SQL call
        call_args = mock_db.fetch.call_args
        assert 0.75 in call_args.args or 0.75 in call_args.kwargs.values()
```

### Unit Test — Utility Functions (Pure Logic)
```python
# tests/test_chunker.py
import pytest
from app.services.chunker import chunk_text, CHUNK_SIZE, CHUNK_OVERLAP


def test_chunk_text_with_short_input_returns_single_chunk():
    text = "Short document."
    result = chunk_text(text)
    assert len(result) == 1
    assert result[0] == text


def test_chunk_text_produces_overlapping_chunks():
    # Arrange — create text longer than CHUNK_SIZE
    text = "A" * (CHUNK_SIZE + CHUNK_OVERLAP + 100)

    # Act
    result = chunk_text(text)

    # Assert — more than one chunk produced
    assert len(result) > 1

    # Each chunk (except last) should have length == CHUNK_SIZE
    for chunk in result[:-1]:
        assert len(chunk) == CHUNK_SIZE

    # Overlap: end of chunk N matches start of chunk N+1
    overlap_from_first = result[0][-CHUNK_OVERLAP:]
    start_of_second = result[1][:CHUNK_OVERLAP]
    assert overlap_from_first == start_of_second


def test_chunk_text_with_empty_string_returns_empty_list():
    assert chunk_text("") == []


# tests/test_llm_utils.py
from app.services.quiz_service import parse_llm_json
import pytest


def test_parse_llm_json_with_plain_json_parses_correctly():
    raw = '{"questions": [{"question_text": "What is Go?"}]}'
    result = parse_llm_json(raw)
    assert result["questions"][0]["question_text"] == "What is Go?"


def test_parse_llm_json_with_markdown_fence_strips_and_parses():
    raw = "```json\n{\"questions\": []}\n```"
    result = parse_llm_json(raw)
    assert "questions" in result


def test_parse_llm_json_with_invalid_json_raises_value_error():
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_llm_json("this is not json {{{")


def test_parse_llm_json_with_empty_string_raises_value_error():
    with pytest.raises(ValueError):
        parse_llm_json("")
```

### Unit Test — Celery Tasks
```python
# tests/test_celery_tasks.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# CELERY_TASK_ALWAYS_EAGER=True is set in conftest.py — tasks run synchronously


def test_run_document_processing_success_updates_status():
    # Arrange
    with patch("app.worker.celery_app.process_document", new_callable=AsyncMock) as mock_proc:
        mock_proc.return_value = {"chunks_written": 10, "status": "completed"}

        from app.worker.celery_app import run_document_processing

        # Act
        result = run_document_processing.delay(
            content_id=1, course_id=1, file_url="docs/lecture1.pdf"
        ).get(timeout=5)

    # Assert
    assert result["status"] == "completed"
    assert result["chunks_written"] == 10
    mock_proc.assert_called_once_with(1, 1, "docs/lecture1.pdf")


def test_run_document_processing_on_failure_raises_and_does_not_swallow():
    # Arrange
    with patch("app.worker.celery_app.process_document", new_callable=AsyncMock) as mock_proc:
        mock_proc.side_effect = ConnectionError("MinIO unreachable")

        from app.worker.celery_app import run_document_processing
        from celery.exceptions import MaxRetriesExceededError

        # Act & Assert
        # After max_retries, the task should fail (not silently succeed)
        with pytest.raises((ConnectionError, MaxRetriesExceededError)):
            run_document_processing.delay(
                content_id=1, course_id=1, file_url="docs/x.pdf"
            ).get(timeout=5)
```

### Run Commands
```bash
# Run all tests
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=app --cov-report=term-missing --cov-report=html

# Run specific test file
pytest tests/test_diagnose_endpoint.py -v

# Run tests matching name pattern
pytest -k "diagnose" -v

# Run only fast unit tests (exclude integration)
pytest -m "not integration" -v
```

### pytest.ini Configuration
```ini
# pytest.ini (place in ai-service/ root)
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    integration: marks tests as integration tests (require external services)
    slow: marks tests that take > 5 seconds
```

---

## Test Coverage Requirements

### What Must Be Tested

```
+----------------------------+------------------------------------------+
| Component                  | Required Test Cases                      |
+----------------------------+------------------------------------------+
| Service method             | Happy path                               |
|                            | Each distinct error path                 |
|                            | Authorization boundary (owner vs admin)  |
+----------------------------+------------------------------------------+
| Repository method          | Returns correct result on success        |
|                            | Returns error/empty on not found         |
|                            | Handles database errors without panic    |
+----------------------------+------------------------------------------+
| Controller/Endpoint        | 2xx with valid input                     |
|                            | 400/422 with invalid input               |
|                            | 401/403 without or with wrong auth       |
|                            | 404/500 when service throws              |
+----------------------------+------------------------------------------+
| Celery Task                | Successful execution path                |
|                            | Failure does not silently swallow error  |
|                            | Retry triggered on transient error       |
+----------------------------+------------------------------------------+
| Utility / Pure function    | All branches (use table-driven tests)    |
|                            | Edge cases: empty input, max bounds      |
+----------------------------+------------------------------------------+
```

### What Must NOT Be Tested

```
- Framework internals (Spring Security filters, Gin routing, FastAPI validation)
- Generated code (Lombok getters/setters, Swagger stubs)
- Third-party library behavior (JWT encoding, bcrypt hashing)
- Trivial getters and setters with no logic
```

---

## CI Integration

```
Every pull request must pass:
  [ ] All tests pass (zero failures)
  [ ] No race conditions detected (Go: -race flag)
  [ ] Coverage does not decrease from main branch
  [ ] go vet / pylint / spotbugs report zero errors

Test commands in CI:
  Auth service:  ./mvnw test -Dspring.profiles.active=test
  LMS service:   go test -race ./...
  AI service:    pytest --cov=app --cov-fail-under=70
```

---

## Test Writing Checklist

Before submitting any test:

```
[ ] Test name follows [method]_[scenario]_[expectedOutcome] convention
[ ] AAA structure is clear — sections labeled if body > 5 lines
[ ] No real database, network, or filesystem calls in unit tests
[ ] All mocks are verified (verify(), AssertExpectations(), assert_called_once())
[ ] Test covers at least one negative/error path per happy path
[ ] No shared mutable state between tests
[ ] Deterministic — no random values, no time.Now() without injection
[ ] Table-driven / parametrized for functions with multiple input variants
[ ] conftest fixtures used for repeated setup (not copy-pasted Arrange blocks)
[ ] New test file is in the correct package (same package as code under test)
[ ] Coverage does not drop below threshold after this change
[ ] Bug fix tests reproduce the bug before the fix (red → green)
```