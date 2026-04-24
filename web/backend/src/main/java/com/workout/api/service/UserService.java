package com.workout.api.service;

import com.workout.api.entity.AnonymousUserEntity;
import com.workout.api.repository.AnonymousUserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.util.UUID;

@Service
public class UserService {

    private final AnonymousUserRepository repo;

    public UserService(AnonymousUserRepository repo) {
        this.repo = repo;
    }

    /**
     * Resolve a token from localStorage into an internal user.
     * Creates a new user if the token is not found.
     * Updates last_seen_at on every call.
     *
     * Returns a two-element array: [entity, isNew]
     */
    @Transactional
    public Object[] resolveOrCreate(UUID token) {
        Optional<AnonymousUserEntity> existing = repo.findByTokenAndDeletedAtIsNull(token);

        if (existing.isPresent()) {
            AnonymousUserEntity user = existing.get();
            repo.save(user);  // triggers @PreUpdate → updates last_seen_at
            return new Object[]{ user, false };
        }

        AnonymousUserEntity user = new AnonymousUserEntity();
        user.setToken(token);
        repo.save(user);
        return new Object[]{ user, true };
    }

    @Transactional
    public void gdprErase(UUID token) {
        repo.findByTokenAndDeletedAtIsNull(token).ifPresent(user -> {
            user.setToken(UUID.randomUUID());   // revoke the token immediately
            user.setDeletedAt(java.time.LocalDateTime.now());
            repo.save(user);
        });
    }
}
