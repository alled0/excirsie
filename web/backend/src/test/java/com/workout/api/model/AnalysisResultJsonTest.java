package com.workout.api.model;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class AnalysisResultJsonTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void deserializesSnakeCaseModelServiceResponse() throws Exception {
        String json = """
            {
              "success": true,
              "exercise_key": "1",
              "exercise_name": "Bicep Curl",
              "reps_total": 3,
              "reps_left": 1,
              "reps_right": 2,
              "signal_quality": 0.82,
              "dropout_rate": 0.12,
              "mean_reliability": 0.91,
              "unknown_rate": 0.04,
              "aborted_reps": 1,
              "rejected_reps": 2,
              "frames_total": 120,
              "frames_detected": 112,
              "fps_mean": 24.5
            }
            """;

        AnalysisResult result = mapper.readValue(json, AnalysisResult.class);

        assertThat(result.isSuccess()).isTrue();
        assertThat(result.getExerciseKey()).isEqualTo("1");
        assertThat(result.getExerciseName()).isEqualTo("Bicep Curl");
        assertThat(result.getRepsTotal()).isEqualTo(3);
        assertThat(result.getRepsLeft()).isEqualTo(1);
        assertThat(result.getRepsRight()).isEqualTo(2);
        assertThat(result.getSignalQuality()).isEqualTo(0.82);
        assertThat(result.getDropoutRate()).isEqualTo(0.12);
        assertThat(result.getMeanReliability()).isEqualTo(0.91);
        assertThat(result.getUnknownRate()).isEqualTo(0.04);
        assertThat(result.getAbortedReps()).isEqualTo(1);
        assertThat(result.getRejectedReps()).isEqualTo(2);
        assertThat(result.getFramesTotal()).isEqualTo(120);
        assertThat(result.getFramesDetected()).isEqualTo(112);
        assertThat(result.getFpsMean()).isEqualTo(24.5);
    }
}
