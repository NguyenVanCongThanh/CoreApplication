package com.example.demo.integration.repository;

import com.example.demo.enums.*;
import com.example.demo.model.*;
import com.example.demo.repository.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
@DisplayName("TaskScoreRepository Tests")
class TaskScoreRepositoryTest {

    @Autowired TaskScoreRepository taskScoreRepo;
    @Autowired TaskRepository      taskRepo;
    @Autowired UserRepository      userRepo;
    @Autowired EventRepository     eventRepo;

    private User admin, user1, user2;
    private Task task;

    @BeforeEach
    void setUp() {
        admin = persistUser("admin@test.com", "ADM001", UserRole.ROLE_ADMIN);
        user1 = persistUser("user1@test.com", "USR001", UserRole.ROLE_USER);
        user2 = persistUser("user2@test.com", "USR002", UserRole.ROLE_USER);
        task  = persistTask();
    }

    @Test
    @DisplayName("findByTaskIdAndUserId - returns score for specific task+user pair")
    void findByTaskIdAndUserId_success() {

        var found = taskScoreRepo.findByTaskIdAndUserId(task.getId(), user1.getId());

        assertThat(found).isPresent();
        assertThat(found.get().getScore()).isEqualTo(100);
    }

    @Test
    @DisplayName("findByTaskIdAndUserId - empty when no score exists")
    void findByTaskIdAndUserId_notFound() {
        assertThat(taskScoreRepo.findByTaskIdAndUserId(task.getId(), user1.getId()))
            .isEmpty();
    }

    @Test
    @DisplayName("findByTaskId - returns all scores for a task")
    void findByTaskId_returnsAll() {
        persistScore(task, user1, 100, false);
        persistScore(task, user2, 80, false);

        assertThat(taskScoreRepo.findByTaskId(task.getId())).hasSize(2);
    }

    @Test
    @DisplayName("findByUserId - returns all scores for a user across tasks")
    void findByUserId_returnsAll() {
        var task2 = persistTask("Second Task");
        persistScore(task,  user1, 100, true);
        persistScore(task2, user1, 50,  false);

        assertThat(taskScoreRepo.findByUserId(user1.getId())).hasSize(2);
    }

    @Test
    @DisplayName("findByTaskIdAndAppliedFalse - returns only unapplied scores")
    void findByTaskIdAndAppliedFalse_filtersCorrectly() {
        persistScore(task, user1, 100, true);  // applied
        persistScore(task, user2, 80, false);  // not applied

        var unapplied = taskScoreRepo.findByTaskIdAndAppliedFalse(task.getId());

        assertThat(unapplied).hasSize(1);
        assertThat(unapplied.get(0).getUser().getId()).isEqualTo(user2.getId());
    }

    @Test
    @DisplayName("getTotalAppliedScoreForUser - sums only applied scores")
    void getTotalAppliedScore_sumsAppliedOnly() {
        var task2 = persistTask("Task 2");
        persistScore(task,  user1, 100, true);  // applied → counted
        persistScore(task2, user1, 50,  false); // not applied → ignored

        Integer total = taskScoreRepo.getTotalAppliedScoreForUser(user1.getId());

        assertThat(total).isEqualTo(100);
    }

    @Test
    @DisplayName("getTotalAppliedScoreForUser - returns null when no applied scores")
    void getTotalAppliedScore_nullWhenNone() {
        assertThat(taskScoreRepo.getTotalAppliedScoreForUser(user1.getId())).isNull();
    }

    @Test
    @DisplayName("findByTaskIdWithDetails - fetches user, task, scoredBy eagerly")
    void findByTaskIdWithDetails_eagerLoads() {
        persistScore(task, user1, 100, false);

        var scores = taskScoreRepo.findByTaskIdWithDetails(task.getId());

        assertThat(scores).hasSize(1);
        // Accessing related entities should not throw LazyInitializationException
        assertThatCode(() -> {
            scores.get(0).getUser().getEmail();
            scores.get(0).getTask().getTitle();
            scores.get(0).getScoredBy().getName();
        }).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("findByTaskIdIn - batch loads scores for multiple tasks")
    void findByTaskIdIn_batchLoad() {
        var task2 = persistTask("Task 2");
        persistScore(task,  user1, 100, false);
        persistScore(task2, user2, 80,  true);

        var allScores = taskScoreRepo.findByTaskIdIn(List.of(task.getId(), task2.getId()));

        assertThat(allScores).hasSize(2);
    }

    @Test
    @DisplayName("findAndGroupByTaskIds - groups scores correctly by taskId")
    void findAndGroupByTaskIds_groupsCorrectly() {
        var task2 = persistTask("Task 2");
        persistScore(task,  user1, 100, false);
        persistScore(task,  user2, 90,  false);
        persistScore(task2, user1, 80,  true);

        Map<Long, List<TaskScore>> grouped =
            taskScoreRepo.findAndGroupByTaskIds(List.of(task.getId(), task2.getId()));

        assertThat(grouped).containsKeys(task.getId(), task2.getId());
        assertThat(grouped.get(task.getId())).hasSize(2);
        assertThat(grouped.get(task2.getId())).hasSize(1);
    }

    @Test
    @DisplayName("existsByTaskIdAndUserId - true when exists, false otherwise")
    void existsByTaskIdAndUserId_correctBoolean() {
        persistScore(task, user1, 100, false);

        assertThat(taskScoreRepo.existsByTaskIdAndUserId(task.getId(), user1.getId())).isTrue();
        assertThat(taskScoreRepo.existsByTaskIdAndUserId(task.getId(), user2.getId())).isFalse();
    }

    @Test
    @DisplayName("uniqueConstraint - cannot persist two scores for same task+user")
    void uniqueConstraint_taskUserCombo() {
        persistScore(task, user1, 100, false);

        assertThatThrownBy(() -> {
            persistScore(task, user1, 200, false); // duplicate
            taskScoreRepo.flush();
        }).isInstanceOf(Exception.class); // DataIntegrityViolationException
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private User persistUser(String email, String code, UserRole role) {
        return userRepo.save(User.builder()
                .name("User " + code).email(email).password("encoded")
                .role(role).team(UserTeam.RESEARCH).code(code).type(UserType.DT)
                .active(true).totalScore(0).build());
    }

    private Task persistTask() { return persistTask("Default Task"); }

    private Task persistTask(String title) {
        return taskRepo.save(Task.builder()
                .title(title).description("Desc").priority(Priority.HIGH)
                .columnId("todo").createdBy(admin).createdAt(LocalDateTime.now())
                .build());
    }

    private TaskScore persistScore(Task t, User u, int score, boolean applied) {
        return taskScoreRepo.save(TaskScore.builder()
                .task(t).user(u).score(score).applied(applied)
                .scoredBy(admin).scoredAt(LocalDateTime.now())
                .appliedAt(applied ? LocalDateTime.now() : null)
                .build());
    }
}
