package com.workout.api.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

@Entity
@Table(name = "user_events")
public class UserEventEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private AnonymousUserEntity user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_id")
    private WorkoutSessionEntity session;

    @Column(nullable = false, length = 50)
    private String eventType;

    // JSON object stored as text — e.g. {"exerciseKey":"1","fileSize":1400000}
    @Column(length = 2000)
    private String properties = "{}";

    @Column(nullable = false)
    private LocalDateTime occurredAt;   // client-side timestamp

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onPersist() {
        this.createdAt = LocalDateTime.now();
    }

    // -- Getters / setters ----------------------------------------------------

    public Long getId()                                  { return id; }

    public AnonymousUserEntity getUser()                 { return user; }
    public void setUser(AnonymousUserEntity v)           { this.user = v; }

    public WorkoutSessionEntity getSession()             { return session; }
    public void setSession(WorkoutSessionEntity v)       { this.session = v; }

    public String getEventType()                         { return eventType; }
    public void setEventType(String v)                   { this.eventType = v; }

    public String getProperties()                        { return properties; }
    public void setProperties(String v)                  { this.properties = v; }

    public LocalDateTime getOccurredAt()                 { return occurredAt; }
    public void setOccurredAt(LocalDateTime v)           { this.occurredAt = v; }

    public LocalDateTime getCreatedAt()                  { return createdAt; }
}
