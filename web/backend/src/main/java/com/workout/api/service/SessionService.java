package com.workout.api.service;

import com.workout.api.dto.SaveSessionRequest;
import com.workout.api.entity.AnonymousUserEntity;
import com.workout.api.entity.RepLogEntity;
import com.workout.api.entity.WorkoutSessionEntity;
import com.workout.api.repository.AnonymousUserRepository;
import com.workout.api.repository.RepLogRepository;
import com.workout.api.repository.WorkoutSessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class SessionService {

    private final WorkoutSessionRepository sessionRepo;
    private final AnonymousUserRepository  userRepo;
    private final RepLogRepository         repLogRepo;

    public SessionService(WorkoutSessionRepository sessionRepo,
                          AnonymousUserRepository userRepo,
                          RepLogRepository repLogRepo) {
        this.sessionRepo = sessionRepo;
        this.userRepo    = userRepo;
        this.repLogRepo  = repLogRepo;
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

            repLogRepo.saveAll(repLogs);
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
        // HashMap allows null values — Map.ofEntries does not
        Map<String, Object> m = new HashMap<>();
        m.put("id",              s.getId());
        m.put("exerciseKey",     s.getExerciseKey());
        m.put("exerciseName",    s.getExerciseName());
        m.put("source",          s.getSource());
        m.put("repsTotal",       s.getRepsTotal());
        m.put("repsLeft",        s.getRepsLeft());
        m.put("repsRight",       s.getRepsRight());
        m.put("signalQuality",   s.getSignalQuality());
        m.put("dropoutRate",     s.getDropoutRate());
        m.put("meanReliability", s.getMeanReliability());
        m.put("framesTotal",     s.getFramesTotal());
        m.put("framesDetected",  s.getFramesDetected());
        m.put("createdAt",       s.getCreatedAt().toString());
        return m;
    }
}
