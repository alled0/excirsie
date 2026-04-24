package com.workout.api.controller;

import com.workout.api.dto.TrackEventsRequest;
import com.workout.api.service.EventService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/events")
public class EventController {

    private final EventService eventService;

    public EventController(EventService eventService) {
        this.eventService = eventService;
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> track(
        @RequestHeader(value = "X-User-Id", required = false) String userIdHeader,
        @RequestBody TrackEventsRequest req
    ) {
        UUID userId = parseUserId(userIdHeader);
        if (userId == null || req.events == null) {
            return ResponseEntity.ok(Map.of("accepted", 0));
        }

        int accepted = eventService.saveAll(userId, req.events);
        return ResponseEntity.ok(Map.of("accepted", accepted));
    }

    private UUID parseUserId(String raw) {
        if (raw == null || raw.isBlank()) return null;
        try { return UUID.fromString(raw); } catch (IllegalArgumentException e) { return null; }
    }
}
