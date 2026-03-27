package com.example.demo.unit.utils;

import com.example.demo.utils.SortUtils;
import org.junit.jupiter.api.*;
import org.springframework.data.domain.Sort;

import static org.assertj.core.api.Assertions.*;

@DisplayName("SortUtils Tests")
class SortUtilsTest {

    @Test
    @DisplayName("parseSort - null params returns unsorted")
    void nullParams_returnsUnsorted() {
        assertThat(SortUtils.parseSort(null)).isEqualTo(Sort.unsorted());
    }

    @Test
    @DisplayName("parseSort - empty array returns unsorted")
    void emptyArray_returnsUnsorted() {
        assertThat(SortUtils.parseSort(new String[]{})).isEqualTo(Sort.unsorted());
    }

    @Test
    @DisplayName("parseSort - 'createdAt:desc' produces DESC order")
    void descSort_parsed() {
        Sort sort = SortUtils.parseSort(new String[]{"createdAt:desc"});
        assertThat(sort.getOrderFor("createdAt")).isNotNull();
        assertThat(sort.getOrderFor("createdAt").getDirection()).isEqualTo(Sort.Direction.DESC);
    }

    @Test
    @DisplayName("parseSort - 'title:asc' produces ASC order")
    void ascSort_parsed() {
        Sort sort = SortUtils.parseSort(new String[]{"title:asc"});
        assertThat(sort.getOrderFor("title").getDirection()).isEqualTo(Sort.Direction.ASC);
    }

    @Test
    @DisplayName("parseSort - field without direction defaults to ASC")
    void noDirection_defaultsToAsc() {
        Sort sort = SortUtils.parseSort(new String[]{"priority"});
        assertThat(sort.getOrderFor("priority").getDirection()).isEqualTo(Sort.Direction.ASC);
    }

    @Test
    @DisplayName("parseSort - multiple params combined")
    void multipleParams_combined() {
        Sort sort = SortUtils.parseSort(new String[]{"createdAt:desc", "title:asc"});
        assertThat(sort.getOrderFor("createdAt").getDirection()).isEqualTo(Sort.Direction.DESC);
        assertThat(sort.getOrderFor("title").getDirection()).isEqualTo(Sort.Direction.ASC);
    }

    @Test
    @DisplayName("parseSort - case-insensitive direction (DESC, desc, Desc)")
    void caseInsensitiveDirection() {
        assertThat(SortUtils.parseSort(new String[]{"field:DESC"}).getOrderFor("field").getDirection())
            .isEqualTo(Sort.Direction.DESC);
        assertThat(SortUtils.parseSort(new String[]{"field:Desc"}).getOrderFor("field").getDirection())
            .isEqualTo(Sort.Direction.DESC);
    }
}