package com.workout.api.repository;

import com.workout.api.entity.AnonymousUserEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface AnonymousUserRepository extends JpaRepository<AnonymousUserEntity, UUID> {

    Optional<AnonymousUserEntity> findByTokenAndDeletedAtIsNull(UUID token);
}
