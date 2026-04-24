package com.workout.api.controller;

import com.workout.api.model.AnalysisResult;
import com.workout.api.model.ExerciseInfo;
import com.workout.api.service.ModelService;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class AnalysisController {

    private final ModelService modelService;

    public AnalysisController(ModelService modelService) {
        this.modelService = modelService;
    }

    @GetMapping("/exercises")
    public ResponseEntity<List<ExerciseInfo>> getExercises() {
        List<ExerciseInfo> exercises = modelService.fetchExercises();
        return ResponseEntity.ok(exercises);
    }

    @PostMapping("/analyze")
    public ResponseEntity<?> analyze(
        @RequestParam("video") MultipartFile video,
        @RequestParam("exerciseKey") String exerciseKey
    ) {
        if (video.isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "No video file provided"));
        }

        try {
            AnalysisResult result = modelService.analyse(video, exerciseKey);
            return ResponseEntity.ok(result);
        } catch (IOException e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("error", "Failed to read the uploaded file: " + e.getMessage()));
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("error", "Analysis failed: " + e.getMessage()));
        }
    }
}
