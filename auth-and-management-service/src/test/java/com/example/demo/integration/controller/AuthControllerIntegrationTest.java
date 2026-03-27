package com.example.demo.integration.controller;

import com.example.demo.common.TestDataFactory;
import com.example.demo.dto.auth.*;
import com.example.demo.enums.*;
import com.example.demo.model.User;
import com.example.demo.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
@DisplayName("AuthController Integration Tests")
class AuthControllerIntegrationTest {

    @Autowired MockMvc         mockMvc;
    @Autowired ObjectMapper    objectMapper;
    @Autowired UserRepository  userRepository;
    @Autowired PasswordEncoder passwordEncoder;

    private User testUser;

    @BeforeEach
    void setUp() {
        testUser = userRepository.save(User.builder()
                .name("Test User")
                .email("test@example.com")
                .password(passwordEncoder.encode("ValidPass1"))
                .role(UserRole.ROLE_USER)
                .team(UserTeam.RESEARCH)
                .code("TEST001")
                .type(UserType.DT)
                .active(true)
                .totalScore(0)
                .build());
    }

    @Test
    @DisplayName("POST /login - 200 with correct credentials, returns token in body + cookie")
    void login_success_200() throws Exception {
        var req = LoginRequest.builder()
                .email("test@example.com")
                .password("ValidPass1")
                .build();

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").exists())
                .andExpect(jsonPath("$.userId").value(testUser.getId()))
                .andExpect(jsonPath("$.email").value("test@example.com"))
                .andExpect(jsonPath("$.role").value("ROLE_USER"))
                .andExpect(jsonPath("$.expiresIn").isNumber())
                .andExpect(cookie().exists("authToken"))
                .andExpect(cookie().httpOnly("authToken", true))
                .andExpect(cookie().exists("refreshToken"));
    }

    @Test
    @DisplayName("POST /login - 400 with wrong password")
    void login_wrongPassword_400() throws Exception {
        var req = LoginRequest.builder()
                .email("test@example.com")
                .password("WrongPassword")
                .build();

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Invalid email or password"));
    }

    @Test
    @DisplayName("POST /login - 400 with unknown email")
    void login_unknownEmail_400() throws Exception {
        var req = LoginRequest.builder()
                .email("unknown@example.com")
                .password("ValidPass1")
                .build();

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Invalid email or password"));
    }

    @Test
    @DisplayName("POST /logout - 200 clears cookies")
    void logout_200_clearsCookies() throws Exception {
        mockMvc.perform(post("/api/auth/logout"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("Logged out successfully"))
                .andExpect(cookie().maxAge("authToken", 0))
                .andExpect(cookie().maxAge("refreshToken", 0));
    }

    @Test
    @DisplayName("POST /register/bulk - 403 for non-admin")
    void bulkRegister_nonAdmin_403() throws Exception {
        var req = new BulkRegisterRequest(List.of(
                TestDataFactory.registerRequest("newuser@test.com", "N001")));

        mockMvc.perform(post("/api/auth/register/bulk")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isUnauthorized()); // no auth
    }

    @Test
    @WithMockUser(username = "admin@test.com", authorities = "ROLE_ADMIN")
    @DisplayName("POST /register/bulk - 200 admin can register users")
    void bulkRegister_admin_200() throws Exception {
        userRepository.save(User.builder()
                .name("Admin").email("admin@test.com")
                .password(passwordEncoder.encode("AdminPass1"))
                .role(UserRole.ROLE_ADMIN).team(UserTeam.RESEARCH)
                .code("ADM001").type(UserType.DT).active(true).totalScore(0).build());

        var req = new BulkRegisterRequest(List.of(
                TestDataFactory.registerRequest("newuser1@test.com", "N001")));

        mockMvc.perform(post("/api/auth/register/bulk")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].email").value("newuser1@test.com"));
    }

    @Test
    @WithMockUser(username = "admin@test.com", authorities = "ROLE_ADMIN")
    @DisplayName("POST /register/bulk - 409 when email already exists")
    void bulkRegister_duplicateEmail_409() throws Exception {
        // test@example.com already exists from setUp
        var req = new BulkRegisterRequest(List.of(
                TestDataFactory.registerRequest("test@example.com", "DUP001")));

        mockMvc.perform(post("/api/auth/register/bulk")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isConflict());
    }

    @Test
    @DisplayName("POST /request-password-change - 400 when current password wrong")
    void requestPasswordChange_wrongCurrentPassword_400() throws Exception {
        var req = new PasswordChangeRequest();
        req.setEmail("test@example.com");
        req.setCurrentPassword("WrongPass");
        req.setNewPassword("NewPass1A");

        mockMvc.perform(post("/api/auth/request-password-change")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest());
    }
}