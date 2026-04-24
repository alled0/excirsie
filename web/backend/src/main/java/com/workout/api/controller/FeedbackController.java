package com.workout.api.controller;

import com.workout.api.model.FeedbackRequest;
import com.workout.api.service.FeedbackService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/feedback")
public class FeedbackController {

    private final FeedbackService feedbackService;

    public FeedbackController(FeedbackService feedbackService) {
        this.feedbackService = feedbackService;
    }

    @PostMapping
    public ResponseEntity<Map<String, String>> submit(
        @RequestHeader(value = "X-User-Id", required = false) String userIdHeader,
        @Valid @RequestBody FeedbackRequest req
    ) {
        UUID userId = parseUserId(userIdHeader);
        feedbackService.save(userId, req);
        return ResponseEntity.ok(Map.of("message", "Thank you"));
    }

    private UUID parseUserId(String raw) {
        if (raw == null || raw.isBlank()) return null;
        try { return UUID.fromString(raw); } catch (IllegalArgumentException e) { return null; }
    }
}
