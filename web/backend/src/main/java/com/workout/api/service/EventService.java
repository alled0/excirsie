package com.workout.api.service;

import com.workout.api.dto.TrackEventsRequest;
import com.workout.api.entity.AnonymousUserEntity;
import com.workout.api.entity.UserEventEntity;
import com.workout.api.repository.AnonymousUserRepository;
import com.workout.api.repository.UserEventRepository;
import com.workout.api.repository.WorkoutSessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class EventService {

    private final UserEventRepository      eventRepo;
    private final AnonymousUserRepository  userRepo;
    private final WorkoutSessionRepository sessionRepo;

    public EventService(UserEventRepository eventRepo,
                        AnonymousUserRepository userRepo,
                        WorkoutSessionRepository sessionRepo) {
        this.eventRepo   = eventRepo;
        this.userRepo    = userRepo;
        this.sessionRepo = sessionRepo;
    }

    @Transactional
    public int saveAll(UUID userId, List<TrackEventsRequest.EventDto> dtos) {
        AnonymousUserEntity user = userRepo.findById(userId).orElse(null);
        if (user == null) return 0;

        for (TrackEventsRequest.EventDto dto : dtos) {
            UserEventEntity event = new UserEventEntity();
            event.setUser(user);
            event.setEventType(dto.eventType);
            event.setProperties(dto.properties != null ? dto.properties : "{}");
            event.setOccurredAt(dto.occurredAt != null ? dto.occurredAt : java.time.LocalDateTime.now());

            if (dto.sessionId != null) {
                sessionRepo.findById(dto.sessionId).ifPresent(event::setSession);
            }
            eventRepo.save(event);
        }
        return dtos.size();
    }
}
