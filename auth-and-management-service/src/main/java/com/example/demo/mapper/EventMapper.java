package com.example.demo.mapper;

import com.example.demo.dto.event.EventResponse;
import com.example.demo.model.Event;
import com.example.demo.model.Task;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;

@Component
public class EventMapper implements EntityMapper<Event, EventResponse> {

    @Override
    public EventResponse toResponse(Event event) {
        return buildBase(event).build();
    }

    public EventResponse toResponseWithTasks(Event event) {
        var tasks = Optional.ofNullable(event.getTasks())
                .filter(list -> !list.isEmpty())
                .map(list -> list.stream().map(this::mapTask).toList())
                .orElse(List.of());

        return buildBase(event).tasks(tasks).build();
    }

    private EventResponse.EventResponseBuilder buildBase(Event event) {
        return EventResponse.builder()
                .id(event.getId())
                .title(event.getTitle())
                .description(event.getDescription())
                .statusEvent(event.getStatusEvent())
                .startTime(event.getStartTime())
                .endTime(event.getEndTime())
                .capacity(event.getCapacity());
    }

    private EventResponse.TaskInfo mapTask(Task task) {
        return EventResponse.TaskInfo.builder()
                .id(task.getId())
                .title(task.getTitle())
                .description(task.getDescription())
                .priority(task.getPriority() != null ? task.getPriority().name() : null)
                .columnId(task.getColumnId())
                .startDate(task.getStartDate())
                .endDate(task.getEndDate())
                .build();
    }
}
