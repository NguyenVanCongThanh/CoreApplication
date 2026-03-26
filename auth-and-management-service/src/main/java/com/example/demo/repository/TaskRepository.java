package com.example.demo.repository;

import com.example.demo.model.Task;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * TaskRepository - tối ưu N+1 query bằng 2-step fetch pattern.
 *
 * Pattern:
 *   Step 1 → findAllWithAssignees()        : JOIN FETCH assignees + user + createdBy + updatedBy
 *   Step 2 → findLinksForTasks(tasks)      : JOIN FETCH links (riêng để tránh MultipleBagFetchException)
 *
 * Không JOIN FETCH 2 collection cùng lúc trong 1 query.
 */
@Repository
public interface TaskRepository extends JpaRepository<Task, Long>, JpaSpecificationExecutor<Task> {

    @Query("""
        SELECT DISTINCT t FROM Task t
        LEFT JOIN FETCH t.event
        LEFT JOIN FETCH t.assignees a
        LEFT JOIN FETCH a.user
        LEFT JOIN FETCH t.createdBy
        LEFT JOIN FETCH t.updatedBy
        """)
    List<Task> findAllWithAssignees();

    @Query("""
        SELECT DISTINCT t FROM Task t
        LEFT JOIN FETCH t.links
        WHERE t IN :tasks
        """)
    List<Task> findLinksForTasks(@Param("tasks") List<Task> tasks);

    @Query("""
        SELECT DISTINCT t FROM Task t
        LEFT JOIN FETCH t.event
        LEFT JOIN FETCH t.assignees a
        LEFT JOIN FETCH a.user
        LEFT JOIN FETCH t.createdBy
        LEFT JOIN FETCH t.updatedBy
        WHERE t.id = :id
        """)
    Optional<Task> findByIdWithAssignees(@Param("id") Long id);

    @Query("""
        SELECT DISTINCT t FROM Task t
        LEFT JOIN FETCH t.links
        WHERE t.id = :id
        """)
    Optional<Task> findByIdWithLinks(@Param("id") Long id);

    @Query("""
        SELECT DISTINCT t FROM Task t
        LEFT JOIN FETCH t.event
        LEFT JOIN FETCH t.assignees a
        LEFT JOIN FETCH a.user
        LEFT JOIN FETCH t.createdBy
        LEFT JOIN FETCH t.updatedBy
        WHERE t.event.id = :eventId
        """)
    List<Task> findByEventIdWithAssignees(@Param("eventId") Long eventId);

    @Query("""
        SELECT DISTINCT t FROM Task t
        LEFT JOIN FETCH t.event
        LEFT JOIN FETCH t.assignees a
        LEFT JOIN FETCH a.user
        LEFT JOIN FETCH t.createdBy
        LEFT JOIN FETCH t.updatedBy
        WHERE t.columnId = :columnId
        """)
    List<Task> findByColumnIdWithAssignees(@Param("columnId") String columnId);

    @Query("""
        SELECT DISTINCT t FROM Task t
        LEFT JOIN FETCH t.assignees a
        LEFT JOIN FETCH a.user u
        WHERE t.id IN :ids
        """)
    List<Task> findByIdsWithAssignees(@Param("ids") List<Long> ids);

    List<Task> findByEventId(Long eventId);
    List<Task> findByColumnId(String columnId);
}