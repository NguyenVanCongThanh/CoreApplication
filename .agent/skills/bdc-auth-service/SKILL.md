---
name: bdc-auth-service
description: >
  Use when working in auth-and-management-service/ — Java 21 + Spring Boot 3.x.
  Covers: JWT, user sync, layered architecture, JPA, email, password reset.
triggers:
  - auth-and-management-service/
  - spring
  - java
  - jwt
  - spring boot
version: "1.0"
authors:
  - BDC Team
requires:
  - bdc-core-orchestrator
---

# BDC Auth & Management Service — Developer Skill

## Role & Scope
You are working on **`auth-and-management-service/`** — the authentication and club management backend. Built with Java 21 + Spring Boot 3.x + PostgreSQL. Always load the orchestrator skill first for cross-cutting concerns, then use this file for service-specific decisions.

**Root package:** `com.example.demo`
**Entry point:** `ClubApplication.java`
**Base URL:** `http://localhost:8080` | Docker internal: `http://backend:8080`

---

## Project Structure

```
auth-and-management-service/
├── src/main/java/com/example/demo/
│   ├── ClubApplication.java          ← @SpringBootApplication + @EnableScheduling
│   ├── config/
│   │   ├── CorsConfig.java           ← CORS whitelist (update with SecurityConfig together)
│   │   ├── DataInitializer.java      ← Seeds default admin on empty DB
│   │   ├── GlobalExceptionHandler.java ← @RestControllerAdvice — ALL errors handled here
│   │   ├── JwtAuthFilter.java        ← OncePerRequestFilter — reads JWT from header OR cookie
│   │   ├── RestTemplateConfig.java   ← RestTemplate bean + @EnableAsync
│   │   ├── SecurityConfig.java       ← Spring Security filter chain + CORS source
│   │   ├── SwaggerConfig.java        ← OpenAPI config with BearerAuth scheme
│   │   └── WebConfig.java            ← Static resource handler for /uploads/**
│   ├── controller/                   ← @RestController — HTTP only, no business logic
│   ├── service/                      ← Business logic, transactions, external calls
│   │   └── impl/                     ← UserServiceImpl implements UserService interface
│   ├── repository/                   ← Spring Data JPA repositories + custom @Query
│   ├── model/                        ← @Entity classes (JPA domain models)
│   ├── dto/                          ← Request/Response DTOs (no JPA annotations)
│   │   ├── announcement/
│   │   ├── auth/
│   │   ├── event/
│   │   ├── task/
│   │   ├── taskscore/
│   │   ├── user/
│   │   └── usertask/
│   ├── enums/                        ← Java enums (Priority, StatusEvent, UserRole, etc.)
│   ├── exception/                    ← Custom exceptions (ResourceNotFoundException)
│   ├── mapper/                       ← Manual mappers (Entity ↔ DTO) — no MapStruct
│   └── utils/                        ← Specifications (JPA Criteria), SortUtils, PasswordGenerator
├── src/main/resources/
│   ├── application.yaml              ← Local dev config
│   ├── application-docker.yaml       ← Docker profile (active via SPRING_PROFILES_ACTIVE=docker)
│   └── application-prod.yaml        ← Production overrides
└── src/test/
    ├── java/.../controller/          ← MockMvc integration tests
    ├── java/.../repository/          ← @DataJpaTest with H2
    └── java/.../service/             ← @DataJpaTest service tests
```

---

## Layered Architecture — Strict Rules

```
HTTP Request
    ↓
Controller   → validates HTTP, calls Service, never touches Repository directly
    ↓
Service      → business logic, @Transactional, calls Repository, EmailService, UserSyncService
    ↓
Repository   → Spring Data JPA + custom @Query — never returns domain model to Controller
    ↓
Database
```

**Rules:**
- Controllers **never** call `repository` directly
- Services **never** return raw `Entity` to Controller — use DTOs
- Mappers live in `mapper/` package — keep mapping logic out of Services
- `@Transactional` belongs on Service methods, not Controllers

---

## Adding a New Feature — Standard Workflow

### Step 1: Domain Model
```java
// src/main/java/.../model/MyEntity.java
@Entity
@Table(name = "my_entities")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class MyEntity {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @ManyToOne
    @JoinColumn(name = "user_id")
    private User createdBy;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() { createdAt = LocalDateTime.now(); }

    @PreUpdate
    protected void onUpdate() { updatedAt = LocalDateTime.now(); }
}
```

### Step 2: DTOs
```java
// src/main/java/.../dto/myentity/MyEntityRequest.java
@Data @Builder
public class MyEntityRequest {
    @NotBlank private String name;
    // validation annotations on request DTOs
}

// src/main/java/.../dto/myentity/MyEntityResponse.java
@Data @Builder
public class MyEntityResponse {
    private Long id;
    private String name;
    private String createdByEmail;
    private LocalDateTime createdAt;
}
```

### Step 3: Repository
```java
// src/main/java/.../repository/MyEntityRepository.java
@Repository
public interface MyEntityRepository extends JpaRepository<MyEntity, Long>, JpaSpecificationExecutor<MyEntity> {
    // Add custom queries only when needed — don't add findAll() variants that Spring Data already provides
    @Query("SELECT DISTINCT e FROM MyEntity e WHERE e.name LIKE %:keyword%")
    List<MyEntity> searchByKeyword(@Param("keyword") String keyword);
}
```

### Step 4: Service
```java
// src/main/java/.../service/MyEntityService.java
@Service
@RequiredArgsConstructor
@Slf4j
public class MyEntityService {
    private final MyEntityRepository repo;
    private final UserRepository userRepo;

    @Transactional(readOnly = true)
    public List<MyEntityResponse> getAll() {
        return repo.findAll().stream()
            .map(MyEntityMapper::toResponse)
            .toList();
    }

    @Transactional
    public MyEntityResponse create(MyEntityRequest req, String creatorEmail) {
        User creator = userRepo.findByEmail(creatorEmail)
            .orElseThrow(() -> new ResourceNotFoundException("User not found: " + creatorEmail));
        MyEntity entity = MyEntityMapper.toEntity(req, creator);
        entity.setCreatedAt(LocalDateTime.now());
        return MyEntityMapper.toResponse(repo.save(entity));
    }
    // Prefer log.info() / log.error() — never System.out.println()
}
```

### Step 5: Mapper
```java
// src/main/java/.../mapper/MyEntityMapper.java
public class MyEntityMapper {
    public static MyEntityResponse toResponse(MyEntity e) {
        return MyEntityResponse.builder()
            .id(e.getId())
            .name(e.getName())
            .createdByEmail(e.getCreatedBy() != null ? e.getCreatedBy().getEmail() : null)
            .createdAt(e.getCreatedAt())
            .build();
    }
    public static MyEntity toEntity(MyEntityRequest req, User creator) {
        return MyEntity.builder()
            .name(req.getName())
            .createdBy(creator)
            .build();
    }
}
```

### Step 6: Controller
```java
// src/main/java/.../controller/MyEntityController.java
@RestController
@RequestMapping("/api/my-entities")
@RequiredArgsConstructor
public class MyEntityController {
    private final MyEntityService service;

    @GetMapping
    public ResponseEntity<List<MyEntityResponse>> getAll() {
        return ResponseEntity.ok(service.getAll());
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    public ResponseEntity<MyEntityResponse> create(@Valid @RequestBody MyEntityRequest req) {
        String email = (String) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return ResponseEntity.ok(service.create(req, email));
    }
}
```

---

## Security & JWT

### How JwtAuthFilter Works
1. Extracts token from `Authorization: Bearer <token>` header OR `authToken` cookie
2. Validates signature using `JWT_SECRET`
3. Sets `SecurityContextHolder` with email as principal + roles as authorities
4. Both header AND cookie paths work — frontend uses cookie, mobile uses header

### Role Hierarchy
```
ROLE_ADMIN   → can do everything
ROLE_MANAGER → can create events, tasks, announcements
ROLE_USER    → read-only on most resources
```

### Securing Endpoints
```java
// Method-level security (preferred for fine-grained control)
@PreAuthorize("hasAuthority('ROLE_ADMIN')")
@PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")  // Strips ROLE_ prefix automatically

// Or configure in SecurityConfig.java for URL-level
.requestMatchers("/api/admin/**").hasAuthority("ROLE_ADMIN")
```

### Getting Current User in Service
```java
// ✅ Correct pattern — get email from SecurityContext, load user from DB
private User getCurrentUser() {
    String email = (String) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
    return userRepo.findByEmail(email)
        .orElseThrow(() -> new EntityNotFoundException("User not found: " + email));
}

// ❌ Wrong — don't inject Authentication in service layer
```

---

## Exception Handling

### GlobalExceptionHandler — The Only Place for HTTP Error Responses
```java
// All custom exceptions must be registered here
@ExceptionHandler(ResourceNotFoundException.class)
public ResponseEntity<Map<String, String>> handleResourceNotFound(ResourceNotFoundException ex) {
    return ResponseEntity.status(HttpStatus.NOT_FOUND)
        .body(Map.of("error", ex.getMessage()));
}

@ExceptionHandler(IllegalArgumentException.class)
public ResponseEntity<Map<String, String>> handleIllegalArgument(IllegalArgumentException ex) {
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(Map.of("error", ex.getMessage()));
}
```

### Custom Exception Pattern
```java
// Add to src/main/java/.../exception/
public class SomeBusinessException extends RuntimeException {
    public SomeBusinessException(String message) { super(message); }
}
// Then register in GlobalExceptionHandler
```

### Production Fix (Required Before Deploy)
```java
// ❌ Current code — EXPOSES STACK TRACE TO CLIENT
return ResponseEntity.status(500).body(Map.of(
    "error", ex.getMessage(),
    "trace", ex.getStackTrace()[0].toString()   // REMOVE THIS
));

// ✅ Production-safe pattern
@Value("${spring.profiles.active:default}")
private String activeProfile;

@ExceptionHandler(Exception.class)
public ResponseEntity<?> handleGenericException(Exception ex) {
    log.error("Unhandled exception: {}", ex.getMessage(), ex);  // log server-side
    if ("docker".equals(activeProfile) || "prod".equals(activeProfile)) {
        return ResponseEntity.status(500).body(Map.of("error", "Internal server error"));
    }
    return ResponseEntity.status(500).body(Map.of("error", ex.getMessage()));
}
```

---

## Database & JPA Patterns

### Entity Relationships — Avoid N+1

```java
// ❌ N+1 problem — loads tasks lazily for each event
List<Event> events = eventRepo.findAll();
events.forEach(e -> e.getTasks().size()); // fires N queries

// ✅ Use EntityGraph or JOIN FETCH
@EntityGraph(attributePaths = {"tasks"})
@Query("SELECT DISTINCT e FROM Event e")
List<Event> findAllWithTasks();

// ✅ Two-step fetch for multi-collection (avoids Hibernate MultipleBagFetchException)
List<Task> tasks = taskRepo.findAllWithAssignees();  // Step 1: fetch with assignees
if (!tasks.isEmpty()) {
    taskRepo.findLinksForTasks(tasks);               // Step 2: fetch links separately
}
```

### JPA Specifications (for Filtering/Search)
```java
// Pattern used in EventSpecifications, TaskSpecifications
public class MyEntitySpecifications {
    public static Specification<MyEntity> containsKeyword(String keyword, String... fields) {
        return (root, query, cb) -> {
            if (keyword == null || keyword.isEmpty()) return cb.conjunction();
            Predicate[] predicates = new Predicate[fields.length];
            for (int i = 0; i < fields.length; i++) {
                predicates[i] = cb.like(cb.lower(root.get(fields[i])), "%" + keyword.toLowerCase() + "%");
            }
            return cb.or(predicates);
        };
    }
}
// Combine: Specification.where(...).and(...).and(...)
```

### Transactional Guidelines
```java
@Transactional(readOnly = true)  // For SELECT queries — better performance
public List<X> findAll() { ... }

@Transactional                   // For INSERT/UPDATE/DELETE
public X create(X x) { ... }

// Never put @Transactional on Controller methods
// Never catch and swallow exceptions inside @Transactional (prevents rollback)
```

---

## Email Service

### When Email is Used
1. `bulkRegister()` → sends temporary password to new users
2. `requestPasswordChange()` → sends confirmation link (15 min expiry)
3. `confirmPasswordChange()` → sends "password changed" notification

### Gmail SMTP Setup
```yaml
# application.yaml
spring.mail:
  host: smtp.gmail.com
  port: 587
  username: ${EMAIL}
  password: ${EMAIL_PASSWORD}   # Must be Gmail App Password (16 chars), not regular password
  properties.mail.smtp.starttls.enable: true
```

### Danger: Silent Email Failure
`bulkRegister()` catches email exceptions and logs them — it does **not** fail the HTTP request. This means users can be created without receiving their password. Always verify email logs after bulk registration:
```bash
docker compose logs backend | grep -i "email\|mail"
```

---

## User Sync to LMS

### Sync is @Async — Never Blocks HTTP Response
```java
// UserSyncService.syncUsersToLms() is @Async — fire and forget
// If LMS is down when users are created, sync silently fails
// Manual re-sync:
curl -X POST http://localhost:8081/api/v1/sync/users/bulk \
  -H "X-Sync-Secret: $LMS_SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"users":[{"user_id":1,"email":"a@b.com","full_name":"Name","roles":["TEACHER","STUDENT"]}]}'
```

### Role Mapping Logic (in UserSyncService AND AuthService — must stay in sync)
```java
private List<String> determineRoles(UserRole userRole) {
    List<String> roles = new ArrayList<>(List.of("TEACHER", "STUDENT")); // Default for ALL users
    if (userRole == UserRole.ROLE_ADMIN) {
        roles.add("ADMIN");
    }
    return roles;
}
```

---

## Password Reset Flow

```
1. POST /api/auth/request-password-change {email, currentPassword, newPassword}
   → Validates current password
   → Creates PasswordResetToken (UUID, 15 min TTL, single-use)
   → Sends email with link: {APP_PUBLIC_URL}/confirm-password-change?token=UUID

2. POST /api/auth/confirm-password-change {token, newPassword}
   → Validates token (not used, not expired)
   → Updates password (BCrypt)
   → Marks token as used
   → Sends "password changed" notification email

3. @Scheduled(cron = "0 0 2 * * *")
   → Cleans up expired tokens nightly
   → Requires @EnableScheduling on ClubApplication (already set)
```

---

## Testing Patterns

### Repository Tests — @DataJpaTest with H2
```java
@DataJpaTest
@ActiveProfiles("test")  // Uses application-test.yaml → H2 in-memory
class UserRepositoryTest {
    @Autowired UserRepository userRepository;
    // Fast, isolated, no Spring context overhead
}
```

### Service Tests — @DataJpaTest + @Import
```java
@DataJpaTest
@Import(MyEntityService.class)
@ActiveProfiles("test")
class MyEntityServiceTest {
    @Autowired MyEntityService service;
    @Autowired MyEntityRepository repo;
}
```

### Controller Integration Tests — @SpringBootTest + MockMvc
```java
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional  // Rollback after each test
class MyEntityControllerTest {
    @Autowired MockMvc mockMvc;

    @Test
    @WithMockUser(username = "admin@test.com", roles = "ADMIN")
    void testCreate_Success() throws Exception {
        mockMvc.perform(post("/api/my-entities")
            .contentType(MediaType.APPLICATION_JSON)
            .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.id").exists());
    }
}
```

### Test Profile (application-test.yaml)
```yaml
spring:
  datasource:
    url: jdbc:h2:mem:testdb;MODE=PostgreSQL;DB_CLOSE_DELAY=-1
    driver-class-name: org.h2.Driver
  jpa:
    database-platform: org.hibernate.dialect.H2Dialect
    hibernate.ddl-auto: create-drop
jwt:
  secret: test-secret-key-for-testing-purposes-only-min32
```

---

## Maven / Dependency Management

### Adding a New Dependency
```xml
<!-- pom.xml — always check for existing Spring Boot managed versions first -->
<dependency>
    <groupId>com.example</groupId>
    <artifactId>some-lib</artifactId>
    <!-- version managed by Spring Boot BOM → omit if available -->
</dependency>
```

### Build Commands
```bash
./mvnw clean package -DskipTests -B   # Build JAR (CI fast path)
./mvnw test                            # Run all tests
./mvnw spring-boot:run                 # Local dev server
./mvnw spring-boot:run \
  -Dspring-boot.run.jvmArguments="-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=5005"
# ↑ Remote debug on port 5005 (attach IntelliJ)
```

---

## Code Quality Checklist

Before submitting any change to this service:

```
[ ] New endpoint has @PreAuthorize or is explicitly public
[ ] All business logic is in Service layer, not Controller
[ ] @Transactional(readOnly = true) on read-only Service methods
[ ] No System.out.println — use @Slf4j + log.info/warn/error
[ ] New env var added to .env.example + application.yaml + docker-compose.yml
[ ] ResourceNotFoundException used for 404 cases (registered in GlobalExceptionHandler)
[ ] N+1 queries avoided (use EntityGraph or two-step fetch for collections)
[ ] Tests written: at least Repository test + Controller integration test
[ ] CORS updated if adding new allowed origin (CorsConfig + SecurityConfig together)
[ ] Email template in EmailService sends valid HTML (test with Mailpit locally)
```

---

## Known Issues & TODOs (from existing code)

### High Priority (Fix Before Production)
1. **`JwtAuthFilter.java`** — Remove `System.out.println` debug statements
2. **`GlobalExceptionHandler.java`** — Hide stack trace in production response
3. **`CorsConfig.java` + `SecurityConfig.java`** — Read `allowedOrigins` from env var instead of hardcoding `bdc.hpcc.vn`
4. **`DataInitializer.java`** — Read admin email/password from env var, not hardcode

### Medium Priority
5. **`AuthServiceTest.java`** — `testBulkRegister_AssignsDefaultPassword` test is incorrect (asserts wrong password)
6. **`EventControllerTest.java`** — `testUpdateEvent_Success` asserts `"ONGOING"` but enum value is `"IN_PROGRESS"`