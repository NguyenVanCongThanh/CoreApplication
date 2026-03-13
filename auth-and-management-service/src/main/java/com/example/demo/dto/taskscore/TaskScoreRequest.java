package com.example.demo.dto.taskscore;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TaskScoreRequest {
    private Long taskId;
    private Long userId;
    private Integer score;
    private String notes;
}
