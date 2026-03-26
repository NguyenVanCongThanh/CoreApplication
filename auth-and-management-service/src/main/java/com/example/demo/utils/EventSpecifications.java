package com.example.demo.utils;

import com.example.demo.enums.StatusEvent;
//
import com.example.demo.model.Event;
import org.springframework.data.jpa.domain.Specification;
import jakarta.persistence.criteria.*;

import java.time.LocalDateTime;

public class EventSpecifications {

    private EventSpecifications() {}

    public static Specification<Event> containsKeyword(String keyword, String... fields) {
        return (root, query, cb) -> {
            if (keyword == null || keyword.isBlank()) return cb.conjunction();
            String pattern = "%" + keyword.toLowerCase() + "%";
            Predicate[] predicates = java.util.Arrays.stream(fields)
                    .map(f -> cb.like(cb.lower(root.get(f)), pattern))
                    .toArray(Predicate[]::new);
            return cb.or(predicates);
        };
    }

    public static Specification<Event> hasStatus(StatusEvent status) {
        return (root, query, cb) ->
            status == null ? cb.conjunction() : cb.equal(root.get("statusEvent"), status);
    }

    public static Specification<Event> startAfter(LocalDateTime dt) {
        return (root, query, cb) ->
            dt == null ? cb.conjunction() : cb.greaterThanOrEqualTo(root.get("startTime"), dt);
    }

    public static Specification<Event> endBefore(LocalDateTime dt) {
        return (root, query, cb) ->
            dt == null ? cb.conjunction() : cb.lessThanOrEqualTo(root.get("endTime"), dt);
    }
}
