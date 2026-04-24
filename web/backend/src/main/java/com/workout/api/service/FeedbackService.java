package com.workout.api.service;

import com.workout.api.entity.FeedbackEntity;
import com.workout.api.model.FeedbackRequest;
import com.workout.api.repository.AnonymousUserRepository;
import com.workout.api.repository.FeedbackRepository;
import com.workout.api.repository.WorkoutSessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class FeedbackService {

    private final FeedbackRepository       feedbackRepo;
    private final AnonymousUserRepository  userRepo;
    private final WorkoutSessionRepository sessionRepo;

    public FeedbackService(FeedbackRepository feedbackRepo,
                           AnonymousUserRepository userRepo,
                           WorkoutSessionRepository sessionRepo) {
        this.feedbackRepo = feedbackRepo;
        this.userRepo     = userRepo;
        this.sessionRepo  = sessionRepo;
    }

    @Transactional
    public FeedbackEntity save(UUID userId, FeedbackRequest req) {
        FeedbackEntity entity = new FeedbackEntity();

        if (userId != null) {
            userRepo.findById(userId).ifPresent(entity::setUser);
        }
        if (req.getSessionId() != null) {
            sessionRepo.findById(req.getSessionId()).ifPresent(entity::setSession);
        }

        entity.setExerciseKey(req.getExerciseKey());
        entity.setRating(req.getRating());
        entity.setRepCountAccurate(req.getRepCountAccurate());
        entity.setUserRepCorrection(req.getUserRepCorrection());
        entity.setComment(req.getComment());

        return feedbackRepo.save(entity);
    }
}
