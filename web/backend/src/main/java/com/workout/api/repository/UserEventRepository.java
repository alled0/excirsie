package com.workout.api.repository;

import com.workout.api.entity.UserEventEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserEventRepository extends JpaRepository<UserEventEntity, Long> {}
