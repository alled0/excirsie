package com.workout.api.entity;

import com.workout.api.converter.StringListConverter;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "rep_logs")
public class RepLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "session_id", nullable = false)
    private WorkoutSessionEntity session;

    private Integer repNumber;

    @Column(length = 10)
    private String side;       // "left" | "right" | "center"

    private Integer setNumber   = 1;
    private Integer durationMs  = 0;
    private Integer formScore   = 0;  // 0–100

    @Column(precision = 6, scale = 2)
    private BigDecimal angleMin = BigDecimal.ZERO;

    @Column(precision = 6, scale = 2)
    private BigDecimal angleMax = BigDecimal.ZERO;

    // Fault keys detected during this rep — e.g. ["upper_arm_drift","trunk_swing"]
    @Column(length = 500)
    @Convert(converter = StringListConverter.class)
    private List<String> faults = new ArrayList<>();

    private Integer penaltyRom         = 0;
    private Integer penaltyTempo       = 0;
    private Integer penaltySwayDrift   = 0;
    private Integer penaltyAsymmetry   = 0;
    private Integer penaltyInstability = 0;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onPersist() {
        this.createdAt = LocalDateTime.now();
    }

    // -- Getters / setters ----------------------------------------------------

    public Long getId()                              { return id; }

    public WorkoutSessionEntity getSession()         { return session; }
    public void setSession(WorkoutSessionEntity v)   { this.session = v; }

    public Integer getRepNumber()                    { return repNumber; }
    public void setRepNumber(Integer v)              { this.repNumber = v; }

    public String getSide()                          { return side; }
    public void setSide(String v)                    { this.side = v; }

    public Integer getSetNumber()                    { return setNumber; }
    public void setSetNumber(Integer v)              { this.setNumber = v; }

    public Integer getDurationMs()                   { return durationMs; }
    public void setDurationMs(Integer v)             { this.durationMs = v; }

    public Integer getFormScore()                    { return formScore; }
    public void setFormScore(Integer v)              { this.formScore = v; }

    public BigDecimal getAngleMin()                  { return angleMin; }
    public void setAngleMin(BigDecimal v)            { this.angleMin = v; }

    public BigDecimal getAngleMax()                  { return angleMax; }
    public void setAngleMax(BigDecimal v)            { this.angleMax = v; }

    public List<String> getFaults()                  { return faults; }
    public void setFaults(List<String> v)            { this.faults = v; }

    public Integer getPenaltyRom()                   { return penaltyRom; }
    public void setPenaltyRom(Integer v)             { this.penaltyRom = v; }

    public Integer getPenaltyTempo()                 { return penaltyTempo; }
    public void setPenaltyTempo(Integer v)           { this.penaltyTempo = v; }

    public Integer getPenaltySwayDrift()             { return penaltySwayDrift; }
    public void setPenaltySwayDrift(Integer v)       { this.penaltySwayDrift = v; }

    public Integer getPenaltyAsymmetry()             { return penaltyAsymmetry; }
    public void setPenaltyAsymmetry(Integer v)       { this.penaltyAsymmetry = v; }

    public Integer getPenaltyInstability()           { return penaltyInstability; }
    public void setPenaltyInstability(Integer v)     { this.penaltyInstability = v; }

    public LocalDateTime getCreatedAt()              { return createdAt; }
}
