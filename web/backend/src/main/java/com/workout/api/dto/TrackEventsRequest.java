package com.workout.api.dto;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

public class TrackEventsRequest {

    public List<EventDto> events;

    public static class EventDto {
        public String        eventType;
        public UUID          sessionId;
        public String        properties; // raw JSON string
        public LocalDateTime occurredAt;
    }
}
