package com.workout.api.controller;

import com.workout.api.dto.SaveSessionRequest;
import com.workout.api.entity.WorkoutSessionEntity;
import com.workout.api.service.SessionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/sessions")
public class SessionController {

    private final SessionService sessionService;

    public SessionController(SessionService sessionService) {
        this.sessionService = sessionService;
    }

    @PostMapping
    public ResponseEntity<?> save(
        @RequestHeader(value = "X-User-Id", required = false) String userIdHeader,
        @RequestBody SaveSessionRequest req
    ) {
        UUID userId = parseUserId(userIdHeader);
        if (userId == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "X-User-Id header is required"));
        }

        try {
            WorkoutSessionEntity session = sessionService.save(userId, req);
            return ResponseEntity.ok(Map.of(
                "sessionId", session.getId().toString(),
                "createdAt", session.getCreatedAt().toString()
            ));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping
    public ResponseEntity<?> history(
        @RequestHeader(value = "X-User-Id", required = false) String userIdHeader
    ) {
        UUID userId = parseUserId(userIdHeader);
        if (userId == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "X-User-Id header is required"));
        }

        List<Map<String, Object>> records = sessionService.getHistory(userId);
        return ResponseEntity.ok(records);
    }

    private UUID parseUserId(String raw) {
        if (raw == null || raw.isBlank()) return null;
        try {
            return UUID.fromString(raw);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }
}
