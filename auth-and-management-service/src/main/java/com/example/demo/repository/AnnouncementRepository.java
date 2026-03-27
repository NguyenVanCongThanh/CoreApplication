package com.example.demo.repository;

import com.example.demo.model.Announcement;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface AnnouncementRepository
        extends JpaRepository<Announcement, Long>, JpaSpecificationExecutor<Announcement> {

    @EntityGraph(attributePaths = {"images", "createdBy", "updatedBy"})
    @Query("SELECT a FROM Announcement a")
    List<Announcement> findAllWithDetails();

    @EntityGraph(attributePaths = {"images", "createdBy", "updatedBy"})
    @Query("SELECT a FROM Announcement a WHERE a.id = :id")
    Optional<Announcement> findWithDetailsById(Long id);
}
