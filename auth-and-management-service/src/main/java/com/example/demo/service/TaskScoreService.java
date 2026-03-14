package com.example.demo.service;

import com.example.demo.dto.taskscore.TaskScoreRequest;
import com.example.demo.dto.taskscore.TaskScoreResponse;
import com.example.demo.enums.UserRole;
import com.example.demo.model.Task;
import com.example.demo.model.TaskScore;
import com.example.demo.model.User;
import com.example.demo.repository.TaskRepository;
import com.example.demo.repository.TaskScoreRepository;
import com.example.demo.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class TaskScoreService {
    private final TaskScoreRepository taskScoreRepo;
    private final TaskRepository taskRepo;
    private final UserRepository userRepo;

    /**
     * Lấy điểm của một user cho một task
     */
    @Transactional(readOnly = true)
    public TaskScoreResponse getScore(Long taskId, Long userId) {
        TaskScore score = taskScoreRepo.findByTaskIdAndUserId(taskId, userId)
                .orElseThrow(() -> new RuntimeException("Score not found for task " + taskId + " and user " + userId));
        return mapToResponse(score);
    }

    /**
     * Lấy tất cả điểm của một task
     */
    @Transactional(readOnly = true)
    public List<TaskScoreResponse> getTaskScores(Long taskId) {
        taskRepo.findById(taskId)
                .orElseThrow(() -> new RuntimeException("Task not found"));
        
        List<TaskScore> scores = taskScoreRepo.findByTaskIdWithDetails(taskId);
        return scores.stream()
                .map(this::mapToResponse)
                .collect(Collectors.toList());
    }

    /**
     * Lấy tất cả điểm của một user
     */
    @Transactional(readOnly = true)
    public List<TaskScoreResponse> getUserScores(Long userId) {
        List<TaskScore> scores = taskScoreRepo.findByUserId(userId);
        return scores.stream()
                .map(this::mapToResponse)
                .collect(Collectors.toList());
    }

    /**
     * Thêm/cập nhật điểm cho một user trong một task
     * Chỉ ADMIN hoặc MANAGER có thể thực hiện
     */
    @Transactional
    public TaskScoreResponse setScore(TaskScoreRequest request, Long adminUserId) {
        // Validate permission
        validateAdminOrManagerPermission(adminUserId);

        Task task = taskRepo.findById(request.getTaskId())
                .orElseThrow(() -> new RuntimeException("Task not found"));
        
        User user = userRepo.findById(request.getUserId())
                .orElseThrow(() -> new RuntimeException("User not found"));
        
        User admin = userRepo.findById(adminUserId)
                .orElseThrow(() -> new RuntimeException("Admin user not found"));

        TaskScore score = taskScoreRepo.findByTaskIdAndUserId(request.getTaskId(), request.getUserId())
                .orElse(TaskScore.builder()
                        .task(task)
                        .user(user)
                        .build());

        // Nếu score đã applied, cần recalculate totalScore
        Integer oldScore = score.getScore() != null ? score.getScore() : 0;
        if (score.getApplied() != null && score.getApplied()) {
            // Lấy lại totalScore từ DB để chắc chắn có giá trị mới nhất
            user = userRepo.findById(request.getUserId()).orElseThrow();
            // Trừ điểm cũ, cộng điểm mới
            Integer newTotalScore = (user.getTotalScore() != null ? user.getTotalScore() : 0) - oldScore + request.getScore();
            user.setTotalScore(newTotalScore);
            userRepo.save(user);
        }

        score.setScore(request.getScore());
        score.setScoredBy(admin);
        score.setScoredAt(LocalDateTime.now());
        score.setNotes(request.getNotes());

        score = taskScoreRepo.save(score);
        log.info("Set score {} for user {} on task {}", request.getScore(), user.getId(), task.getId());
        
        return mapToResponse(score);
    }

    /**
     * Trừ điểm cho một user trong một task
     * Chỉ ADMIN hoặc MANAGER có thể thực hiện
     */
    @Transactional
    public TaskScoreResponse deductScore(Long taskId, Long userId, Integer deductAmount, String reason, Long adminUserId) {
        validateAdminOrManagerPermission(adminUserId);

        Task task = taskRepo.findById(taskId)
                .orElseThrow(() -> new RuntimeException("Task not found"));
        
        User user = userRepo.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));
        
        User admin = userRepo.findById(adminUserId)
                .orElseThrow(() -> new RuntimeException("Admin user not found"));

        TaskScore score = taskScoreRepo.findByTaskIdAndUserId(taskId, userId)
                .orElseThrow(() -> new RuntimeException("Score record not found"));

        Integer oldScore = score.getScore();
        Integer newScore = Math.max(0, oldScore - deductAmount); // Không cho điểm âm
        
        // Nếu score đã applied, cần update totalScore
        if (score.getApplied() != null && score.getApplied()) {
            // Lấy lại totalScore từ DB để chắc chắn có giá trị mới nhất
            user = userRepo.findById(userId).orElseThrow();
            // Tính toán delta: newScore - oldScore (âm vì đang trừ)
            int delta = newScore - oldScore;
            Integer newTotalScore = (user.getTotalScore() != null ? user.getTotalScore() : 0) + delta;
            user.setTotalScore(newTotalScore);
            userRepo.save(user);
        }
        
        score.setScore(newScore);
        score.setScoredBy(admin);
        score.setScoredAt(LocalDateTime.now());
        score.setNotes("Deducted: " + reason);

        score = taskScoreRepo.save(score);
        log.info("Deducted {} points from user {} on task {}", deductAmount, user.getId(), task.getId());
        
        return mapToResponse(score);
    }

    /**
     * Cộng điểm cho tất cả assignees của một task khi task được hoàn thành
     * Chỉ ADMIN hoặc MANAGER có thể thực hiện
     */
    @Transactional
    public List<TaskScoreResponse> applyScoresToTask(Long taskId, Long adminUserId) {
        validateAdminOrManagerPermission(adminUserId);

        taskRepo.findById(taskId)
                .orElseThrow(() -> new RuntimeException("Task not found"));

        // Lấy tất cả scores chưa được cộng cho task này
        List<TaskScore> scores = taskScoreRepo.findByTaskIdAndAppliedFalse(taskId);

        LocalDateTime now = LocalDateTime.now();
        for (TaskScore score : scores) {
            if (score.getScore() > 0) {
                // Cộng điểm vào totalScore của user
                User user = score.getUser();
                user.setTotalScore((user.getTotalScore() != null ? user.getTotalScore() : 0) + score.getScore());
                userRepo.save(user);

                // Đánh dấu score đã được cộng
                score.setApplied(true);
                score.setAppliedAt(now);
                taskScoreRepo.save(score);
                
                log.info("Applied score {} to user {}", score.getScore(), user.getId());
            }
        }

        // Trả về danh sách scores sau khi cộng
        List<TaskScore> updatedScores = taskScoreRepo.findByTaskId(taskId);
        return updatedScores.stream()
                .map(this::mapToResponse)
                .collect(Collectors.toList());
    }

    /**
     * Áp dụng/huỷ áp dụng điểm cho một user cụ thể trên một task
     */
    @Transactional
    public TaskScoreResponse toggleApplyScore(Long taskId, Long userId, Boolean applied, Long adminUserId) {
        validateAdminOrManagerPermission(adminUserId);

        TaskScore score = taskScoreRepo.findByTaskIdAndUserId(taskId, userId)
                .orElseThrow(() -> new RuntimeException("Score not found"));

        if (applied && !score.getApplied()) {
            // Áp dụng điểm
            User user = score.getUser();
            user.setTotalScore((user.getTotalScore() != null ? user.getTotalScore() : 0) + score.getScore());
            userRepo.save(user);
            
            score.setApplied(true);
            score.setAppliedAt(LocalDateTime.now());
        } else if (!applied && score.getApplied()) {
            // Huỷ áp dụng điểm
            User user = score.getUser();
            user.setTotalScore((user.getTotalScore() != null ? user.getTotalScore() : 0) - score.getScore());
            userRepo.save(user);
            
            score.setApplied(false);
            score.setAppliedAt(null);
        }

        score = taskScoreRepo.save(score);
        return mapToResponse(score);
    }

    /**
     * Xoá điểm của một user trong một task
     */
    @Transactional
    public void deleteScore(Long taskId, Long userId, Long adminUserId) {
        validateAdminOrManagerPermission(adminUserId);

        TaskScore score = taskScoreRepo.findByTaskIdAndUserId(taskId, userId)
                .orElseThrow(() -> new RuntimeException("Score not found"));

        // Nếu điểm đã được cộng, cần trừ lại từ totalScore
        if (score.getApplied() && score.getScore() > 0) {
            User user = score.getUser();
            user.setTotalScore((user.getTotalScore() != null ? user.getTotalScore() : 0) - score.getScore());
            userRepo.save(user);
        }

        taskScoreRepo.delete(score);
        log.info("Deleted score record for user {} on task {}", userId, taskId);
    }

    /**
     * Khởi tạo điểm cho tất cả assignees của một task
     * Chỉ ADMIN hoặc MANAGER có thể thực hiện
     */
    @Transactional
    public List<TaskScoreResponse> initializeScoresForTask(Long taskId, Integer initialScore, Long adminUserId) {
        validateAdminOrManagerPermission(adminUserId);

        Task task = taskRepo.findById(taskId)
                .orElseThrow(() -> new RuntimeException("Task not found"));

        User admin = userRepo.findById(adminUserId)
                .orElseThrow(() -> new RuntimeException("Admin user not found"));

        // Tạo score record cho mỗi assignee nếu chưa tồn tại
        task.getAssignees().forEach(userTask -> {
            if (!taskScoreRepo.existsByTaskIdAndUserId(taskId, userTask.getUser().getId())) {
                TaskScore score = TaskScore.builder()
                        .task(task)
                        .user(userTask.getUser())
                        .score(initialScore)
                        .scoredBy(admin)
                        .scoredAt(LocalDateTime.now())
                        .applied(false)
                        .build();
                taskScoreRepo.save(score);
            }
        });

        List<TaskScore> scores = taskScoreRepo.findByTaskId(taskId);
        return scores.stream()
                .map(this::mapToResponse)
                .collect(Collectors.toList());
    }

    /**
     * Áp dụng điểm cho tất cả assignees của một task sau khi hoàn thành
     * Chỉ ADMIN hoặc MANAGER có thể thực hiện
     */
    @Transactional
    public List<TaskScoreResponse> completeTaskAndApplyScores(Long taskId, Long adminUserId) {
        validateAdminOrManagerPermission(adminUserId);

        Task task = taskRepo.findById(taskId)
                .orElseThrow(() -> new RuntimeException("Task not found"));

        // Chuyển task sang column "done"
        task.setColumnId("done");
        taskRepo.save(task);

        // Áp dụng điểm cho tất cả assignees
        return applyScoresToTask(taskId, adminUserId);
    }

    /**
     * Lấy tổng điểm đã áp dụng của một user
     */
    @Transactional(readOnly = true)
    public Integer getTotalAppliedScore(Long userId) {
        Integer total = taskScoreRepo.getTotalAppliedScoreForUser(userId);
        return total != null ? total : 0;
    }

    /**
     * Validate rằng người dùng là ADMIN hoặc MANAGER
     */
    private void validateAdminOrManagerPermission(Long userId) {
        User user = userRepo.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

        if (user.getRole() != UserRole.ROLE_ADMIN && user.getRole() != UserRole.ROLE_MANAGER) {
            throw new RuntimeException("Only ADMIN or MANAGER can manage task scores");
        }
    }

    /**
     * Map TaskScore entity to TaskScoreResponse DTO
     */
    private TaskScoreResponse mapToResponse(TaskScore score) {
        return TaskScoreResponse.builder()
                .id(score.getId())
                .taskId(score.getTask().getId())
                .taskTitle(score.getTask().getTitle())
                .userId(score.getUser().getId())
                .userName(score.getUser().getName())
                .userEmail(score.getUser().getEmail())
                .userCode(score.getUser().getCode())
                .score(score.getScore())
                .applied(score.getApplied())
                .scoredById(score.getScoredBy() != null ? score.getScoredBy().getId() : null)
                .scoredByName(score.getScoredBy() != null ? score.getScoredBy().getName() : null)
                .scoredAt(score.getScoredAt())
                .appliedAt(score.getAppliedAt())
                .notes(score.getNotes())
                .build();
    }
}
