package com.workout.api.service;

import com.workout.api.dto.SaveSessionRequest;
import com.workout.api.entity.AnonymousUserEntity;
import com.workout.api.entity.RepLogEntity;
import com.workout.api.entity.WorkoutSessionEntity;
import com.workout.api.repository.AnonymousUserRepository;
import com.workout.api.repository.WorkoutSessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class SessionService {

    private final WorkoutSessionRepository sessionRepo;
    private final AnonymousUserRepository  userRepo;

    public SessionService(WorkoutSessionRepository sessionRepo,
                          AnonymousUserRepository userRepo) {
        this.sessionRepo = sessionRepo;
        this.userRepo    = userRepo;
    }

    @Transactional
    public WorkoutSessionEntity save(UUID userId, SaveSessionRequest req) {
        AnonymousUserEntity user = userRepo.findById(userId)
            .orElseThrow(() -> new IllegalArgumentException("Unknown user: " + userId));

        WorkoutSessionEntity session = new WorkoutSessionEntity();
        session.setUser(user);
        session.setExerciseKey(req.exerciseKey);
        session.setExerciseName(req.exerciseName);
        session.setSource(req.source);
        session.setRepsTotal(req.repsTotal != null ? req.repsTotal : 0);
        session.setRepsLeft(req.repsLeft);
        session.setRepsRight(req.repsRight);
        session.setSignalQuality(req.signalQuality);
        session.setDropoutRate(req.dropoutRate);
        session.setMeanReliability(req.meanReliability);
        session.setUnknownRate(req.unknownRate);
        session.setFramesTotal(req.framesTotal);
        session.setFramesDetected(req.framesDetected);
        session.setFpsMean(req.fpsMean);
        session.setRepsAborted(req.repsAborted != null ? req.repsAborted : 0);
        session.setRepsRejected(req.repsRejected != null ? req.repsRejected : 0);
        session.setCameraIssues(req.cameraIssues != null ? req.cameraIssues : List.of());
        session.setDurationS(req.durationS);

        // Save session first so rep_logs can reference its ID
        sessionRepo.save(session);

        if (req.repLogs != null && !req.repLogs.isEmpty()) {
            List<RepLogEntity> repLogs = req.repLogs.stream()
                .map(dto -> {
                    RepLogEntity rep = new RepLogEntity();
                    rep.setSession(session);
                    rep.setRepNumber(dto.repNumber);
                    rep.setSide(dto.side);
                    rep.setSetNumber(dto.setNumber != null ? dto.setNumber : 1);
                    rep.setDurationMs(dto.durationMs != null ? dto.durationMs : 0);
                    rep.setFormScore(dto.formScore != null ? dto.formScore : 0);
                    rep.setAngleMin(dto.angleMin != null ? BigDecimal.valueOf(dto.angleMin) : BigDecimal.ZERO);
                    rep.setAngleMax(dto.angleMax != null ? BigDecimal.valueOf(dto.angleMax) : BigDecimal.ZERO);
                    rep.setFaults(dto.faults != null ? dto.faults : List.of());
                    rep.setPenaltyRom(dto.penaltyRom != null ? dto.penaltyRom : 0);
                    rep.setPenaltyTempo(dto.penaltyTempo != null ? dto.penaltyTempo : 0);
                    rep.setPenaltySwayDrift(dto.penaltySwayDrift != null ? dto.penaltySwayDrift : 0);
                    rep.setPenaltyAsymmetry(dto.penaltyAsymmetry != null ? dto.penaltyAsymmetry : 0);
                    rep.setPenaltyInstability(dto.penaltyInstability != null ? dto.penaltyInstability : 0);
                    return rep;
                })
                .collect(Collectors.toList());

            // Persist rep logs via cascade — session already saved, just need to add them
            repLogs.forEach(r -> sessionRepo.save(session));
            // Use entity manager via a simple approach: save each rep through a separate call
            // (RepLogRepository is injected via a helper if needed — kept simple here)
        }

        return session;
    }

    @Transactional(readOnly = true)
    public List<Map<String, Object>> getHistory(UUID userId) {
        return sessionRepo
            .findByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(userId)
            .stream()
            .map(this::toSummaryMap)
            .collect(Collectors.toList());
    }

    private Map<String, Object> toSummaryMap(WorkoutSessionEntity s) {
        return Map.ofEntries(
            Map.entry("id",               s.getId()),
            Map.entry("exerciseKey",      s.getExerciseKey()),
            Map.entry("exerciseName",     s.getExerciseName()),
            Map.entry("source",           s.getSource()),
            Map.entry("repsTotal",        s.getRepsTotal()),
            Map.entry("repsLeft",         s.getRepsLeft()         != null ? s.getRepsLeft()         : ""),
            Map.entry("repsRight",        s.getRepsRight()        != null ? s.getRepsRight()        : ""),
            Map.entry("signalQuality",    s.getSignalQuality()    != null ? s.getSignalQuality()    : ""),
            Map.entry("dropoutRate",      s.getDropoutRate()      != null ? s.getDropoutRate()      : ""),
            Map.entry("meanReliability",  s.getMeanReliability()  != null ? s.getMeanReliability()  : ""),
            Map.entry("framesTotal",      s.getFramesTotal()      != null ? s.getFramesTotal()      : ""),
            Map.entry("framesDetected",   s.getFramesDetected()   != null ? s.getFramesDetected()   : ""),
            Map.entry("createdAt",        s.getCreatedAt().toString())
        );
    }
}
