package com.workout.api.service;

import com.workout.api.config.AppProperties;
import com.workout.api.model.AnalysisResult;
import com.workout.api.model.ExerciseInfo;

import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;

@Service
public class ModelService {

    private final RestTemplate restTemplate;
    private final String serviceUrl;

    public ModelService(AppProperties props) {
        this.serviceUrl = props.getUrl();

        // Generous timeout — analysing a long video can take a few minutes
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(300_000);

        this.restTemplate = new RestTemplate(factory);
    }

    public List<ExerciseInfo> fetchExercises() {
        return restTemplate.exchange(
            serviceUrl + "/exercises",
            HttpMethod.GET,
            null,
            new ParameterizedTypeReference<List<ExerciseInfo>>() {}
        ).getBody();
    }

    public AnalysisResult analyse(MultipartFile video, String exerciseKey) throws IOException {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        // Wrap the bytes so RestTemplate sends a proper filename in the multipart part
        ByteArrayResource fileResource = new ByteArrayResource(video.getBytes()) {
            @Override
            public String getFilename() {
                return video.getOriginalFilename() != null
                    ? video.getOriginalFilename()
                    : "upload.mp4";
            }
        };

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("video", fileResource);
        body.add("exercise_key", exerciseKey);

        return restTemplate.postForObject(
            serviceUrl + "/process",
            new HttpEntity<>(body, headers),
            AnalysisResult.class
        );
    }
}
