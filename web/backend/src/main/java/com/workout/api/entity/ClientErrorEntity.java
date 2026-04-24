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
@Table(name = "client_errors")
public class ClientErrorEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private AnonymousUserEntity user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_id")
    private WorkoutSessionEntity session;

    @Column(nullable = false, length = 50)
    private String errorType;

    @Column(length = 500)
    private String message;

    @Column(length = 64)
    private String stackHash;

    private Integer httpStatus;

    @Column(nullable = false)
    private LocalDateTime occurredAt;

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

    public String getErrorType()                         { return errorType; }
    public void setErrorType(String v)                   { this.errorType = v; }

    public String getMessage()                           { return message; }
    public void setMessage(String v)                     { this.message = v; }

    public String getStackHash()                         { return stackHash; }
    public void setStackHash(String v)                   { this.stackHash = v; }

    public Integer getHttpStatus()                       { return httpStatus; }
    public void setHttpStatus(Integer v)                 { this.httpStatus = v; }

    public LocalDateTime getOccurredAt()                 { return occurredAt; }
    public void setOccurredAt(LocalDateTime v)           { this.occurredAt = v; }

    public LocalDateTime getCreatedAt()                  { return createdAt; }
}
