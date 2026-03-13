package com.example.demo.dto.taskscore;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TaskScoreResponse {
    private Long id;
    private Long taskId;
    private String taskTitle;
    private Long userId;
    private String userName;
    private String userEmail;
    private String userCode;
    private Integer score;
    private Boolean applied;
    private Long scoredById;
    private String scoredByName;
    
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime scoredAt;
    
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime appliedAt;
    
    private String notes;
}
