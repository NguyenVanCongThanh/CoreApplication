package com.example.demo.utils;

import com.example.demo.enums.Priority;
import com.example.demo.model.Task;
import org.springframework.data.jpa.domain.Specification;

import java.time.LocalDateTime;
import jakarta.persistence.criteria.Predicate;

public class TaskSpecifications {

    private TaskSpecifications() {}

    public static Specification<Task> containsKeyword(String keyword, String... fields) {
        return (root, query, cb) -> {
            if (keyword == null || keyword.isBlank()) return cb.conjunction();
            String pattern = "%" + keyword.toLowerCase() + "%";
            Predicate[] predicates = java.util.Arrays.stream(fields)
                    .map(f -> cb.like(cb.lower(root.get(f)), pattern))
                    .toArray(Predicate[]::new);
            return cb.or(predicates);
        };
    }

    public static Specification<Task> hasColumnId(String columnId) {
        return (root, query, cb) ->
            (columnId == null || columnId.isBlank())
                ? cb.conjunction()
                : cb.equal(root.get("columnId"), columnId);
    }

    public static Specification<Task> hasPriority(Priority priority) {
        return (root, query, cb) ->
            priority == null ? cb.conjunction() : cb.equal(root.get("priority"), priority);
    }

    public static Specification<Task> hasEventId(Long eventId) {
        return (root, query, cb) ->
            eventId == null ? cb.conjunction() : cb.equal(root.get("event").get("id"), eventId);
    }

    public static Specification<Task> startAfter(LocalDateTime dt) {
        return (root, query, cb) ->
            dt == null ? cb.conjunction() : cb.greaterThanOrEqualTo(root.get("startDate"), dt);
    }

    public static Specification<Task> endBefore(LocalDateTime dt) {
        return (root, query, cb) ->
            dt == null ? cb.conjunction() : cb.lessThanOrEqualTo(root.get("endDate"), dt);
    }
}