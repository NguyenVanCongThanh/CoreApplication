package com.example.demo.controller;

import com.example.demo.dto.taskscore.TaskScoreRequest;
import com.example.demo.dto.taskscore.TaskScoreResponse;
import com.example.demo.service.TaskScoreService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/task-scores")
@RequiredArgsConstructor
public class TaskScoreController {
    private final TaskScoreService taskScoreService;

    /**
     * GET /api/task-scores/{taskId}/{userId}
     * Lấy điểm của một user cho một task
     */
    @GetMapping("/{taskId}/{userId}")
    public ResponseEntity<TaskScoreResponse> getScore(
            @PathVariable Long taskId,
            @PathVariable Long userId) {
        return ResponseEntity.ok(taskScoreService.getScore(taskId, userId));
    }

    /**
     * GET /api/task-scores/task/{taskId}
     * Lấy tất cả điểm của một task
     */
    @GetMapping("/task/{taskId}")
    public ResponseEntity<List<TaskScoreResponse>> getTaskScores(
            @PathVariable Long taskId) {
        return ResponseEntity.ok(taskScoreService.getTaskScores(taskId));
    }

    /**
     * GET /api/task-scores/user/{userId}
     * Lấy tất cả điểm của một user
     */
    @GetMapping("/user/{userId}")
    public ResponseEntity<List<TaskScoreResponse>> getUserScores(
            @PathVariable Long userId) {
        return ResponseEntity.ok(taskScoreService.getUserScores(userId));
    }

    /**
     * GET /api/task-scores/user/{userId}/total
     * Lấy tổng điểm đã áp dụng của một user
     */
    @GetMapping("/user/{userId}/total")
    public ResponseEntity<Map<String, Integer>> getTotalScore(
            @PathVariable Long userId) {
        Integer total = taskScoreService.getTotalAppliedScore(userId);
        return ResponseEntity.ok(Map.of("totalScore", total));
    }

    /**
     * POST /api/task-scores/set
     * Thêm/cập nhật điểm cho một user trong một task
     * Yêu cầu: adminUserId trong query parameter
     */
    @PostMapping("/set")
    public ResponseEntity<TaskScoreResponse> setScore(
            @RequestBody TaskScoreRequest request,
            @RequestParam Long adminUserId) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(taskScoreService.setScore(request, adminUserId));
    }

    /**
     * PATCH /api/task-scores/{taskId}/{userId}/deduct
     * Trừ điểm cho một user trong một task
     * Query parameters: deductAmount, reason, adminUserId
     */
    @PatchMapping("/{taskId}/{userId}/deduct")
    public ResponseEntity<TaskScoreResponse> deductScore(
            @PathVariable Long taskId,
            @PathVariable Long userId,
            @RequestParam Integer deductAmount,
            @RequestParam(required = false, defaultValue = "Manual deduction") String reason,
            @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.deductScore(taskId, userId, deductAmount, reason, adminUserId));
    }

    /**
     * POST /api/task-scores/{taskId}/apply
     * Cộng điểm cho tất cả assignees của một task
     * Query parameter: adminUserId
     */
    @PostMapping("/{taskId}/apply")
    public ResponseEntity<List<TaskScoreResponse>> applyScoresToTask(
            @PathVariable Long taskId,
            @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.applyScoresToTask(taskId, adminUserId));
    }

    /**
     * PATCH /api/task-scores/{taskId}/{userId}/toggle
     * Áp dụng/huỷ áp dụng điểm cho một user cụ thể trên một task
     * Query parameters: applied, adminUserId
     */
    @PatchMapping("/{taskId}/{userId}/toggle")
    public ResponseEntity<TaskScoreResponse> toggleApplyScore(
            @PathVariable Long taskId,
            @PathVariable Long userId,
            @RequestParam Boolean applied,
            @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.toggleApplyScore(taskId, userId, applied, adminUserId));
    }

    /**
     * DELETE /api/task-scores/{taskId}/{userId}
     * Xoá điểm của một user trong một task
     * Query parameter: adminUserId
     */
    @DeleteMapping("/{taskId}/{userId}")
    public ResponseEntity<Map<String, String>> deleteScore(
            @PathVariable Long taskId,
            @PathVariable Long userId,
            @RequestParam Long adminUserId) {
        taskScoreService.deleteScore(taskId, userId, adminUserId);
        return ResponseEntity.ok(Map.of("message", "Score deleted successfully"));
    }

    /**
     * POST /api/task-scores/{taskId}/initialize
     * Khởi tạo điểm cho tất cả assignees của một task
     * Query parameters: initialScore, adminUserId
     */
    @PostMapping("/{taskId}/initialize")
    public ResponseEntity<List<TaskScoreResponse>> initializeScoresForTask(
            @PathVariable Long taskId,
            @RequestParam Integer initialScore,
            @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.initializeScoresForTask(taskId, initialScore, adminUserId));
    }

    /**
     * POST /api/task-scores/{taskId}/complete
     * Hoàn thành task và cộng điểm cho tất cả assignees
     * Query parameter: adminUserId
     */
    @PostMapping("/{taskId}/complete")
    public ResponseEntity<List<TaskScoreResponse>> completeTaskAndApplyScores(
            @PathVariable Long taskId,
            @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.completeTaskAndApplyScores(taskId, adminUserId));
    }

    /**
     * Exception handler
     */
    @ExceptionHandler({RuntimeException.class})
    public ResponseEntity<Map<String, String>> handleException(RuntimeException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(Map.of("error", ex.getMessage()));
    }
}
