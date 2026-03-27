package com.example.demo.mapper;

import java.util.List;

/**
 * Generic mapper interface - Interface Segregation Principle.
 * Mỗi mapper implement interface này, tái sử dụng toResponseList() miễn phí.
 */
public interface EntityMapper<E, R> {
    R toResponse(E entity);

    default List<R> toResponseList(List<E> entities) {
        return entities.stream().map(this::toResponse).toList();
    }
}