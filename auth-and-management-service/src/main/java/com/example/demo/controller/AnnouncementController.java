package com.example.demo.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import com.example.demo.service.AnnouncementService;
import com.example.demo.dto.announcement.AnnouncementRequest;
import com.example.demo.dto.announcement.AnnouncementResponse;
 
@RestController
@RequestMapping("/api/announcements")
@RequiredArgsConstructor
class AnnouncementController {
 
    private final AnnouncementService announcementService;
 
    @GetMapping
    public ResponseEntity<List<AnnouncementResponse>> getAll() {
        return ResponseEntity.ok(announcementService.getAll());
    }
 
    @GetMapping("/{id}")
    public ResponseEntity<AnnouncementResponse> getById(@PathVariable Long id) {
        return ResponseEntity.ok(announcementService.getById(id));
    }
 
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN','MANAGER')")
    public ResponseEntity<AnnouncementResponse> create(@RequestBody AnnouncementRequest req) {
        return ResponseEntity.ok(announcementService.create(req));
    }
 
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN','MANAGER')")
    public ResponseEntity<AnnouncementResponse> update(@PathVariable Long id,
                                                       @RequestBody AnnouncementRequest req) {
        return ResponseEntity.ok(announcementService.update(id, req));
    }
 
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN','MANAGER')")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        announcementService.delete(id);
        return ResponseEntity.noContent().build();
    }
}