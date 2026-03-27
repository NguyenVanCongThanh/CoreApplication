package com.example.demo.service;

import com.example.demo.dto.task.TaskRequest;
import com.example.demo.dto.task.TaskResponse;
import com.example.demo.enums.Priority;
import com.example.demo.exception.ResourceNotFoundException;
import com.example.demo.mapper.TaskMapper;
import com.example.demo.model.*;
import com.example.demo.repository.*;
import com.example.demo.utils.SortUtils;
import com.example.demo.utils.TaskSpecifications;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TaskService {

    private final TaskRepository taskRepo;
    private final UserRepository userRepo;
    private final EventRepository eventRepo;
    private final TaskMapper taskMapper;
    private final TaskScoreRepository taskScoreRepo;

    @Transactional
    public TaskResponse createTask(TaskRequest req, Long creatorId) {
        var creator = findUser(creatorId);

        var task = Task.builder()
                .title(req.getTitle())
                .description(req.getDescription())
                .priority(req.getPriority())
                .columnId(req.getColumnId())
                .startDate(req.getStartDate())
                .endDate(req.getEndDate())
                .createdBy(creator)
                .createdAt(LocalDateTime.now())
                .build();

        if (req.getEventId() != null) {
            task.setEvent(findEvent(req.getEventId()));
        }

        task = taskRepo.save(task);
        applyLinks(task, req);
        applyAssignees(task, req);
        task = taskRepo.save(task);

        return taskMapper.toResponse(task);
    }

    @Transactional
    public TaskResponse updateTask(Long taskId, TaskRequest req, Long updaterId) {
        var task    = findTaskById(taskId);
        var updater = findUser(updaterId);

        task.setTitle(req.getTitle());
        task.setDescription(req.getDescription());
        task.setPriority(req.getPriority());
        task.setColumnId(req.getColumnId());
        task.setStartDate(req.getStartDate());
        task.setEndDate(req.getEndDate());
        task.setUpdatedBy(updater);
        task.setUpdatedAt(LocalDateTime.now());
        task.setEvent(req.getEventId() != null ? findEvent(req.getEventId()) : null);

        task.getLinks().clear();
        task.getAssignees().clear();
        applyLinks(task, req);
        applyAssignees(task, req);

        return taskMapper.toResponse(taskRepo.save(task));
    }

    @Transactional
    public TaskResponse moveTask(Long taskId, String columnId, Long userId) {
        var task = findTaskById(taskId);
        task.setColumnId(columnId);
        task.setUpdatedBy(findUser(userId));
        task.setUpdatedAt(LocalDateTime.now());
        return taskMapper.toResponse(taskRepo.save(task));
    }

    @Transactional
    public void deleteTask(Long id) {
        taskRepo.deleteById(id);
    }


    public List<TaskResponse> getAllTasks() {
        return fetchAndMap(taskRepo.findAllWithAssignees());
    }

    public TaskResponse getTaskById(Long id) {
        var task = taskRepo.findByIdWithAssignees(id)
                .orElseThrow(() -> new ResourceNotFoundException("Task", id));
        taskRepo.findByIdWithLinks(id); // hydrate links in persistence context
        return taskMapper.toResponse(task);
    }

    public List<TaskResponse> getTasksByEventId(Long eventId) {
        return fetchAndMap(taskRepo.findByEventIdWithAssignees(eventId));
    }

    public List<TaskResponse> getTasksByColumnId(String columnId) {
        return fetchAndMap(taskRepo.findByColumnIdWithAssignees(columnId));
    }

    public List<TaskResponse> searchTasks(String keyword, String columnId, Priority priority,
                                          Long eventId, LocalDateTime startAfter,
                                          LocalDateTime endBefore, String[] sortParams) {
        Specification<Task> spec = Specification
                .where(TaskSpecifications.containsKeyword(keyword, "title", "description"))
                .and(TaskSpecifications.hasColumnId(columnId))
                .and(TaskSpecifications.hasPriority(priority))
                .and(TaskSpecifications.hasEventId(eventId))
                .and(TaskSpecifications.startAfter(startAfter))
                .and(TaskSpecifications.endBefore(endBefore));

        Sort sort = SortUtils.parseSort(sortParams);
        return taskRepo.findAll(spec, sort).stream()
                .map(taskMapper::toResponse)
                .toList();
    }

    private List<TaskResponse> fetchAndMap(List<Task> tasks) {
        if (tasks.isEmpty()) return List.of();
        taskRepo.findLinksForTasks(tasks);
        
        var taskIds = tasks.stream().map(Task::getId).toList();
        var scoresByTaskAndUser = taskScoreRepo.findByTaskIdIn(taskIds).stream()
                .collect(Collectors.groupingBy(
                    s -> s.getTask().getId(),
                    Collectors.toMap(s -> s.getUser().getId(), s -> s)
                ));
        
        return tasks.stream()
                .map(t -> taskMapper.toResponse(t, scoresByTaskAndUser.getOrDefault(t.getId(), Map.of())))
                .toList();
    }

    private void applyLinks(Task task, TaskRequest req) {
        if (req.getLinks() == null) return;
        req.getLinks().stream()
                .map(l -> TaskLink.builder().url(l.getUrl()).title(l.getTitle()).task(task).build())
                .forEach(task.getLinks()::add);
    }

    private void applyAssignees(Task task, TaskRequest req) {
        if (req.getAssigneeIds() == null) return;
        req.getAssigneeIds().stream()
                .map(uid -> UserTask.builder()
                        .user(findUser(uid))
                        .task(task)
                        .build())
                .forEach(task.getAssignees()::add);
    }

    private Task findTaskById(Long id) {
        return taskRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Task", id));
    }

    private User findUser(Long id) {
        return userRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User", id));
    }

    private Event findEvent(Long id) {
        return eventRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Event", id));
    }
}