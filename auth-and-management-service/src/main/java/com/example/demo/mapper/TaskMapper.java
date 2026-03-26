package com.example.demo.mapper;

import com.example.demo.dto.task.TaskResponse;
import com.example.demo.model.Task;
import com.example.demo.model.TaskScore;
import com.example.demo.repository.TaskScoreRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.Optional;

@Component
@RequiredArgsConstructor
public class TaskMapper implements EntityMapper<Task, TaskResponse> {

    private final TaskScoreRepository taskScoreRepo;

    @Override
    public TaskResponse toResponse(Task task) {
        return TaskResponse.builder()
                .id(task.getId())
                .title(task.getTitle())
                .description(task.getDescription())
                .priority(task.getPriority())
                .columnId(task.getColumnId())
                .startDate(task.getStartDate())
                .endDate(task.getEndDate())
                .createdAt(task.getCreatedAt())
                .updatedAt(task.getUpdatedAt())
                .event(mapEvent(task))
                .createdBy(mapUser(task.getCreatedBy()))
                .updatedBy(mapUser(task.getUpdatedBy()))
                .assignees(mapAssignees(task))
                .links(mapLinks(task))
                .build();
    }

    private TaskResponse.EventInfo mapEvent(Task task) {
        return Optional.ofNullable(task.getEvent())
                .map(e -> TaskResponse.EventInfo.builder()
                        .id(e.getId())
                        .title(e.getTitle())
                        .build())
                .orElse(null);
    }

    private TaskResponse.UserInfo mapUser(com.example.demo.model.User user) {
        return Optional.ofNullable(user)
                .map(u -> TaskResponse.UserInfo.builder()
                        .id(u.getId())
                        .name(u.getName())
                        .email(u.getEmail())
                        .build())
                .orElse(null);
    }

    private java.util.List<TaskResponse.AssigneeInfo> mapAssignees(Task task) {
        return task.getAssignees().stream()
                .map(ut -> {
                    var u = ut.getUser();
                    var scoreOpt = taskScoreRepo.findByTaskIdAndUserId(task.getId(), u.getId());
                    return TaskResponse.AssigneeInfo.builder()
                            .id(u.getId())
                            .name(u.getName())
                            .email(u.getEmail())
                            .code(u.getCode())
                            .team(u.getTeam().name())
                            .type(u.getType().name())
                            .score(scoreOpt.map(TaskScore::getScore).orElse(null))
                            .applied(scoreOpt.map(TaskScore::getApplied).orElse(null))
                            .appliedAt(scoreOpt.map(TaskScore::getAppliedAt).orElse(null))
                            .build();
                })
                .toList();
    }

    private java.util.List<TaskResponse.TaskLinkInfo> mapLinks(Task task) {
        return task.getLinks().stream()
                .map(l -> TaskResponse.TaskLinkInfo.builder()
                        .id(l.getId())
                        .url(l.getUrl())
                        .title(l.getTitle())
                        .build())
                .toList();
    }
}