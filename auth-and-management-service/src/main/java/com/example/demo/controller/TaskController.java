package com.example.demo.controller;

import com.example.demo.dto.task.TaskRequest;
import com.example.demo.dto.task.TaskResponse;
import com.example.demo.enums.Priority;
import com.example.demo.service.TaskService;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
 
import java.time.LocalDateTime;
import java.util.List;
 
@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
class TaskController {
 
    private final TaskService taskService;
 
    @PostMapping
    public ResponseEntity<TaskResponse> create(@RequestBody TaskRequest req,
                                               @RequestParam Long userId) {
        return ResponseEntity.status(HttpStatus.CREATED).body(taskService.createTask(req, userId));
    }
 
    @PutMapping("/{id}")
    public ResponseEntity<TaskResponse> update(@PathVariable Long id,
                                               @RequestBody TaskRequest req,
                                               @RequestParam Long userId) {
        return ResponseEntity.ok(taskService.updateTask(id, req, userId));
    }
 
    @PatchMapping("/{id}/move")
    public ResponseEntity<TaskResponse> move(@PathVariable Long id,
                                             @RequestParam String columnId,
                                             @RequestParam Long userId) {
        return ResponseEntity.ok(taskService.moveTask(id, columnId, userId));
    }
 
    @GetMapping
    public ResponseEntity<List<TaskResponse>> getAll() {
        return ResponseEntity.ok(taskService.getAllTasks());
    }
 
    @GetMapping("/{id}")
    public ResponseEntity<TaskResponse> getById(@PathVariable Long id) {
        return ResponseEntity.ok(taskService.getTaskById(id));
    }
 
    @GetMapping("/event/{eventId}")
    public ResponseEntity<List<TaskResponse>> getByEvent(@PathVariable Long eventId) {
        return ResponseEntity.ok(taskService.getTasksByEventId(eventId));
    }
 
    @GetMapping("/column/{columnId}")
    public ResponseEntity<List<TaskResponse>> getByColumn(@PathVariable String columnId) {
        return ResponseEntity.ok(taskService.getTasksByColumnId(columnId));
    }
 
    @GetMapping("/search")
    public ResponseEntity<List<TaskResponse>> search(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String columnId,
            @RequestParam(required = false) Priority priority,
            @RequestParam(required = false) Long eventId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime startAfter,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime endBefore,
            @RequestParam(required = false) String[] sort) {
        return ResponseEntity.ok(
            taskService.searchTasks(keyword, columnId, priority, eventId, startAfter, endBefore, sort));
    }
 
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        taskService.deleteTask(id);
        return ResponseEntity.noContent().build();
    }
}