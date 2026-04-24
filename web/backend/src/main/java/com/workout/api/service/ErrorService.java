package com.workout.api.service;

import com.workout.api.dto.ReportErrorRequest;
import com.workout.api.entity.ClientErrorEntity;
import com.workout.api.repository.AnonymousUserRepository;
import com.workout.api.repository.ClientErrorRepository;
import com.workout.api.repository.WorkoutSessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

@Service
public class ErrorService {

    private final ClientErrorRepository    errorRepo;
    private final AnonymousUserRepository  userRepo;
    private final WorkoutSessionRepository sessionRepo;

    public ErrorService(ClientErrorRepository errorRepo,
                        AnonymousUserRepository userRepo,
                        WorkoutSessionRepository sessionRepo) {
        this.errorRepo   = errorRepo;
        this.userRepo    = userRepo;
        this.sessionRepo = sessionRepo;
    }

    @Transactional
    public void save(UUID userId, ReportErrorRequest req) {
        ClientErrorEntity error = new ClientErrorEntity();

        if (userId != null) {
            userRepo.findById(userId).ifPresent(error::setUser);
        }
        if (req.sessionId != null) {
            sessionRepo.findById(req.sessionId).ifPresent(error::setSession);
        }

        error.setErrorType(req.errorType != null ? req.errorType : "unknown");
        error.setMessage(req.message);
        error.setStackHash(req.stackHash);
        error.setHttpStatus(req.httpStatus);
        error.setOccurredAt(req.occurredAt != null ? req.occurredAt : LocalDateTime.now());

        errorRepo.save(error);
    }
}
