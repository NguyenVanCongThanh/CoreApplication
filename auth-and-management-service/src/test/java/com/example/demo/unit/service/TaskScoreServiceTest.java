package com.example.demo.unit.service;

import com.example.demo.common.TestDataFactory;
import com.example.demo.dto.taskscore.TaskScoreResponse;
import com.example.demo.exception.ForbiddenException;
import com.example.demo.model.*;
import com.example.demo.repository.*;
import com.example.demo.service.task.TaskScoreService;

import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("TaskScoreService Tests")
class TaskScoreServiceTest {

    @Mock TaskScoreRepository taskScoreRepo;
    @Mock TaskRepository      taskRepo;
    @Mock UserRepository      userRepo;

    @InjectMocks TaskScoreService taskScoreService;

    private User    admin;
    private User    manager;
    private User    regularUser;
    private Task    task;
    private TaskScore score;
    private TaskScore appliedScore;

    @BeforeEach
    void setUp() {
        admin       = TestDataFactory.adminUser();
        manager     = TestDataFactory.managerUser();
        regularUser = TestDataFactory.regularUser();
        task        = TestDataFactory.task();
        task.setAssignees(new ArrayList<>());
        score       = TestDataFactory.taskScore(task, regularUser);
        appliedScore= TestDataFactory.appliedTaskScore(task, regularUser);
    }

    @Test
    @DisplayName("setScore - regular user (non-admin/manager) throws ForbiddenException")
    void setScore_regularUser_throwsForbidden() {
        given(userRepo.findById(regularUser.getId())).willReturn(Optional.of(regularUser));

        assertThatThrownBy(() ->
            taskScoreService.setScore(TestDataFactory.taskScoreRequest(task.getId(), admin.getId()),
                                      regularUser.getId()))
            .isInstanceOf(ForbiddenException.class)
            .hasMessageContaining("ADMIN or MANAGER");
    }

    @Test
    @DisplayName("setScore - manager user is allowed")
    void setScore_manager_allowed() {
        var req = TestDataFactory.taskScoreRequest(task.getId(), regularUser.getId());

        given(userRepo.findById(manager.getId())).willReturn(Optional.of(manager));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(userRepo.findById(regularUser.getId())).willReturn(Optional.of(regularUser));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.empty()); // new score
        given(taskScoreRepo.save(any(TaskScore.class))).willReturn(score);

        TaskScoreResponse resp = taskScoreService.setScore(req, manager.getId());

        assertThat(resp).isNotNull();
        then(taskScoreRepo).should().save(any(TaskScore.class));
    }

    @Test
    @DisplayName("setScore - creates new score when none exists")
    void setScore_createsNew() {
        var req = TestDataFactory.taskScoreRequest(task.getId(), regularUser.getId());

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(userRepo.findById(regularUser.getId())).willReturn(Optional.of(regularUser));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.empty());
        given(taskScoreRepo.save(any())).willReturn(score);

        taskScoreService.setScore(req, admin.getId());

        then(taskScoreRepo).should().save(argThat(s ->
            s.getScore() == 150 &&
            s.getNotes().equals("Excellent contribution") &&
            s.getScoredBy().equals(admin)
        ));
    }

    @Test
    @DisplayName("setScore - updates existing unapplied score without touching totalScore")
    void setScore_updatesExisting_notApplied() {
        var req = TestDataFactory.taskScoreRequest(task.getId(), regularUser.getId());
        score.setApplied(false);
        score.setScore(100);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(userRepo.findById(regularUser.getId())).willReturn(Optional.of(regularUser));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(score));
        given(taskScoreRepo.save(any())).willReturn(score);

        taskScoreService.setScore(req, admin.getId());

        then(userRepo).should(never()).save(any(User.class));
    }

    @Test
    @DisplayName("setScore - updates already-applied score adjusts totalScore by delta")
    void setScore_updatesApplied_adjustsTotalScore() {
        score.setApplied(true);
        score.setScore(100);
        regularUser.setTotalScore(500);

        var req = TestDataFactory.taskScoreRequest(task.getId(), regularUser.getId());
        req.setScore(150);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(userRepo.findById(regularUser.getId())).willReturn(Optional.of(regularUser));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(score));
        given(taskScoreRepo.save(any())).willReturn(score);

        taskScoreService.setScore(req, admin.getId());

        assertThat(regularUser.getTotalScore()).isEqualTo(550);
        then(userRepo).should().save(regularUser);
    }

    @Test
    @DisplayName("deductScore - reduces score, floor at 0")
    void deductScore_floorsAtZero() {
        score.setScore(30);
        score.setApplied(false);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(userRepo.findById(regularUser.getId())).willReturn(Optional.of(regularUser));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(score));
        given(taskScoreRepo.save(any())).willReturn(score);

        taskScoreService.deductScore(task.getId(), regularUser.getId(), 50, "Missed deadline", admin.getId());

        assertThat(score.getScore()).isEqualTo(0);
    }

    @Test
    @DisplayName("deductScore - on applied score adjusts totalScore correctly")
    void deductScore_appliedScore_adjustsTotal() {
        score.setScore(100);
        score.setApplied(true);
        regularUser.setTotalScore(300);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(userRepo.findById(regularUser.getId())).willReturn(Optional.of(regularUser));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(score));
        given(taskScoreRepo.save(any())).willReturn(score);

        taskScoreService.deductScore(task.getId(), regularUser.getId(), 30, "Late submission", admin.getId());

        assertThat(regularUser.getTotalScore()).isEqualTo(270); // 300 - 30
    }

    @Test
    @DisplayName("applyScoresToTask - applies only unapplied scores with score > 0")
    void applyScoresToTask_appliesOnlyPositiveUnapplied() {
        var score1 = TestDataFactory.taskScore(task, regularUser); // score=100, applied=false
        var score2 = TestDataFactory.taskScore(task, TestDataFactory.userWithId(4L));
        score2.setScore(0); // should be skipped

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskRepo.existsById(task.getId())).willReturn(true);
        given(taskScoreRepo.findByTaskIdAndAppliedFalse(task.getId())).willReturn(List.of(score1, score2));
        given(taskScoreRepo.findByTaskId(task.getId())).willReturn(List.of(score1, score2));
        given(taskScoreRepo.save(any())).willAnswer(inv -> inv.getArgument(0));

        taskScoreService.applyScoresToTask(task.getId(), admin.getId());

        assertThat(score1.getApplied()).isTrue();
        assertThat(score1.getAppliedAt()).isNotNull();
        assertThat(score1.getUser().getTotalScore()).isEqualTo(100); // was 0

        assertThat(score2.getApplied()).isFalse();
    }

    @Test
    @DisplayName("toggleApplyScore - apply=true adds to totalScore, sets appliedAt")
    void toggleApplyScore_apply_addsToTotal() {
        score.setApplied(false);
        score.setScore(200);
        regularUser.setTotalScore(100);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(score));
        given(taskScoreRepo.save(any())).willReturn(score);

        taskScoreService.toggleApplyScore(task.getId(), regularUser.getId(), true, admin.getId());

        assertThat(score.getApplied()).isTrue();
        assertThat(score.getAppliedAt()).isNotNull();
        assertThat(regularUser.getTotalScore()).isEqualTo(300); // 100 + 200
    }

    @Test
    @DisplayName("toggleApplyScore - apply=false removes from totalScore, clears appliedAt")
    void toggleApplyScore_unapply_removesFromTotal() {
        appliedScore.setScore(200);
        regularUser.setTotalScore(300);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(appliedScore));
        given(taskScoreRepo.save(any())).willReturn(appliedScore);

        taskScoreService.toggleApplyScore(task.getId(), regularUser.getId(), false, admin.getId());

        assertThat(appliedScore.getApplied()).isFalse();
        assertThat(appliedScore.getAppliedAt()).isNull();
        assertThat(regularUser.getTotalScore()).isEqualTo(100); // 300 - 200
    }

    @Test
    @DisplayName("toggleApplyScore - no-op when already in target state (idempotent)")
    void toggleApplyScore_noOp_whenAlreadyInTargetState() {
        score.setApplied(false);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(score));
        given(taskScoreRepo.save(any())).willReturn(score);

        taskScoreService.toggleApplyScore(task.getId(), regularUser.getId(), false, admin.getId());

        then(userRepo).should(never()).save(any(User.class)); // no score adjustment
    }

    @Test
    @DisplayName("deleteScore - applied score: deducts from totalScore before delete")
    void deleteScore_applied_deductsFirst() {
        appliedScore.setScore(150);
        regularUser.setTotalScore(400);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(appliedScore));

        taskScoreService.deleteScore(task.getId(), regularUser.getId(), admin.getId());

        assertThat(regularUser.getTotalScore()).isEqualTo(250); // 400 - 150
        then(taskScoreRepo).should().delete(appliedScore);
    }

    @Test
    @DisplayName("deleteScore - unapplied score: deletes without touching totalScore")
    void deleteScore_notApplied_noScoreAdjustment() {
        score.setApplied(false);

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskScoreRepo.findByTaskIdAndUserId(task.getId(), regularUser.getId()))
            .willReturn(Optional.of(score));

        taskScoreService.deleteScore(task.getId(), regularUser.getId(), admin.getId());

        then(userRepo).should(never()).save(any(User.class));
        then(taskScoreRepo).should().delete(score);
    }

    @Test
    @DisplayName("initializeScores - creates score only for assignees without existing score")
    void initializeScores_skipsExisting() {
        var ut1 = UserTask.builder().user(regularUser).task(task).build();
        var ut2 = UserTask.builder().user(TestDataFactory.userWithId(5L)).task(task).build();
        task.setAssignees(List.of(ut1, ut2));

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        // user3 already has score, user5 doesn't
        given(taskScoreRepo.existsByTaskIdAndUserId(task.getId(), regularUser.getId())).willReturn(true);
        given(taskScoreRepo.existsByTaskIdAndUserId(task.getId(), 5L)).willReturn(false);
        given(taskScoreRepo.findByTaskId(task.getId())).willReturn(List.of());
        given(taskScoreRepo.save(any())).willAnswer(inv -> inv.getArgument(0));

        taskScoreService.initializeScoresForTask(task.getId(), 100, admin.getId());

        // Only user5 should get a new score record
        then(taskScoreRepo).should(times(1)).save(argThat(s ->
            s.getUser().getId().equals(5L) && s.getScore() == 100
        ));
    }

    @Test
    @DisplayName("getTotalAppliedScore - returns 0 when null from DB")
    void getTotalAppliedScore_nullFromDb_returns0() {
        given(taskScoreRepo.getTotalAppliedScoreForUser(regularUser.getId())).willReturn(null);

        assertThat(taskScoreService.getTotalAppliedScore(regularUser.getId())).isEqualTo(0);
    }

    @Test
    @DisplayName("getTotalAppliedScore - returns actual sum from DB")
    void getTotalAppliedScore_returnsSum() {
        given(taskScoreRepo.getTotalAppliedScoreForUser(regularUser.getId())).willReturn(350);

        assertThat(taskScoreService.getTotalAppliedScore(regularUser.getId())).isEqualTo(350);
    }

    @Test
    @DisplayName("completeTaskAndApplyScores - moves task to 'done' then applies scores")
    void completeTaskAndApplyScores_movesToDone() {
        task.setColumnId("in-progress");

        given(userRepo.findById(admin.getId())).willReturn(Optional.of(admin));
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(taskRepo.save(any())).willReturn(task);
        given(taskRepo.existsById(task.getId())).willReturn(true);
        given(taskScoreRepo.findByTaskIdAndAppliedFalse(task.getId())).willReturn(List.of());
        given(taskScoreRepo.findByTaskId(task.getId())).willReturn(List.of());

        taskScoreService.completeTaskAndApplyScores(task.getId(), admin.getId());

        assertThat(task.getColumnId()).isEqualTo("done");
        then(taskRepo).should().save(argThat(t -> "done".equals(t.getColumnId())));
    }
}
