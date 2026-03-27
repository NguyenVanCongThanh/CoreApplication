package com.example.demo.common;

import com.example.demo.dto.announcement.AnnouncementRequest;
import com.example.demo.dto.auth.LoginRequest;
import com.example.demo.dto.auth.RegisterRequest;
import com.example.demo.dto.event.EventRequest;
import com.example.demo.dto.task.TaskRequest;
import com.example.demo.dto.taskscore.TaskScoreRequest;
import com.example.demo.enums.*;
import com.example.demo.model.*;

import java.time.LocalDateTime;
import java.util.List;

public final class TestDataFactory {

    private TestDataFactory() {}

    public static User adminUser() {
        return User.builder()
                .id(1L)
                .name("Admin User")
                .email("admin@test.com")
                .password("$2a$10$encoded_password")
                .role(UserRole.ROLE_ADMIN)
                .team(UserTeam.RESEARCH)
                .code("ADMIN001")
                .type(UserType.DT)
                .active(true)
                .totalScore(1000)
                .build();
    }

    public static User managerUser() {
        return User.builder()
                .id(2L)
                .name("Manager User")
                .email("manager@test.com")
                .password("$2a$10$encoded_password")
                .role(UserRole.ROLE_MANAGER)
                .team(UserTeam.ENGINEER)
                .code("MGR001")
                .type(UserType.TN)
                .active(true)
                .totalScore(500)
                .build();
    }

    public static User regularUser() {
        return User.builder()
                .id(3L)
                .name("Regular User")
                .email("user@test.com")
                .password("$2a$10$encoded_password")
                .role(UserRole.ROLE_USER)
                .team(UserTeam.EVENT)
                .code("USR001")
                .type(UserType.CLC)
                .active(true)
                .totalScore(0)
                .build();
    }

    public static User userWithId(Long id) {
        return regularUser().toBuilder().id(id)
                .email("user" + id + "@test.com")
                .code("USR" + id)
                .build();
    }

    public static Event event() {
        return Event.builder()
                .id(10L)
                .title("Hackathon 2025")
                .description("24-hour coding competition")
                .statusEvent(StatusEvent.PENDING)
                .startTime(LocalDateTime.now().plusDays(10))
                .endTime(LocalDateTime.now().plusDays(11))
                .capacity(100)
                .createdBy(adminUser())
                .createdAt(LocalDateTime.now())
                .build();
    }

    public static EventRequest eventRequest() {
        return EventRequest.builder()
                .title("Hackathon 2025")
                .description("24-hour coding competition")
                .statusEvent(StatusEvent.PENDING)
                .startTime(LocalDateTime.now().plusDays(10))
                .endTime(LocalDateTime.now().plusDays(11))
                .capacity(100)
                .build();
    }

    public static Task task() {
        var t = Task.builder()
                .id(100L)
                .title("Build Feature X")
                .description("Implement feature X")
                .priority(Priority.HIGH)
                .columnId("todo")
                .startDate(LocalDateTime.now())
                .endDate(LocalDateTime.now().plusDays(5))
                .event(event())
                .createdBy(managerUser())
                .createdAt(LocalDateTime.now())
                .build();
        return t;
    }

    public static TaskRequest taskRequest() {
        return TaskRequest.builder()
                .title("Build Feature X")
                .description("Implement feature X")
                .priority(Priority.HIGH)
                .columnId("todo")
                .eventId(10L)
                .assigneeIds(List.of(3L))
                .startDate(LocalDateTime.now())
                .endDate(LocalDateTime.now().plusDays(5))
                .build();
    }

    public static TaskRequest taskRequestWithLinks() {
        return TaskRequest.builder()
                .title("Task with Links")
                .description("Has reference links")
                .priority(Priority.MEDIUM)
                .columnId("in-progress")
                .links(List.of(
                    new TaskRequest.TaskLinkRequest("https://jira.com/TASK-1", "Jira ticket"),
                    new TaskRequest.TaskLinkRequest("https://figma.com/design", "Figma design")
                ))
                .build();
    }

    public static TaskScore taskScore(Task task, User user) {
        return TaskScore.builder()
                .id(1L)
                .task(task)
                .user(user)
                .score(100)
                .applied(false)
                .scoredBy(adminUser())
                .scoredAt(LocalDateTime.now())
                .notes("Good work")
                .build();
    }

    public static TaskScore appliedTaskScore(Task task, User user) {
        return taskScore(task, user).toBuilder()
                .applied(true)
                .appliedAt(LocalDateTime.now())
                .build();
    }

    public static TaskScoreRequest taskScoreRequest(Long taskId, Long userId) {
        return TaskScoreRequest.builder()
                .taskId(taskId)
                .userId(userId)
                .score(150)
                .notes("Excellent contribution")
                .build();
    }

    public static LoginRequest loginRequest(String email, String password) {
        return LoginRequest.builder().email(email).password(password).build();
    }

    public static RegisterRequest registerRequest(String email, String code) {
        return RegisterRequest.builder()
                .name("New Member")
                .email(email)
                .role(UserRole.ROLE_USER)
                .team(UserTeam.RESEARCH)
                .code(code)
                .type(UserType.DT)
                .build();
    }

    public static AnnouncementRequest announcementRequest() {
        return AnnouncementRequest.builder()
                .title("Important Update")
                .content("Please read this announcement carefully.")
                .images(List.of("img1.jpg", "img2.jpg"))
                .status(StatusPermission.APPROVED)
                .build();
    }

    public static Announcement announcement(User creator) {
        return Announcement.builder()
                .id(1L)
                .title("Important Update")
                .content("Please read this announcement carefully.")
                .images(new java.util.ArrayList<>(List.of("img1.jpg")))
                .status(StatusPermission.APPROVED)
                .createdBy(creator)
                .createdAt(LocalDateTime.now())
                .build();
    }

    public static PasswordResetToken validToken(User user) {
        return PasswordResetToken.builder()
                .id(1L)
                .token("valid-reset-token-uuid")
                .user(user)
                .expiryDate(LocalDateTime.now().plusMinutes(10))
                .createdAt(LocalDateTime.now())
                .used(false)
                .build();
    }

    public static PasswordResetToken expiredToken(User user) {
        return PasswordResetToken.builder()
                .id(2L)
                .token("expired-token")
                .user(user)
                .expiryDate(LocalDateTime.now().minusMinutes(5))
                .createdAt(LocalDateTime.now().minusMinutes(20))
                .used(false)
                .build();
    }

    public static PasswordResetToken usedToken(User user) {
        return PasswordResetToken.builder()
                .id(3L)
                .token("used-token")
                .user(user)
                .expiryDate(LocalDateTime.now().plusMinutes(10))
                .createdAt(LocalDateTime.now())
                .used(true)
                .build();
    }
}