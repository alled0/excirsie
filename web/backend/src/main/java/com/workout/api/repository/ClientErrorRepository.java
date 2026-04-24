package com.workout.api.repository;

import com.workout.api.entity.ClientErrorEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ClientErrorRepository extends JpaRepository<ClientErrorEntity, Long> {}
