package com.example.demo.utils;

import org.springframework.data.domain.Sort;

public final class SortUtils {

    private SortUtils() {}

    public static Sort parseSort(String[] params) {
        if (params == null || params.length == 0) return Sort.unsorted();

        return java.util.Arrays.stream(params)
                .map(p -> p.split(":", 2))
                .map(parts -> {
                    var dir = parts.length > 1 && "desc".equalsIgnoreCase(parts[1])
                              ? Sort.Direction.DESC : Sort.Direction.ASC;
                    return Sort.by(dir, parts[0]);
                })
                .reduce(Sort.unsorted(), Sort::and);
    }
}
