package com.workout.api.repository;

import com.workout.api.entity.FeedbackEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface FeedbackRepository extends JpaRepository<FeedbackEntity, Long> {

    List<FeedbackEntity> findAllByOrderByCreatedAtDesc();

    List<FeedbackEntity> findByExerciseKey(String exerciseKey);
}
