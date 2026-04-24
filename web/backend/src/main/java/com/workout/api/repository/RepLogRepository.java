package com.workout.api.repository;

import com.workout.api.entity.RepLogEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface RepLogRepository extends JpaRepository<RepLogEntity, Long> {

    List<RepLogEntity> findBySessionIdOrderByRepNumber(UUID sessionId);
}
