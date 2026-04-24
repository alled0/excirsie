package com.workout.api.repository;

import com.workout.api.entity.WorkoutSessionEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface WorkoutSessionRepository extends JpaRepository<WorkoutSessionEntity, UUID> {

    List<WorkoutSessionEntity> findByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(UUID userId);
}
