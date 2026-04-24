package com.workout.api.dto;

import java.math.BigDecimal;
import java.util.List;

public class SaveSessionRequest {

    public String exerciseKey;
    public String exerciseName;
    public String source;

    public Integer repsTotal;
    public Integer repsLeft;
    public Integer repsRight;

    public BigDecimal signalQuality;
    public BigDecimal dropoutRate;
    public BigDecimal meanReliability;
    public BigDecimal unknownRate;

    public Integer framesTotal;
    public Integer framesDetected;
    public BigDecimal fpsMean;

    public Integer repsAborted;
    public Integer repsRejected;

    public List<String> cameraIssues;

    public Integer durationS;

    public List<RepLogDto> repLogs;

    public static class RepLogDto {
        public Integer repNumber;
        public String  side;
        public Integer setNumber;
        public Integer durationMs;
        public Integer formScore;
        public Double  angleMin;
        public Double  angleMax;
        public List<String> faults;
        public Integer penaltyRom;
        public Integer penaltyTempo;
        public Integer penaltySwayDrift;
        public Integer penaltyAsymmetry;
        public Integer penaltyInstability;
    }
}
