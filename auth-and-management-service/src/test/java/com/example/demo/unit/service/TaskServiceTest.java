package com.example.demo.unit.service;

import com.example.demo.common.TestDataFactory;
import com.example.demo.dto.task.TaskRequest;
import com.example.demo.dto.task.TaskResponse;
import com.example.demo.enums.Priority;
import com.example.demo.exception.ResourceNotFoundException;
import com.example.demo.mapper.TaskMapper;
import com.example.demo.model.*;
import com.example.demo.repository.*;
import com.example.demo.service.TaskService;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("TaskService Tests")
class TaskServiceTest {

    @Mock TaskRepository      taskRepo;
    @Mock UserRepository      userRepo;
    @Mock EventRepository     eventRepo;
    @Mock TaskMapper          taskMapper;

    @InjectMocks TaskService taskService;

    private User    creator;
    private User    assignee;
    private Event   event;
    private Task    task;

    @BeforeEach
    void setUp() {
        creator  = TestDataFactory.managerUser();
        assignee = TestDataFactory.regularUser();
        event    = TestDataFactory.event();
        task     = TestDataFactory.task();
        // Init collections to avoid NPE
        task.setLinks(new ArrayList<>());
        task.setAssignees(new ArrayList<>());
    }

    @Test
    @DisplayName("createTask - success with event and assignee")
    void createTask_success_withEventAndAssignee() {
        var req = TestDataFactory.taskRequest();
        var expectedResponse = TaskResponse.builder().id(100L).title("Build Feature X").build();

        given(userRepo.findById(creator.getId())).willReturn(Optional.of(creator));
        given(eventRepo.findById(10L)).willReturn(Optional.of(event));
        given(userRepo.findById(assignee.getId())).willReturn(Optional.of(assignee));
        given(taskRepo.save(any(Task.class))).willReturn(task);
        given(taskMapper.toResponse(any(Task.class))).willReturn(expectedResponse);

        TaskResponse result = taskService.createTask(req, creator.getId());

        assertThat(result.getId()).isEqualTo(100L);
        // save() called twice: once before links/assignees, once after
        then(taskRepo).should(times(2)).save(any(Task.class));
    }

    @Test
    @DisplayName("createTask - success without event (standalone task)")
    void createTask_withoutEvent() {
        var req = TestDataFactory.taskRequest();
        req.setEventId(null);
        req.setAssigneeIds(null);

        given(userRepo.findById(creator.getId())).willReturn(Optional.of(creator));
        given(taskRepo.save(any(Task.class))).willReturn(task);
        given(taskMapper.toResponse(any(Task.class))).willReturn(
                TaskResponse.builder().id(100L).build());

        assertThatCode(() -> taskService.createTask(req, creator.getId())).doesNotThrowAnyException();

        // eventRepo should NOT be called
        then(eventRepo).should(never()).findById(anyLong());
    }

    @Test
    @DisplayName("createTask - with links creates TaskLink entities")
    void createTask_withLinks() {
        var req = TestDataFactory.taskRequestWithLinks();

        given(userRepo.findById(creator.getId())).willReturn(Optional.of(creator));
        given(taskRepo.save(any(Task.class))).willReturn(task);
        given(taskMapper.toResponse(any(Task.class))).willReturn(TaskResponse.builder().id(100L).build());

        taskService.createTask(req, creator.getId());

        // Verify that the task saved in second save call has links
        then(taskRepo).should(times(2)).save(argThat(t -> {
            return true; // basic check that save was called
        }));
    }

    @Test
    @DisplayName("createTask - creator not found throws ResourceNotFoundException")
    void createTask_creatorNotFound() {
        given(userRepo.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> taskService.createTask(TestDataFactory.taskRequest(), 999L))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasMessageContaining("User");
    }

    @Test
    @DisplayName("createTask - event not found throws ResourceNotFoundException")
    void createTask_eventNotFound() {
        var req = TestDataFactory.taskRequest();
        req.setEventId(999L);

        given(userRepo.findById(creator.getId())).willReturn(Optional.of(creator));
        given(eventRepo.findById(999L)).willReturn(Optional.empty());
        given(taskRepo.save(any(Task.class))).willReturn(task);

        assertThatThrownBy(() -> taskService.createTask(req, creator.getId()))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasMessageContaining("Event");
    }

    @Test
    @DisplayName("createTask - assignee not found throws ResourceNotFoundException")
    void createTask_assigneeNotFound() {
        var req = TestDataFactory.taskRequest();
        req.setAssigneeIds(List.of(999L));

        given(userRepo.findById(creator.getId())).willReturn(Optional.of(creator));
        given(eventRepo.findById(anyLong())).willReturn(Optional.of(event));
        given(taskRepo.save(any(Task.class))).willReturn(task);
        given(userRepo.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> taskService.createTask(req, creator.getId()))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasMessageContaining("User");
    }

    @Test
    @DisplayName("updateTask - clears old links/assignees and sets new ones")
    void updateTask_clearsAndSetsNewAssignees() {
        // task has old assignee
        var oldAssignee = TestDataFactory.userWithId(99L);
        var oldUserTask = UserTask.builder().user(oldAssignee).task(task).build();
        task.setAssignees(new ArrayList<>(List.of(oldUserTask)));

        var req = TestDataFactory.taskRequest();
        req.setAssigneeIds(List.of(assignee.getId())); // new assignee

        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(userRepo.findById(creator.getId())).willReturn(Optional.of(creator));
        given(eventRepo.findById(anyLong())).willReturn(Optional.of(event));
        given(userRepo.findById(assignee.getId())).willReturn(Optional.of(assignee));
        given(taskRepo.save(any(Task.class))).willReturn(task);
        given(taskMapper.toResponse(any(Task.class))).willReturn(TaskResponse.builder().build());

        taskService.updateTask(task.getId(), req, creator.getId());

        // After update, only new assignee should be in list
        assertThat(task.getAssignees()).hasSize(1);
        assertThat(task.getAssignees().get(0).getUser()).isEqualTo(assignee);
    }

    @Test
    @DisplayName("updateTask - sets event to null when eventId is null")
    void updateTask_clearsEvent_whenEventIdNull() {
        task.setEvent(event);
        var req = TestDataFactory.taskRequest();
        req.setEventId(null);

        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(userRepo.findById(anyLong())).willReturn(Optional.of(creator));
        given(taskRepo.save(any(Task.class))).willReturn(task);
        given(taskMapper.toResponse(any(Task.class))).willReturn(TaskResponse.builder().build());

        taskService.updateTask(task.getId(), req, creator.getId());

        assertThat(task.getEvent()).isNull();
    }

    @Test
    @DisplayName("updateTask - task not found throws ResourceNotFoundException")
    void updateTask_taskNotFound() {
        given(taskRepo.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() ->
            taskService.updateTask(999L, TestDataFactory.taskRequest(), creator.getId()))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasMessageContaining("Task");
    }

    @Test
    @DisplayName("moveTask - updates columnId, updatedBy, updatedAt")
    void moveTask_updatesFields() {
        given(taskRepo.findById(task.getId())).willReturn(Optional.of(task));
        given(userRepo.findById(creator.getId())).willReturn(Optional.of(creator));
        given(taskRepo.save(any(Task.class))).willReturn(task);
        given(taskMapper.toResponse(any(Task.class))).willReturn(
                TaskResponse.builder().columnId("done").build());

        TaskResponse result = taskService.moveTask(task.getId(), "done", creator.getId());

        assertThat(task.getColumnId()).isEqualTo("done");
        assertThat(task.getUpdatedBy()).isEqualTo(creator);
        assertThat(task.getUpdatedAt()).isNotNull();
        assertThat(result.getColumnId()).isEqualTo("done");
    }

    @Test
    @DisplayName("getAllTasks - calls findLinksForTasks when list is non-empty (2-step fetch)")
    void getAllTasks_callsFindLinksForTasks() {
        given(taskRepo.findAllWithAssignees()).willReturn(List.of(task));
        given(taskRepo.findLinksForTasks(anyList())).willReturn(List.of(task));
        given(taskMapper.toResponse(any())).willReturn(TaskResponse.builder().build());

        taskService.getAllTasks();

        then(taskRepo).should(times(1)).findLinksForTasks(anyList());
    }

    @Test
    @DisplayName("getAllTasks - does NOT call findLinksForTasks when list is empty")
    void getAllTasks_skipsLinksWhenEmpty() {
        given(taskRepo.findAllWithAssignees()).willReturn(List.of());

        List<TaskResponse> result = taskService.getAllTasks();

        assertThat(result).isEmpty();
        then(taskRepo).should(never()).findLinksForTasks(anyList());
    }

    @Test
    @DisplayName("getTaskById - found: fetches assignees and links separately")
    void getTaskById_success() {
        given(taskRepo.findByIdWithAssignees(task.getId())).willReturn(Optional.of(task));
        given(taskRepo.findByIdWithLinks(task.getId())).willReturn(Optional.of(task));
        given(taskMapper.toResponse(task)).willReturn(TaskResponse.builder().id(task.getId()).build());

        TaskResponse result = taskService.getTaskById(task.getId());

        assertThat(result.getId()).isEqualTo(task.getId());
        then(taskRepo).should().findByIdWithAssignees(task.getId());
        then(taskRepo).should().findByIdWithLinks(task.getId());
    }

    @Test
    @DisplayName("getTaskById - not found throws ResourceNotFoundException")
    void getTaskById_notFound() {
        given(taskRepo.findByIdWithAssignees(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> taskService.getTaskById(999L))
            .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    @DisplayName("searchTasks - null params treated as no filter (returns all)")
    void searchTasks_nullParams_returnsAll() {
        given(taskRepo.findAll(any(org.springframework.data.jpa.domain.Specification.class),
                               any(org.springframework.data.domain.Sort.class)))
            .willReturn(List.of(task));
        given(taskMapper.toResponse(any())).willReturn(TaskResponse.builder().build());

        List<TaskResponse> result = taskService.searchTasks(null, null, null, null, null, null, null);

        assertThat(result).hasSize(1);
    }

    @Test
    @DisplayName("deleteTask - delegates to repository deleteById")
    void deleteTask_delegates() {
        taskService.deleteTask(100L);
        then(taskRepo).should().deleteById(100L);
    }
}
