package com.example.demo.mapper;

import com.example.demo.dto.announcement.AnnouncementRequest;
import com.example.demo.dto.announcement.AnnouncementResponse;
import com.example.demo.model.Announcement;
import com.example.demo.model.User;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Optional;

@Component
public class AnnouncementMapper implements EntityMapper<Announcement, AnnouncementResponse> {

    @Override
    public AnnouncementResponse toResponse(Announcement a) {
        return AnnouncementResponse.builder()
                .id(a.getId())
                .title(a.getTitle())
                .content(a.getContent())
                .images(a.getImages())
                .status(a.getStatus())
                .createdAt(a.getCreatedAt())
                .createdBy(emailOf(a.getCreatedBy()))
                .updatedAt(a.getUpdatedAt())
                .updatedBy(emailOf(a.getUpdatedBy()))
                .build();
    }

    public Announcement toEntity(AnnouncementRequest req, User creator) {
        return Announcement.builder()
                .title(req.getTitle())
                .content(req.getContent())
                .images(req.getImages() != null ? new ArrayList<>(req.getImages()) : new ArrayList<>())
                .status(req.getStatus())
                .createdBy(creator)
                .build();
    }

    private String emailOf(User user) {
        return Optional.ofNullable(user).map(User::getEmail).orElse(null);
    }
}