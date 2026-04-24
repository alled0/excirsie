package com.workout.api.model;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.UUID;

public class FeedbackRequest {

    private UUID sessionId;         // links feedback to the specific session

    @NotBlank
    private String exerciseKey;

    @Min(1)
    @Max(5)
    private int rating;

    private Boolean repCountAccurate;

    // What the user thinks the real rep count was (only meaningful when repCountAccurate = false)
    private Integer userRepCorrection;

    @Size(max = 2000)
    private String comment;

    // -- Getters and setters --------------------------------------------------

    public UUID getSessionId()                      { return sessionId; }
    public void setSessionId(UUID v)                { this.sessionId = v; }

    public String getExerciseKey()                  { return exerciseKey; }
    public void setExerciseKey(String v)            { this.exerciseKey = v; }

    public int getRating()                          { return rating; }
    public void setRating(int v)                    { this.rating = v; }

    public Boolean getRepCountAccurate()            { return repCountAccurate; }
    public void setRepCountAccurate(Boolean v)      { this.repCountAccurate = v; }

    public Integer getUserRepCorrection()           { return userRepCorrection; }
    public void setUserRepCorrection(Integer v)     { this.userRepCorrection = v; }

    public String getComment()                      { return comment; }
    public void setComment(String v)                { this.comment = v; }
}
