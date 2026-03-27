package com.example.demo.model;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "task_scores", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"task_id", "user_id"})
})
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder(toBuilder = true)
public class TaskScore {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "task_id", nullable = false)
    private Task task;

    @ManyToOne
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(nullable = false)
    @Builder.Default
    private Integer score = 0;

    @Column(nullable = false)
    @Builder.Default
    private Boolean applied = false; // true nếu điểm đã được cộng vào totalScore của user

    @ManyToOne
    @JoinColumn(name = "scored_by") // admin/manager đã set điểm
    private User scoredBy;

    private LocalDateTime scoredAt;

    private LocalDateTime appliedAt; // thời điểm cộng điểm vào totalScore

    @Column(length = 500)
    private String notes; // ghi chú tại sao cộng/trừ điểm này

    @PrePersist
    protected void onCreate() {
        if (scoredAt == null) {
            scoredAt = LocalDateTime.now();
        }
    }
}
