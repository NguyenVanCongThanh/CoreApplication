package com.example.demo.unit.service;

import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.util.ReflectionTestUtils;

import com.example.demo.service.auth.JwtService;

import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.*;

@DisplayName("JwtService Tests")
class JwtServiceTest {

    private JwtService jwtService;

    private static final String SECRET = "test-secret-key-32chars-minimum!!";
    private static final long   EXP_MS = 3_600_000L;   // 1h
    private static final long   REF_MS = 86_400_000L;  // 24h

    @BeforeEach
    void setUp() {
        jwtService = new JwtService();
        ReflectionTestUtils.setField(jwtService, "jwtSecret",          SECRET);
        ReflectionTestUtils.setField(jwtService, "expirationMs",       EXP_MS);
        ReflectionTestUtils.setField(jwtService, "refreshExpirationMs", REF_MS);
        jwtService.init();
    }

    // ── generateToken ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("generateToken - returns non-blank JWT with 3 parts")
    void generateToken_returnsValidJwt() {
        String token = jwtService.generateToken(1L, "admin@test.com", List.of("ADMIN", "TEACHER"));

        assertThat(token).isNotBlank();
        assertThat(token.split("\\.")).hasSize(3);
    }

    @Test
    @DisplayName("generateToken - different users produce different tokens")
    void generateToken_differentUsersProduceDifferentTokens() {
        String t1 = jwtService.generateToken(1L, "a@test.com", List.of("STUDENT"));
        String t2 = jwtService.generateToken(2L, "b@test.com", List.of("STUDENT"));

        assertThat(t1).isNotEqualTo(t2);
    }

    @Test
    @DisplayName("generateToken - same user at different times produces different tokens (iat differs)")
    void generateToken_sameUserDifferentTime() throws InterruptedException {
        String t1 = jwtService.generateToken(1L, "a@test.com", List.of("STUDENT"));
        Thread.sleep(100);
        String t2 = jwtService.generateToken(1L, "a@test.com", List.of("STUDENT"));

        assertThat(t1).isNotEqualTo(t2);
    }

    @Test
    @DisplayName("extractEmail - returns correct subject from token")
    void extractEmail_success() {
        String token = jwtService.generateToken(1L, "user@test.com", List.of("TEACHER"));

        assertThat(jwtService.extractEmail(token)).isEqualTo("user@test.com");
    }

    @Test
    @DisplayName("extractUserId - returns correct user_id claim")
    void extractUserId_success() {
        String token = jwtService.generateToken(42L, "user@test.com", List.of("TEACHER"));

        assertThat(jwtService.extractUserId(token)).isEqualTo(42L);
    }

    @Test
    @DisplayName("extractRoles - returns all roles from claim")
    void extractRoles_multipleRoles() {
        List<String> roles = List.of("TEACHER", "STUDENT", "ADMIN");
        String token = jwtService.generateToken(1L, "admin@test.com", roles);

        assertThat(jwtService.extractRoles(token)).containsExactlyInAnyOrderElementsOf(roles);
    }

    @Test
    @DisplayName("extractRoles - empty roles list preserved")
    void extractRoles_emptyList() {
        String token = jwtService.generateToken(1L, "user@test.com", List.of());

        assertThat(jwtService.extractRoles(token)).isEmpty();
    }

    @Test
    @DisplayName("generateRefreshToken - valid token, no roles claim")
    void generateRefreshToken_doesNotContainRoles() {
        String rt = jwtService.generateRefreshToken(1L, "user@test.com");

        assertThat(rt).isNotBlank();
        assertThat(jwtService.extractEmail(rt)).isEqualTo("user@test.com");
        assertThat(jwtService.extractRoles(rt)).isNull(); // refresh token has no roles
    }

    @Test
    @DisplayName("validateToken - valid token returns true")
    void validateToken_valid() {
        String token = jwtService.generateToken(1L, "user@test.com", List.of("STUDENT"));
        assertThat(jwtService.validateToken(token)).isTrue();
    }

    @Test
    @DisplayName("validateToken - tampered token returns false")
    void validateToken_tampered() {
        String token = jwtService.generateToken(1L, "user@test.com", List.of("STUDENT"));
        String tampered = token.substring(0, token.length() - 5) + "XXXXX";

        assertThat(jwtService.validateToken(tampered)).isFalse();
    }

    @Test
    @DisplayName("validateToken - expired token returns false")
    void validateToken_expired() {
        // Set expiry = -1ms (already expired)
        ReflectionTestUtils.setField(jwtService, "expirationMs", -1L);
        String token = jwtService.generateToken(1L, "user@test.com", List.of("STUDENT"));

        assertThat(jwtService.validateToken(token)).isFalse();
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"not.a.jwt", "random-string", "eyJ.eyJ.invalid"})
    @DisplayName("validateToken - invalid formats return false")
    void validateToken_invalidFormats(String token) {
        assertThat(jwtService.validateToken(token)).isFalse();
    }

    @Test
    @DisplayName("validateToken - wrong secret returns false")
    void validateToken_wrongSecret() {
        String token = jwtService.generateToken(1L, "user@test.com", List.of("STUDENT"));

        JwtService otherService = new JwtService();
        ReflectionTestUtils.setField(otherService, "jwtSecret", "another-secret-key-32chars-min!!");
        ReflectionTestUtils.setField(otherService, "expirationMs", EXP_MS);
        ReflectionTestUtils.setField(otherService, "refreshExpirationMs", REF_MS);
        otherService.init();

        assertThat(otherService.validateToken(token)).isFalse();
    }

    @Test
    @DisplayName("generateToken - thread-safe under high concurrency (50 threads)")
    void generateToken_threadSafe() throws InterruptedException {
        int threadCount  = 50;
        var latch        = new CountDownLatch(1);
        var successCount = new AtomicInteger(0);
        var errorCount   = new AtomicInteger(0);
        var executor     = Executors.newFixedThreadPool(threadCount);

        for (int i = 0; i < threadCount; i++) {
            final int id = i;
            executor.submit(() -> {
                try {
                    latch.await();
                    String token = jwtService.generateToken((long) id, "user" + id + "@test.com",
                                                            List.of("STUDENT"));
                    assertThat(jwtService.validateToken(token)).isTrue();
                    assertThat(jwtService.extractEmail(token)).isEqualTo("user" + id + "@test.com");
                    successCount.incrementAndGet();
                } catch (Exception e) {
                    errorCount.incrementAndGet();
                }
            });
        }

        latch.countDown(); // Fire!
        executor.shutdown();
        executor.awaitTermination(10, TimeUnit.SECONDS);

        assertThat(errorCount.get()).isZero();
        assertThat(successCount.get()).isEqualTo(threadCount);
    }
}