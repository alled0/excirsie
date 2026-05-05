package com.workout.api.model;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * Metrics returned after analysing a workout video.
 * Null fields (e.g. repsLeft on a unilateral exercise) are omitted from the JSON.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class AnalysisResult {

    private boolean success;
    @JsonAlias("exercise_key")
    private String exerciseKey;
    @JsonAlias("exercise_name")
    private String exerciseName;
    @JsonAlias("reps_total")
    private int repsTotal;
    @JsonAlias("reps_left")
    private Integer repsLeft;
    @JsonAlias("reps_right")
    private Integer repsRight;
    @JsonAlias("signal_quality")
    private double signalQuality;
    @JsonAlias("dropout_rate")
    private double dropoutRate;
    @JsonAlias("mean_reliability")
    private double meanReliability;
    @JsonAlias("unknown_rate")
    private double unknownRate;
    @JsonAlias("aborted_reps")
    private int abortedReps;
    @JsonAlias("rejected_reps")
    private int rejectedReps;
    @JsonAlias("frames_total")
    private int framesTotal;
    @JsonAlias("frames_detected")
    private int framesDetected;
    @JsonAlias("fps_mean")
    private double fpsMean;

    // -- Getters and setters --------------------------------------------------

    public boolean isSuccess()                  { return success; }
    public void setSuccess(boolean v)           { this.success = v; }

    public String getExerciseKey()              { return exerciseKey; }
    public void setExerciseKey(String v)        { this.exerciseKey = v; }

    public String getExerciseName()             { return exerciseName; }
    public void setExerciseName(String v)       { this.exerciseName = v; }

    public int getRepsTotal()                   { return repsTotal; }
    public void setRepsTotal(int v)             { this.repsTotal = v; }

    public Integer getRepsLeft()                { return repsLeft; }
    public void setRepsLeft(Integer v)          { this.repsLeft = v; }

    public Integer getRepsRight()               { return repsRight; }
    public void setRepsRight(Integer v)         { this.repsRight = v; }

    public double getSignalQuality()            { return signalQuality; }
    public void setSignalQuality(double v)      { this.signalQuality = v; }

    public double getDropoutRate()              { return dropoutRate; }
    public void setDropoutRate(double v)        { this.dropoutRate = v; }

    public double getMeanReliability()          { return meanReliability; }
    public void setMeanReliability(double v)    { this.meanReliability = v; }

    public double getUnknownRate()              { return unknownRate; }
    public void setUnknownRate(double v)        { this.unknownRate = v; }

    public int getAbortedReps()                 { return abortedReps; }
    public void setAbortedReps(int v)           { this.abortedReps = v; }

    public int getRejectedReps()                { return rejectedReps; }
    public void setRejectedReps(int v)          { this.rejectedReps = v; }

    public int getFramesTotal()                 { return framesTotal; }
    public void setFramesTotal(int v)           { this.framesTotal = v; }

    public int getFramesDetected()              { return framesDetected; }
    public void setFramesDetected(int v)        { this.framesDetected = v; }

    public double getFpsMean()                  { return fpsMean; }
    public void setFpsMean(double v)            { this.fpsMean = v; }
}
