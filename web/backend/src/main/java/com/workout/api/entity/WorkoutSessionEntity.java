package com.workout.api.entity;

import com.workout.api.converter.StringListConverter;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "workout_sessions")
public class WorkoutSessionEntity {

    @Id
    @Column(nullable = false, updatable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private AnonymousUserEntity user;

    @Column(nullable = false, length = 20)
    private String exerciseKey;

    @Column(nullable = false, length = 100)
    private String exerciseName;

    @Column(nullable = false, length = 10)
    private String source;   // "upload" or "live"

    private Integer repsTotal   = 0;
    private Integer repsLeft;
    private Integer repsRight;

    @Column(precision = 5, scale = 4)
    private BigDecimal signalQuality;

    @Column(precision = 5, scale = 4)
    private BigDecimal dropoutRate;

    @Column(precision = 5, scale = 4)
    private BigDecimal meanReliability;

    @Column(precision = 5, scale = 4)
    private BigDecimal unknownRate;

    private Integer framesTotal;
    private Integer framesDetected;

    @Column(precision = 6, scale = 2)
    private BigDecimal fpsMean;

    private Integer repsAborted  = 0;
    private Integer repsRejected = 0;

    // Stored as JSON array string: '["cam_too_close","cam_turn_left"]'
    @Column(length = 500)
    @Convert(converter = StringListConverter.class)
    private List<String> cameraIssues = new ArrayList<>();

    @Column(name = "duration_s")
    private Integer durationS;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    private LocalDateTime deletedAt;

    @PrePersist
    void onPersist() {
        if (this.id == null) this.id = UUID.randomUUID();
        this.createdAt = LocalDateTime.now();
    }

    // -- Getters / setters ----------------------------------------------------

    public UUID getId()                              { return id; }
    public void setId(UUID v)                        { this.id = v; }

    public AnonymousUserEntity getUser()             { return user; }
    public void setUser(AnonymousUserEntity v)       { this.user = v; }

    public String getExerciseKey()                   { return exerciseKey; }
    public void setExerciseKey(String v)             { this.exerciseKey = v; }

    public String getExerciseName()                  { return exerciseName; }
    public void setExerciseName(String v)            { this.exerciseName = v; }

    public String getSource()                        { return source; }
    public void setSource(String v)                  { this.source = v; }

    public Integer getRepsTotal()                    { return repsTotal; }
    public void setRepsTotal(Integer v)              { this.repsTotal = v; }

    public Integer getRepsLeft()                     { return repsLeft; }
    public void setRepsLeft(Integer v)               { this.repsLeft = v; }

    public Integer getRepsRight()                    { return repsRight; }
    public void setRepsRight(Integer v)              { this.repsRight = v; }

    public BigDecimal getSignalQuality()             { return signalQuality; }
    public void setSignalQuality(BigDecimal v)       { this.signalQuality = v; }

    public BigDecimal getDropoutRate()               { return dropoutRate; }
    public void setDropoutRate(BigDecimal v)         { this.dropoutRate = v; }

    public BigDecimal getMeanReliability()           { return meanReliability; }
    public void setMeanReliability(BigDecimal v)     { this.meanReliability = v; }

    public BigDecimal getUnknownRate()               { return unknownRate; }
    public void setUnknownRate(BigDecimal v)         { this.unknownRate = v; }

    public Integer getFramesTotal()                  { return framesTotal; }
    public void setFramesTotal(Integer v)            { this.framesTotal = v; }

    public Integer getFramesDetected()               { return framesDetected; }
    public void setFramesDetected(Integer v)         { this.framesDetected = v; }

    public BigDecimal getFpsMean()                   { return fpsMean; }
    public void setFpsMean(BigDecimal v)             { this.fpsMean = v; }

    public Integer getRepsAborted()                  { return repsAborted; }
    public void setRepsAborted(Integer v)            { this.repsAborted = v; }

    public Integer getRepsRejected()                 { return repsRejected; }
    public void setRepsRejected(Integer v)           { this.repsRejected = v; }

    public List<String> getCameraIssues()            { return cameraIssues; }
    public void setCameraIssues(List<String> v)      { this.cameraIssues = v; }

    public Integer getDurationS()                    { return durationS; }
    public void setDurationS(Integer v)              { this.durationS = v; }

    public LocalDateTime getCreatedAt()              { return createdAt; }
    public LocalDateTime getDeletedAt()              { return deletedAt; }
    public void setDeletedAt(LocalDateTime v)        { this.deletedAt = v; }
}
