package com.example.demo.service;

import com.example.demo.dto.event.*;
import com.example.demo.enums.StatusEvent;
import com.example.demo.mapper.EventMapper;
import com.example.demo.model.Event;
import com.example.demo.model.User;
import com.example.demo.repository.EventRepository;
import com.example.demo.repository.UserRepository;
import com.example.demo.utils.*;

import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class EventService {
    private final EventRepository eventRepo;
    private final UserRepository userRepo;
    private final EventMapper eventMapper;

    @Transactional
    public EventResponse createEvent(EventRequest request, Long creatorId) {
        User creator = userRepo.findById(creatorId).orElseThrow(() -> new RuntimeException("User not found"));
        Event event = Event.builder()
                .title(request.getTitle())
                .description(request.getDescription())
                .statusEvent(request.getStatusEvent())
                .startTime(request.getStartTime())
                .endTime(request.getEndTime())
                .capacity(request.getCapacity())
                .createdAt(LocalDateTime.now())
                .createdBy(creator)
                .build();
        event = eventRepo.save(event);
        return eventMapper.toResponse(event);
    }

    @Transactional
    public EventResponse updateEvent(Long id, EventRequest request, Long updaterId) {
        Event event = eventRepo.findById(id)
                .orElseThrow(() -> new RuntimeException("Event not found"));
        
        User updater = userRepo.findById(updaterId)
                .orElseThrow(() -> new RuntimeException("User not found"));

        event.setTitle(request.getTitle());
        event.setDescription(request.getDescription());
        event.setStatusEvent(request.getStatusEvent());
        event.setStartTime(request.getStartTime());
        event.setEndTime(request.getEndTime());
        event.setCapacity(request.getCapacity());
        event.setUpdatedAt(LocalDateTime.now());
        event.setUpdatedBy(updater);
        event = eventRepo.save(event);
        return eventMapper.toResponse(event);
    }

    @Transactional(readOnly = true)
    public List<EventResponse> searchEvents(String keyword,
                                            StatusEvent status,
                                            LocalDateTime start,
                                            LocalDateTime end,
                                            String[] sortParams) {

        Specification<Event> spec = Specification
                .where(EventSpecifications.containsKeyword(keyword, "title", "description"))
                .and(EventSpecifications.hasStatus(status))
                .and(EventSpecifications.startAfter(start))
                .and(EventSpecifications.endBefore(end));

        Sort sort = SortUtils.parseSort(sortParams);

        return eventRepo.findAll(spec, sort).stream()
                .map(eventMapper::toResponse)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<EventResponse> getAllEvents() {
        // Sử dụng EntityGraph để fetch tasks cùng lúc, tránh N+1 query
        return eventRepo.findAllWithTasks().stream()
                .map(eventMapper::toResponseWithTasks)
                .toList();
    }

    @Transactional(readOnly = true)
    public EventResponse getEventById(Long id) {
        // Fetch event cùng với tasks
        return eventRepo.findWithTasksById(id)
                .map(eventMapper::toResponseWithTasks)
                .orElseThrow(() -> new RuntimeException("Event not found"));
    }

    @Transactional
    public void deleteEvent(Long id) {
        eventRepo.deleteById(id);
    }
}