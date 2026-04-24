package com.workout.api.controller;

import com.workout.api.entity.AnonymousUserEntity;
import com.workout.api.service.UserService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    /**
     * Called on every app load. Creates the user if new, refreshes last_seen_at if returning.
     * Angular stores the returned token in localStorage and the userId for subsequent requests.
     */
    @PostMapping("/resolve")
    public ResponseEntity<Map<String, Object>> resolve(@RequestBody Map<String, String> body) {
        String rawToken = body.get("token");
        if (rawToken == null || rawToken.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "token is required"));
        }

        UUID token;
        try {
            token = UUID.fromString(rawToken);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", "invalid token format"));
        }

        Object[] result  = userService.resolveOrCreate(token);
        AnonymousUserEntity user = (AnonymousUserEntity) result[0];
        boolean isNew    = (boolean) result[1];

        return ResponseEntity.ok(Map.of(
            "userId", user.getId().toString(),
            "token",  user.getToken().toString(),
            "isNew",  isNew
        ));
    }

    /**
     * GDPR erasure — rotates the token and soft-deletes the user.
     * All sessions remain in the DB for aggregate analytics but are unlinkable after erasure.
     */
    @DeleteMapping("/{token}")
    public ResponseEntity<Void> erase(@PathVariable String token) {
        try {
            userService.gdprErase(UUID.fromString(token));
        } catch (IllegalArgumentException ignored) {
            // invalid UUID — nothing to erase
        }
        return ResponseEntity.noContent().build();
    }
}
