package com.workout.api.converter;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

import java.util.Collections;
import java.util.List;

/**
 * Stores List<String> as a JSON array string in the database.
 * Works identically with H2 (dev) and PostgreSQL (prod).
 */
@Converter
public class StringListConverter implements AttributeConverter<List<String>, String> {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final TypeReference<List<String>> LIST_TYPE = new TypeReference<>() {};

    @Override
    public String convertToDatabaseColumn(List<String> list) {
        if (list == null || list.isEmpty()) return "[]";
        try {
            return MAPPER.writeValueAsString(list);
        } catch (Exception e) {
            return "[]";
        }
    }

    @Override
    public List<String> convertToEntityAttribute(String json) {
        if (json == null || json.isBlank()) return Collections.emptyList();
        try {
            return MAPPER.readValue(json, LIST_TYPE);
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }
}
