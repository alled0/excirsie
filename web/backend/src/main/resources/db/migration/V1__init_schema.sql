-- Production schema — designed for PostgreSQL.
-- Local dev uses H2 in PostgreSQL compatibility mode (see application.properties).
--
-- To reset local dev: delete data/workout-dev.mv.db and restart Spring Boot.

-- Drop old single-table schema if it exists from the previous ddl-auto=update setup
DROP TABLE IF EXISTS feedback;


-- ── Users ─────────────────────────────────────────────────────────────────────
-- Anonymous users identified by a UUID token stored in the browser's localStorage.
-- No email, no password. GDPR erasure = rotate the token + set deleted_at.

CREATE TABLE anonymous_users (
    id              UUID         NOT NULL PRIMARY KEY,
    token           UUID         NOT NULL UNIQUE,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP,
    ip_country      VARCHAR(2),          -- coarse geo only, no precise location stored
    user_agent_hash VARCHAR(64)          -- SHA-256 of UA string, not the raw string
);

CREATE INDEX idx_users_token      ON anonymous_users (token);
CREATE INDEX idx_users_created_at ON anonymous_users (created_at);


-- ── Workout sessions ──────────────────────────────────────────────────────────
-- One row per completed analysis — whether from a video upload or a live session.
-- This is the central fact table. Everything else joins back to it.

CREATE TABLE workout_sessions (
    id               UUID         NOT NULL PRIMARY KEY,
    user_id          UUID         NOT NULL REFERENCES anonymous_users(id),

    exercise_key     VARCHAR(20)  NOT NULL,
    exercise_name    VARCHAR(100) NOT NULL,
    source           VARCHAR(10)  NOT NULL,         -- 'upload' | 'live'

    -- Volume
    reps_total       SMALLINT     NOT NULL DEFAULT 0,
    reps_left        SMALLINT,
    reps_right       SMALLINT,

    -- Quantitative quality metrics (0–1 range)
    signal_quality   DECIMAL(5,4),
    dropout_rate     DECIMAL(5,4),
    mean_reliability DECIMAL(5,4),
    unknown_rate     DECIMAL(5,4),

    -- Frame counts
    frames_total     INTEGER,
    frames_detected  INTEGER,
    fps_mean         DECIMAL(6,2),

    -- Rejected / aborted reps (tracker-level signals)
    reps_aborted     SMALLINT     NOT NULL DEFAULT 0,
    reps_rejected    SMALLINT     NOT NULL DEFAULT 0,

    -- Camera position issues at session start — stored as a JSON array string
    -- e.g. '["cam_too_close","cam_turn_left"]'
    camera_issues    VARCHAR(500) NOT NULL DEFAULT '[]',

    duration_s       INTEGER,                        -- live sessions only

    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at       TIMESTAMP                       -- soft-deleted on GDPR erasure
);

CREATE INDEX idx_sessions_user_id       ON workout_sessions (user_id);
CREATE INDEX idx_sessions_exercise      ON workout_sessions (exercise_key);
CREATE INDEX idx_sessions_created_at    ON workout_sessions (created_at);
CREATE INDEX idx_sessions_source        ON workout_sessions (source);
CREATE INDEX idx_sessions_user_exercise ON workout_sessions (user_id, exercise_key, created_at);


-- ── Rep logs ──────────────────────────────────────────────────────────────────
-- One row per completed rep within a session. High-volume table.
-- Gives per-rep fault frequency, tempo trends, and ROM data for model improvement.

CREATE TABLE rep_logs (
    id                  BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    session_id          UUID         NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,

    rep_number          SMALLINT     NOT NULL,
    side                VARCHAR(10)  NOT NULL,       -- 'left' | 'right' | 'center'
    set_number          SMALLINT     NOT NULL DEFAULT 1,

    duration_ms         INTEGER      NOT NULL DEFAULT 0,
    form_score          SMALLINT     NOT NULL DEFAULT 0,  -- 0–100

    angle_min           DECIMAL(6,2) NOT NULL DEFAULT 0,
    angle_max           DECIMAL(6,2) NOT NULL DEFAULT 0,

    -- Detected faults — JSON array of fault key strings
    -- e.g. '["upper_arm_drift","trunk_swing"]'
    faults              VARCHAR(500) NOT NULL DEFAULT '[]',

    -- Score component penalties (0–100 each, lower is better)
    penalty_rom         SMALLINT     NOT NULL DEFAULT 0,
    penalty_tempo       SMALLINT     NOT NULL DEFAULT 0,
    penalty_sway_drift  SMALLINT     NOT NULL DEFAULT 0,
    penalty_asymmetry   SMALLINT     NOT NULL DEFAULT 0,
    penalty_instability SMALLINT     NOT NULL DEFAULT 0,

    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rep_logs_session ON rep_logs (session_id);


-- ── Feedback ──────────────────────────────────────────────────────────────────
-- User rating of a session. The most direct signal for model accuracy.
-- rep_count_accurate = false + user_rep_correction is the ground-truth label
-- that drives model evaluation.

CREATE TABLE feedback (
    id                  BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    session_id          UUID         REFERENCES workout_sessions(id) ON DELETE SET NULL,
    user_id             UUID         REFERENCES anonymous_users(id)  ON DELETE SET NULL,
    exercise_key        VARCHAR(20)  NOT NULL,

    rating              SMALLINT     NOT NULL,       -- 1–5 stars
    rep_count_accurate  BOOLEAN      NOT NULL,
    user_rep_correction SMALLINT,                    -- their count if they said inaccurate
    comment             VARCHAR(2000),

    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feedback_session   ON feedback (session_id);
CREATE INDEX idx_feedback_exercise  ON feedback (exercise_key);
CREATE INDEX idx_feedback_created   ON feedback (created_at);


-- ── User events ───────────────────────────────────────────────────────────────
-- Funnel analytics — page views, exercise selections, session starts/ends, etc.
-- Append-only. Used to understand drop-off points and feature usage.

CREATE TABLE user_events (
    id          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    user_id     UUID         NOT NULL REFERENCES anonymous_users(id) ON DELETE CASCADE,
    session_id  UUID         REFERENCES workout_sessions(id) ON DELETE SET NULL,

    event_type  VARCHAR(50)  NOT NULL,
    -- JSON object with event-specific properties, e.g. {"exerciseKey":"1","fileSize":1400000}
    properties  VARCHAR(2000) NOT NULL DEFAULT '{}',

    occurred_at TIMESTAMP    NOT NULL,               -- client-side timestamp
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_user_id  ON user_events (user_id, occurred_at);
CREATE INDEX idx_events_type     ON user_events (event_type, occurred_at);
CREATE INDEX idx_events_session  ON user_events (session_id);


-- ── Client errors ─────────────────────────────────────────────────────────────
-- Angular runtime errors and failed API calls reported by the client.
-- Helps identify systematic failures before they become user complaints.

CREATE TABLE client_errors (
    id          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    user_id     UUID         REFERENCES anonymous_users(id)  ON DELETE SET NULL,
    session_id  UUID         REFERENCES workout_sessions(id) ON DELETE SET NULL,

    error_type  VARCHAR(50)  NOT NULL,
    message     VARCHAR(500),
    stack_hash  VARCHAR(64),                         -- SHA-256 of stack trace for dedup
    http_status SMALLINT,

    occurred_at TIMESTAMP    NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_errors_user_id ON client_errors (user_id);
CREATE INDEX idx_errors_type    ON client_errors (error_type, occurred_at);
CREATE INDEX idx_errors_session ON client_errors (session_id);
