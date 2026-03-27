package com.example.demo.unit.service;

import com.example.demo.common.TestDataFactory;
import com.example.demo.dto.auth.BulkRegisterRequest;
import com.example.demo.dto.auth.LoginRequest;
import com.example.demo.exception.BadRequestException;
import com.example.demo.exception.DuplicateResourceException;
import com.example.demo.model.User;
import com.example.demo.repository.UserRepository;
import com.example.demo.service.auth.AuthService;
import com.example.demo.service.auth.JwtService;
import com.example.demo.service.email.EmailService;
import com.example.demo.service.user.UserSyncService;
import com.example.demo.strategy.RoleResolutionStrategy;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("AuthService Tests")
class AuthServiceTest {

    @Mock UserRepository          userRepository;
    @Mock JwtService              jwtService;
    @Mock PasswordEncoder         passwordEncoder;
    @Mock EmailService            emailService;
    @Mock UserSyncService         userSyncService;
    @Mock RoleResolutionStrategy  roleStrategy;

    @InjectMocks AuthService authService;

    private User admin;
    private User regularUser;

    @BeforeEach
    void setUp() {
        admin       = TestDataFactory.adminUser();
        regularUser = TestDataFactory.regularUser();
    }

    @Test
    @DisplayName("authenticate - success with correct credentials")
    void authenticate_success() {
        given(userRepository.findByEmail("admin@test.com")).willReturn(Optional.of(admin));
        given(passwordEncoder.matches("password123", admin.getPassword())).willReturn(true);

        User result = authService.authenticate(LoginRequest.builder()
                .email("admin@test.com").password("password123").build());

        assertThat(result).isEqualTo(admin);
    }

    @Test
    @DisplayName("authenticate - email not found throws BadRequestException")
    void authenticate_emailNotFound() {
        given(userRepository.findByEmail(anyString())).willReturn(Optional.empty());

        assertThatThrownBy(() ->
            authService.authenticate(LoginRequest.builder()
                .email("ghost@test.com").password("pass").build()))
            .isInstanceOf(BadRequestException.class)
            .hasMessageContaining("Invalid email or password");
    }

    @Test
    @DisplayName("authenticate - wrong password throws BadRequestException (same message for security)")
    void authenticate_wrongPassword() {
        given(userRepository.findByEmail("admin@test.com")).willReturn(Optional.of(admin));
        given(passwordEncoder.matches(anyString(), anyString())).willReturn(false);

        assertThatThrownBy(() ->
            authService.authenticate(LoginRequest.builder()
                .email("admin@test.com").password("wrong").build()))
            .isInstanceOf(BadRequestException.class)
            .hasMessageContaining("Invalid email or password");
    }

    @Test
    @DisplayName("generateToken - delegates to jwtService with resolved roles")
    void generateToken_delegatesWithRoles() {
        given(roleStrategy.resolve(admin.getRole())).willReturn(List.of("ADMIN", "TEACHER", "STUDENT"));
        given(jwtService.generateToken(eq(1L), eq("admin@test.com"), anyList())).willReturn("mock-jwt");

        String token = authService.generateToken(admin);

        assertThat(token).isEqualTo("mock-jwt");
        then(roleStrategy).should().resolve(admin.getRole());
        then(jwtService).should().generateToken(eq(1L), eq("admin@test.com"),
                argThat(roles -> roles.containsAll(List.of("ADMIN", "TEACHER", "STUDENT"))));
    }

    @Test
    @DisplayName("generateRefreshToken - delegates to jwtService without roles")
    void generateRefreshToken_delegates() {
        given(jwtService.generateRefreshToken(1L, "admin@test.com")).willReturn("refresh-token");

        assertThat(authService.generateRefreshToken(admin)).isEqualTo("refresh-token");
    }

    @Test
    @DisplayName("validateToken - delegates to jwtService")
    void validateToken_delegates() {
        given(jwtService.validateToken("token")).willReturn(true);
        assertThat(authService.validateToken("token")).isTrue();

        given(jwtService.validateToken("bad")).willReturn(false);
        assertThat(authService.validateToken("bad")).isFalse();
    }

    @Test
    @DisplayName("bulkRegister - success: validate all, saveAll once, async email+sync")
    void bulkRegister_success() {
        var req1 = TestDataFactory.registerRequest("user1@test.com", "U001");
        var req2 = TestDataFactory.registerRequest("user2@test.com", "U002");
        var bulkReq = new BulkRegisterRequest(List.of(req1, req2));

        given(userRepository.existsByEmail("user1@test.com")).willReturn(false);
        given(userRepository.existsByEmail("user2@test.com")).willReturn(false);
        given(passwordEncoder.encode(anyString())).willReturn("encoded_pw");
        given(userRepository.saveAll(anyList())).willAnswer(inv -> {
            List<User> users = inv.getArgument(0);
            // Simulate DB assign IDs
            for (int i = 0; i < users.size(); i++) {
                ReflectionTestUtils_setField(users.get(i), "id", (long)(i + 10));
            }
            return users;
        });
        given(emailService.sendWelcomeBatch(anyMap(), anyMap()))
            .willReturn(CompletableFuture.completedFuture(null));
        given(userSyncService.syncUsers(anyList()))
            .willReturn(CompletableFuture.completedFuture(null));

        List<User> result = authService.bulkRegister(bulkReq);

        assertThat(result).hasSize(2);

        // Verify saveAll called ONCE (not save per user)
        then(userRepository).should(times(1)).saveAll(anyList());
        then(userRepository).should(never()).save(any(User.class));

        // Verify async notifications triggered
        then(emailService).should(times(1)).sendWelcomeBatch(anyMap(), anyMap());
        then(userSyncService).should(times(1)).syncUsers(anyList());
    }

    @Test
    @DisplayName("bulkRegister - duplicate email throws DuplicateResourceException before any save")
    void bulkRegister_duplicateEmail_throwsBeforeSave() {
        var req = TestDataFactory.registerRequest("existing@test.com", "X001");
        var bulkReq = new BulkRegisterRequest(List.of(req));

        given(userRepository.existsByEmail("existing@test.com")).willReturn(true);

        assertThatThrownBy(() -> authService.bulkRegister(bulkReq))
            .isInstanceOf(DuplicateResourceException.class);

        // Verify NOTHING was saved
        then(userRepository).should(never()).save(any());
        then(userRepository).should(never()).saveAll(any());
        then(emailService).should(never()).sendWelcomeBatch(anyMap(), anyMap());
    }

    @Test
    @DisplayName("bulkRegister - multiple duplicates listed together in exception message")
    void bulkRegister_multipleDuplicates() {
        var req1 = TestDataFactory.registerRequest("dup1@test.com", "D001");
        var req2 = TestDataFactory.registerRequest("dup2@test.com", "D002");
        var bulkReq = new BulkRegisterRequest(List.of(req1, req2));

        given(userRepository.existsByEmail("dup1@test.com")).willReturn(true);
        given(userRepository.existsByEmail("dup2@test.com")).willReturn(true);

        assertThatThrownBy(() -> authService.bulkRegister(bulkReq))
            .isInstanceOf(DuplicateResourceException.class)
            .hasMessageContaining("dup1@test.com")
            .hasMessageContaining("dup2@test.com");
    }

    @Test
    @DisplayName("bulkRegister - email failure does not propagate (non-blocking)")
    void bulkRegister_emailFailure_doesNotPropagate() {
        var req = TestDataFactory.registerRequest("ok@test.com", "OK001");
        var bulkReq = new BulkRegisterRequest(List.of(req));

        given(userRepository.existsByEmail(anyString())).willReturn(false);
        given(passwordEncoder.encode(anyString())).willReturn("encoded");
        given(userRepository.saveAll(anyList())).willReturn(List.of(regularUser));
        // Email service fails
        given(emailService.sendWelcomeBatch(anyMap(), anyMap()))
            .willReturn(CompletableFuture.failedFuture(new RuntimeException("SMTP error")));
        given(userSyncService.syncUsers(anyList()))
            .willReturn(CompletableFuture.completedFuture(null));

        // Should NOT throw even though email failed
        assertThatCode(() -> authService.bulkRegister(bulkReq)).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("bulkRegister - assigns ROLE_USER as default when role is null")
    void bulkRegister_defaultRole() {
        var req = TestDataFactory.registerRequest("new@test.com", "N001");
        req.setRole(null); // null role → should default to ROLE_USER

        var bulkReq = new BulkRegisterRequest(List.of(req));
        given(userRepository.existsByEmail(anyString())).willReturn(false);
        given(passwordEncoder.encode(anyString())).willReturn("encoded");

        given(userRepository.saveAll(anyList())).willAnswer(inv -> {
            List<User> users = inv.getArgument(0);
            return users;
        });
        given(emailService.sendWelcomeBatch(anyMap(), anyMap()))
            .willReturn(CompletableFuture.completedFuture(null));
        given(userSyncService.syncUsers(anyList()))
            .willReturn(CompletableFuture.completedFuture(null));

        authService.bulkRegister(bulkReq);

        then(userRepository).should().saveAll(argThat(users ->
            ((List<User>) users).stream()
                .allMatch(u -> u.getRole() == com.example.demo.enums.UserRole.ROLE_USER)
        ));
    }

    // Helper to set private field in test (workaround for no setter)
    private void ReflectionTestUtils_setField(Object target, String field, Object value) {
        try {
            var f = target.getClass().getDeclaredField(field);
            f.setAccessible(true);
            f.set(target, value);
        } catch (Exception e) { /* ignore in test */ }
    }
}