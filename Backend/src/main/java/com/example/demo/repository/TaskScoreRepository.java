package com.example.demo.repository;

import com.example.demo.model.TaskScore;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface TaskScoreRepository extends JpaRepository<TaskScore, Long> {
    Optional<TaskScore> findByTaskIdAndUserId(Long taskId, Long userId);

    List<TaskScore> findByTaskId(Long taskId);

    List<TaskScore> findByUserId(Long userId);

    List<TaskScore> findByTaskIdAndAppliedFalse(Long taskId);

    @Query("SELECT SUM(ts.score) FROM TaskScore ts WHERE ts.user.id = :userId AND ts.applied = true")
    Integer getTotalAppliedScoreForUser(@Param("userId") Long userId);

    @Query("SELECT ts FROM TaskScore ts " +
           "LEFT JOIN FETCH ts.user " +
           "LEFT JOIN FETCH ts.task " +
           "LEFT JOIN FETCH ts.scoredBy " +
           "WHERE ts.task.id = :taskId")
    List<TaskScore> findByTaskIdWithDetails(@Param("taskId") Long taskId);

    boolean existsByTaskIdAndUserId(Long taskId, Long userId);
}
