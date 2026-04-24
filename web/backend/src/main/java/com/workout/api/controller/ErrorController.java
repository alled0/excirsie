package com.workout.api.controller;

import com.workout.api.dto.ReportErrorRequest;
import com.workout.api.service.ErrorService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/errors")
public class ErrorController {

    private final ErrorService errorService;

    public ErrorController(ErrorService errorService) {
        this.errorService = errorService;
    }

    @PostMapping
    public ResponseEntity<Void> report(
        @RequestHeader(value = "X-User-Id", required = false) String userIdHeader,
        @RequestBody ReportErrorRequest req
    ) {
        UUID userId = parseUserId(userIdHeader);
        errorService.save(userId, req);
        return ResponseEntity.noContent().build();
    }

    private UUID parseUserId(String raw) {
        if (raw == null || raw.isBlank()) return null;
        try { return UUID.fromString(raw); } catch (IllegalArgumentException e) { return null; }
    }
}
