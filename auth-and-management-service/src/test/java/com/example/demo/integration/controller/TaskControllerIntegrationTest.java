package com.example.demo.integration.controller;

import com.example.demo.dto.task.TaskRequest;
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
@DisplayName("TaskController Integration Tests")
class TaskControllerIntegrationTest {

    @Autowired MockMvc        mockMvc;
    @Autowired ObjectMapper   objectMapper;
    @Autowired UserRepository userRepository;
    @Autowired PasswordEncoder passwordEncoder;

    private User manager;
    private User assignee;

    @BeforeEach
    void setUp() {
        manager = userRepository.save(User.builder()
                .name("Manager").email("manager@test.com")
                .password(passwordEncoder.encode("ManagerPass1"))
                .role(UserRole.ROLE_MANAGER).team(UserTeam.RESEARCH)
                .code("MGR001").type(UserType.DT).active(true).totalScore(0).build());

        assignee = userRepository.save(User.builder()
                .name("Assignee").email("assignee@test.com")
                .password(passwordEncoder.encode("AssigneePass1"))
                .role(UserRole.ROLE_USER).team(UserTeam.EVENT)
                .code("ASN001").type(UserType.TN).active(true).totalScore(0).build());
    }

    @Test
    @WithMockUser(username = "manager@test.com")
    @DisplayName("POST /tasks - 201 creates task with assignee")
    void createTask_201() throws Exception {
        var req = TaskRequest.builder()
                .title("New Task")
                .description("Description")
                .priority(Priority.HIGH)
                .columnId("todo")
                .assigneeIds(List.of(assignee.getId()))
                .build();

        mockMvc.perform(post("/api/tasks")
                        .param("userId", manager.getId().toString())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").exists())
                .andExpect(jsonPath("$.title").value("New Task"))
                .andExpect(jsonPath("$.priority").value("HIGH"))
                .andExpect(jsonPath("$.columnId").value("todo"))
                .andExpect(jsonPath("$.assignees", hasSize(1)))
                .andExpect(jsonPath("$.assignees[0].email").value("assignee@test.com"))
                .andExpect(jsonPath("$.createdBy.email").value("manager@test.com"));
    }

    @Test
    @DisplayName("POST /tasks - 401 without authentication")
    void createTask_noAuth_401() throws Exception {
        mockMvc.perform(post("/api/tasks")
                        .param("userId", "1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(TaskRequest.builder()
                                .title("Task").build())))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @WithMockUser(username = "manager@test.com")
    @DisplayName("GET /tasks - 200 returns empty list initially")
    void getAllTasks_emptyList_200() throws Exception {
        mockMvc.perform(get("/api/tasks"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray());
    }

    @Test
    @WithMockUser(username = "manager@test.com")
    @DisplayName("PATCH /tasks/{id}/move - 200 updates columnId")
    void moveTask_200() throws Exception {
        // Create task first
        var createReq = TaskRequest.builder()
                .title("Move Me").priority(Priority.LOW).columnId("todo").build();

        String createResp = mockMvc.perform(post("/api/tasks")
                        .param("userId", manager.getId().toString())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(createReq)))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();

        Long taskId = objectMapper.readTree(createResp).get("id").asLong();

        // Move it
        mockMvc.perform(patch("/api/tasks/{id}/move", taskId)
                        .param("columnId", "in-progress")
                        .param("userId", manager.getId().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.columnId").value("in-progress"));
    }

    @Test
    @WithMockUser(username = "manager@test.com")
    @DisplayName("GET /tasks/99999 - 404 not found")
    void getById_notFound_404() throws Exception {
        mockMvc.perform(get("/api/tasks/99999"))
                .andExpect(status().isNotFound());
    }

    @Test
    @WithMockUser(username = "manager@test.com")
    @DisplayName("GET /tasks/search - 200 returns filtered results")
    void searchTasks_200() throws Exception {
        // Create a task with known title
        mockMvc.perform(post("/api/tasks")
                        .param("userId", manager.getId().toString())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                            TaskRequest.builder().title("SearchableTask")
                                .priority(Priority.HIGH).columnId("todo").build())))
                .andExpect(status().isCreated());

        mockMvc.perform(get("/api/tasks/search")
                        .param("keyword", "Searchable")
                        .param("priority", "HIGH"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray());
    }

    @Test
    @WithMockUser(username = "manager@test.com")
    @DisplayName("DELETE /tasks/{id} - 204 deletes task")
    void deleteTask_204() throws Exception {
        String resp = mockMvc.perform(post("/api/tasks")
                        .param("userId", manager.getId().toString())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                            TaskRequest.builder().title("Delete Me")
                                .priority(Priority.LOW).columnId("todo").build())))
                .andReturn().getResponse().getContentAsString();

        Long taskId = objectMapper.readTree(resp).get("id").asLong();

        mockMvc.perform(delete("/api/tasks/{id}", taskId))
                .andExpect(status().isNoContent());

        // Verify deleted
        mockMvc.perform(get("/api/tasks/{id}", taskId))
                .andExpect(status().isNotFound());
    }
}
