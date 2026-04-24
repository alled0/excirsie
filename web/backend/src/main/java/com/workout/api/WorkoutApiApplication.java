package com.workout.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

import com.workout.api.config.AppProperties;

@SpringBootApplication
@EnableConfigurationProperties(AppProperties.class)
public class WorkoutApiApplication {

    public static void main(String[] args) {
        SpringApplication.run(WorkoutApiApplication.class, args);
    }
}
