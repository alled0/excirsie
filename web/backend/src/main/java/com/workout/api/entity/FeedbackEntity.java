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
@Table(name = "feedback")
public class FeedbackEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Nullable so feedback survives if the session or user is soft-deleted / erased
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_id")
    private WorkoutSessionEntity session;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private AnonymousUserEntity user;

    @Column(nullable = false, length = 20)
    private String exerciseKey;

    private Integer rating;               // 1–5

    private Boolean repCountAccurate;

    // What the user thinks the real count was (only set if repCountAccurate = false)
    private Integer userRepCorrection;

    @Column(length = 2000)
    private String comment;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onPersist() {
        this.createdAt = LocalDateTime.now();
    }

    // -- Getters / setters ----------------------------------------------------

    public Long getId()                                  { return id; }

    public WorkoutSessionEntity getSession()             { return session; }
    public void setSession(WorkoutSessionEntity v)       { this.session = v; }

    public AnonymousUserEntity getUser()                 { return user; }
    public void setUser(AnonymousUserEntity v)           { this.user = v; }

    public String getExerciseKey()                       { return exerciseKey; }
    public void setExerciseKey(String v)                 { this.exerciseKey = v; }

    public Integer getRating()                           { return rating; }
    public void setRating(Integer v)                     { this.rating = v; }

    public Boolean getRepCountAccurate()                 { return repCountAccurate; }
    public void setRepCountAccurate(Boolean v)           { this.repCountAccurate = v; }

    public Integer getUserRepCorrection()                { return userRepCorrection; }
    public void setUserRepCorrection(Integer v)          { this.userRepCorrection = v; }

    public String getComment()                           { return comment; }
    public void setComment(String v)                     { this.comment = v; }

    public LocalDateTime getCreatedAt()                  { return createdAt; }
}
