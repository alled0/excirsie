package com.workout.api.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "anonymous_users")
public class AnonymousUserEntity {

    @Id
    @Column(nullable = false, updatable = false)
    private UUID id;

    // The token lives in the user's localStorage. Rotating it on erasure revokes access.
    @Column(nullable = false, unique = true)
    private UUID token;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(nullable = false)
    private LocalDateTime lastSeenAt;

    private LocalDateTime deletedAt;

    @Column(length = 2)
    private String ipCountry;

    @Column(length = 64)
    private String userAgentHash;

    @PrePersist
    void onPersist() {
        if (this.id    == null) this.id    = UUID.randomUUID();
        if (this.token == null) this.token = UUID.randomUUID();
        LocalDateTime now = LocalDateTime.now();
        this.createdAt  = now;
        this.lastSeenAt = now;
    }

    @PreUpdate
    void onUpdate() {
        this.lastSeenAt = LocalDateTime.now();
    }

    // -- Getters / setters ----------------------------------------------------

    public UUID getId()                          { return id; }
    public void setId(UUID v)                    { this.id = v; }

    public UUID getToken()                       { return token; }
    public void setToken(UUID v)                 { this.token = v; }

    public LocalDateTime getCreatedAt()          { return createdAt; }
    public LocalDateTime getLastSeenAt()         { return lastSeenAt; }
    public void setLastSeenAt(LocalDateTime v)   { this.lastSeenAt = v; }

    public LocalDateTime getDeletedAt()          { return deletedAt; }
    public void setDeletedAt(LocalDateTime v)    { this.deletedAt = v; }

    public String getIpCountry()                 { return ipCountry; }
    public void setIpCountry(String v)           { this.ipCountry = v; }

    public String getUserAgentHash()             { return userAgentHash; }
    public void setUserAgentHash(String v)       { this.userAgentHash = v; }
}
