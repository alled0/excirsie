package com.workout.api.dto;

import java.time.LocalDateTime;
import java.util.UUID;

public class ReportErrorRequest {

    public UUID          sessionId;
    public String        errorType;
    public String        message;
    public String        stackHash;
    public Integer       httpStatus;
    public LocalDateTime occurredAt;
}
