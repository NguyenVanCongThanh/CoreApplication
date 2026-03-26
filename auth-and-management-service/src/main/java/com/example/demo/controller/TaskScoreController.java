package com.example.demo.controller;

import com.example.demo.dto.taskscore.TaskScoreRequest;
import com.example.demo.dto.taskscore.TaskScoreResponse;
import com.example.demo.service.TaskScoreService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
 
import java.util.List;
 
@RestController
@RequestMapping("/api/task-scores")
@RequiredArgsConstructor
class TaskScoreController {
 
    private final TaskScoreService taskScoreService;
 
    @GetMapping("/{taskId}/{userId}")
    public ResponseEntity<TaskScoreResponse> getScore(@PathVariable Long taskId,
                                                      @PathVariable Long userId) {
        return ResponseEntity.ok(taskScoreService.getScore(taskId, userId));
    }
 
    @GetMapping("/task/{taskId}")
    public ResponseEntity<List<TaskScoreResponse>> getByTask(@PathVariable Long taskId) {
        return ResponseEntity.ok(taskScoreService.getTaskScores(taskId));
    }
 
    @GetMapping("/user/{userId}")
    public ResponseEntity<List<TaskScoreResponse>> getByUser(@PathVariable Long userId) {
        return ResponseEntity.ok(taskScoreService.getUserScores(userId));
    }
 
    @GetMapping("/user/{userId}/total")
    public ResponseEntity<java.util.Map<String, Integer>> getTotal(@PathVariable Long userId) {
        return ResponseEntity.ok(java.util.Map.of("totalScore", taskScoreService.getTotalAppliedScore(userId)));
    }
 
    @PostMapping("/set")
    public ResponseEntity<TaskScoreResponse> setScore(@RequestBody TaskScoreRequest req,
                                                      @RequestParam Long adminUserId) {
        return ResponseEntity.status(HttpStatus.CREATED).body(taskScoreService.setScore(req, adminUserId));
    }
 
    @PatchMapping("/{taskId}/{userId}/deduct")
    public ResponseEntity<TaskScoreResponse> deduct(@PathVariable Long taskId,
                                                    @PathVariable Long userId,
                                                    @RequestParam int deductAmount,
                                                    @RequestParam(defaultValue = "Manual deduction") String reason,
                                                    @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.deductScore(taskId, userId, deductAmount, reason, adminUserId));
    }
 
    @PostMapping("/{taskId}/apply")
    public ResponseEntity<List<TaskScoreResponse>> apply(@PathVariable Long taskId,
                                                         @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.applyScoresToTask(taskId, adminUserId));
    }
 
    @PatchMapping("/{taskId}/{userId}/toggle")
    public ResponseEntity<TaskScoreResponse> toggle(@PathVariable Long taskId,
                                                    @PathVariable Long userId,
                                                    @RequestParam boolean applied,
                                                    @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.toggleApplyScore(taskId, userId, applied, adminUserId));
    }
 
    @DeleteMapping("/{taskId}/{userId}")
    public ResponseEntity<java.util.Map<String, String>> deleteScore(@PathVariable Long taskId,
                                                                     @PathVariable Long userId,
                                                                     @RequestParam Long adminUserId) {
        taskScoreService.deleteScore(taskId, userId, adminUserId);
        return ResponseEntity.ok(java.util.Map.of("message", "Score deleted successfully"));
    }
 
    @PostMapping("/{taskId}/initialize")
    public ResponseEntity<List<TaskScoreResponse>> initialize(@PathVariable Long taskId,
                                                              @RequestParam int initialScore,
                                                              @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.initializeScoresForTask(taskId, initialScore, adminUserId));
    }
 
    @PostMapping("/{taskId}/complete")
    public ResponseEntity<List<TaskScoreResponse>> complete(@PathVariable Long taskId,
                                                            @RequestParam Long adminUserId) {
        return ResponseEntity.ok(taskScoreService.completeTaskAndApplyScores(taskId, adminUserId));
    }
}