# Taharrak / FormCheck — Complete Project Report

**Date:** April 2026  
**Status:** Active development — CLI app production-ready, web app in integration phase

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [Core CLI Application](#3-core-cli-application)
   - 3.1 Entry Point
   - 3.2 Application State Machine
   - 3.3 Supported Exercises
   - 3.4 Live Frame Processing Pipeline
   - 3.5 Rep Tracking & FSM
   - 3.6 Form Scoring
   - 3.7 Correction Engine
   - 3.8 Pose Smoothing
   - 3.9 Trust & Recovery System
   - 3.10 UI & Messages
   - 3.11 Persistence (SQLite)
   - 3.12 Configuration System
4. [Web Application](#4-web-application)
   - 4.1 Architecture Overview
   - 4.2 Python Model Service (FastAPI)
   - 4.3 Spring Boot Backend
   - 4.4 Angular Frontend
   - 4.5 Data Flow — Video Upload
   - 4.6 Data Flow — Live Camera
   - 4.7 User Identity & GDPR
5. [Database Schema (Production)](#5-database-schema-production)
6. [API Reference](#6-api-reference)
7. [Test Coverage](#7-test-coverage)
8. [Known Issues & Bugs Fixed](#8-known-issues--bugs-fixed)
9. [Configuration Reference](#9-configuration-reference)
10. [Deployment Guide](#10-deployment-guide)
11. [Data Strategy](#11-data-strategy)
12. [Development History](#12-development-history)
13. [What to Build Next](#13-what-to-build-next)

---

## 1. Project Overview

**Taharrak** (Arabic: تحرك — "move") is an AI workout form analysis platform in two layers:

### Layer 1 — Local CLI App
Runs entirely on your laptop. No internet, no account. Point a webcam at yourself,
press a number to select your exercise, and get:
- Real-time rep counting (left and right side independently)
- Per-rep form score 0–100
- One live coaching cue per frame (priority-ranked, never overwhelming)
- Voice feedback via text-to-speech
- Bilingual HUD (English + Arabic)
- Full session history in local SQLite

### Layer 2 — Web App (FormCheck)
A browser-based interface so anyone can try the model without installing anything:
- Upload a workout video → get rep count + quality metrics
- Use live camera → get real-time form feedback in the browser
- All sessions saved to a structured database
- User feedback collected to improve the model over time

### Core Technology
- **Pose detection:** MediaPipe BlazePose (33 body landmarks, ~30fps)
- **Smoothing:** One Euro Filter (adaptive low-pass, per landmark axis)
- **Rep logic:** Per-side finite state machines + kinematics-based phase detection
- **Form scoring:** Rule-based penalty system (ROM, swing, drift, tempo)
- **Coaching:** 4-tier priority correction engine, one-cue-per-frame policy
- **Languages:** Python (CLI + model service), Java/Spring Boot (API), TypeScript/Angular (frontend)

---

## 2. Repository Structure

```
excirsie/
│
├── bicep_curl_counter.py          Main CLI entry point (624 lines)
├── requirements.txt               Python dependencies
├── config.json                    User-configurable thresholds
├── DEVLOG.md                      Full development history
├── CODEBASE.md                    Quick reference for contributors
├── PROJECT_REPORT.md              This document
│
├── taharrak/                      Core Python package
│   ├── __init__.py
│   ├── tracker.py                 RepTracker, smoothers, trust gates (1,217 lines)
│   ├── analysis.py                Pose analysis, quality detection, message building (390 lines)
│   ├── correction.py              CorrectionEngine, fault prioritisation (275 lines)
│   ├── database.py                SQLite schema & persistence (184 lines)
│   ├── session.py                 CSV & event log export (76 lines)
│   ├── ui.py                      All OpenCV screen renderers (750+ lines)
│   ├── messages.py                EN/AR message dictionaries + Arabic PIL renderer (291 lines)
│   ├── eval.py                    Offline video replay harness (369 lines)
│   └── exercises/
│       ├── __init__.py            Exercise registry
│       ├── base.py                Exercise & TechniqueProfile dataclasses
│       ├── bicep_curl.py
│       ├── shoulder_press.py
│       ├── lateral_raise.py
│       ├── tricep_extension.py
│       └── squat.py
│
├── tests/                         213 tests, all passing
│   ├── test_correction_engine.py
│   ├── test_technique_runtime.py
│   ├── test_live_trust.py
│   ├── test_gating.py
│   ├── test_reason_logging.py
│   ├── test_eval_metrics.py
│   ├── test_fsm.py
│   ├── test_camera_gate.py
│   ├── test_smoother.py
│   └── ... (6 more files)
│
└── web/                           Web application
    ├── SETUP.md
    ├── start-dev.ps1              One-click dev startup script
    ├── docker-compose.yml
    ├── nginx.conf
    ├── model-service/             Python FastAPI (stateless analysis)
    │   ├── main.py
    │   ├── requirements.txt
    │   └── Dockerfile
    ├── backend/                   Java Spring Boot (persistence, API gateway)
    │   ├── pom.xml
    │   └── src/main/java/com/workout/api/
    │       ├── config/
    │       ├── controller/
    │       ├── converter/
    │       ├── dto/
    │       ├── entity/
    │       ├── model/
    │       ├── repository/
    │       └── service/
    └── frontend/                  Angular 17 (standalone components, Tailwind CSS)
        └── src/app/
            ├── interceptors/
            ├── models/
            ├── pages/
            │   ├── home/
            │   ├── analyze/
            │   ├── camera/
            │   ├── results/
            │   └── history/
            └── services/
```

---

## 3. Core CLI Application

### 3.1 Entry Point

**File:** `bicep_curl_counter.py`

Owns the camera loop and application state machine. Initialises MediaPipe in VIDEO
running mode (single model instance, frame timestamps for consistent filtering),
creates trackers, smoother, trust gate, tracking guard, and voice engine, then runs
the main `while True` loop reading frames from `cv2.VideoCapture`.

**CLI flags:**
```
--camera INT      Camera device index (default 0)
--reps INT        Override target reps per set
--no-voice        Disable TTS
--no-mirror       Disable horizontal flip
--seg             Enable MediaPipe segmentation (background blur)
--rest INT        Override rest timer duration in seconds
--lang {en,ar}    UI language
```

### 3.2 Application State Machine

```
EXERCISE_SELECT  ──H──▶  HISTORY (browse past sessions, ESC to return)
      │
   1-5 key
      ▼
WEIGHT_INPUT     (UP/DOWN adjust weight, SPACE/ENTER confirm)
      │
   confirm
      ▼
CALIBRATION      (stand ~1.5m away, raise arms; waits for GOOD visibility)
      │           Camera feedback shown live: too close, too far, turn left/right, etc.
   SPACE
      ▼
COUNTDOWN        (3 → 2 → 1 → GO)
      │
   auto
      ▼
WORKOUT ◀────────────────────────────────┐
      │                                  │
   S key / target reps hit           SPACE / timer
      ▼                                  │
REST TIMER ──────────────────────────────┘
      │
   last set done
      ▼
SUMMARY          (stats, rating S/A/B/C, symmetry, fatigue warning — auto-closes 12s)
```

**Key keyboard controls during WORKOUT:**
| Key | Action |
|-----|--------|
| S | End current set, start rest |
| R | Reset current set (keep session) |
| Q | Finish session, go to summary |
| L | Toggle language (EN ↔ AR) |
| M | Toggle mirror mode |
| W | Toggle warmup mode |

### 3.3 Supported Exercises

| Key | Name | Tracking | Angle decreases | Key joints monitored |
|-----|------|----------|-----------------|---------------------|
| 1 | Bicep Curl | Bilateral | ✓ (curl) | shoulder, elbow, wrist |
| 2 | Shoulder Press | Bilateral | ✗ (press up) | shoulder, elbow, wrist |
| 3 | Lateral Raise | Bilateral | ✗ (raise up) | shoulder, elbow, wrist |
| 4 | Tricep Extension | Bilateral | ✗ (extend up) | shoulder, elbow, wrist |
| 5 | Squat | Single (right) | ✓ (squat down) | hip, knee, ankle |

**Adding a new exercise:**
1. Create `taharrak/exercises/my_exercise.py` — define one `Exercise` frozen dataclass
2. Import it in `taharrak/exercises/__init__.py` and add to `EXERCISES` dict with a new key
3. Nothing else in the codebase needs to change

### 3.4 Live Frame Processing Pipeline

```
Camera frame (BGR)
      │
cv2.cvtColor → RGB
      │
mp.Image (SRGB format)
      │
PoseLandmarker.detect_for_video(frame, timestamp_ms)
      │
      ├── No landmarks detected?
      │       └── tr.update_quality("LOST") for all trackers
      │           HUD shows: "Move into frame" / camera feedback
      │
      └── Landmarks detected (33 points with x,y,z,visibility,presence)
              │
      OneEuroLandmarkSmoother.smooth()
              │  filters x,y,z per landmark (99 independent filters)
              │  visibility kept RAW — filtering would delay LOST detection
              │
      det_quality_ex(lm, exercise, cfg)
              │  returns (left_quality, right_quality) ∈ {GOOD, WEAK, LOST}
              │  uses joint_reliability = min(visibility, presence) per joint
              │
      LiveTrustGate.update(qualities, recovering)
              │  returns LiveTrustState
              │  render_allowed   → draw skeleton overlays
              │  counting_allowed → update rep FSMs
              │  coaching_allowed → show form cues
              │
      [for each tracker side]
      RepTracker.update_quality(raw_quality)
              │  ConfidenceSmoother (10-frame majority vote)
              │  recovery gate: suppresses FSM after landmark loss
              │
      [if counting_allowed]
      RepTracker.update(p_lm, v_lm, d_lm, swing_lm, w, h)
              │  OneEuroFilter on angle
              │  swing detection via shoulder/hip y-motion history
              │  FSM transition check (angle vs thresholds)
              │  _update_technique_state() → fault detection
              │  returns (angle, swinging, rep_done, score)
              │
      TrackingGuard.update(lm, trackers)
              │  monitors bbox jump, scale jump, low reliability, recovery frequency
              │  triggers tracker.reset_tracking() if any signal fires
              │
      build_msgs(trackers, angles, swings, exercise, voice, cfg, lang, qualities)
              │  one-cue policy: collects all candidates, sorts by severity
              │  returns [(text, severity)] — exactly 1 item
              │
      ui.screen_workout_*()
              │  draws frame + skeleton + angle arc + rep counter + feedback
              │
cv2.imshow() → user sees frame
cv2.waitKeyEx(1) → keyboard handling
```

### 3.5 Rep Tracking & FSM

**File:** `taharrak/tracker.py` — class `RepTracker`

Each `RepTracker` instance tracks one side of one exercise for one set.

**FSM states:**
- `None` — unknown (just started, or after landmark loss)
- `"start"` — arm at rest / bottom position
- `"end"` — arm at peak / top position

**Transitions (non-invert exercise like bicep curl):**
```
angle > angle_down  →  stage = "start"   (arm extended, rep begins)
angle < angle_up    →  stage = "end"     (arm curled, but only if already in "start")
```

**Rep completion guard:** minimum rep duration (`min_rep_time`) enforced.
Too-fast transitions → `rejected_reps` counter incremented, `_log_event("below_min_duration")`.

**Recovery gate:** after landmark loss, `_recovering = True`.
FSM transitions suppressed until `_recovery_frames` (default 3) consecutive GOOD frames.
`_consecutive_lost > _max_lost_frames` (default 15) → abort in-progress rep, `_log_event("lost_visibility")`.

**Event log categories** (structured, not just counts):
- `lost_visibility` — rep aborted due to persistent landmark loss
- `below_min_duration` — rep rejected, moved too fast
- `recovery_interrupted` — GOOD signal returned mid-rep after LOST
- `tracking_reset` — TrackingGuard triggered hard reset

### 3.6 Form Scoring

**Range:** 0–100 per rep (higher is better)

**Penalty components:**

| Component | Max penalty | Triggered by |
|-----------|-------------|--------------|
| ROM (bottom) | 25 pts | Didn't reach `angle_down` threshold |
| ROM (top) | 25 pts | Didn't reach `angle_up` threshold |
| Swing | 30 pts | Shoulder/hip y-motion > `swing_threshold` (15pts for ≥1 frame, 30pts for ≥3 frames) |
| Drift/sway | 20 pts | Upper arm drift, wrist misalign, elbow flare, lateral raise too high |
| Tempo | 20 pts | Rep too fast (20pts), rep too slow (10pts) |

**Warmup mode:** Penalty halved in set 1 (encourages users to ease in).

**Session rating:**
- S: avg score ≥ 90
- A: avg score ≥ 75
- B: avg score ≥ 60
- C: below 60

**Fatigue detection:** `FatigueDetector` compares avg score of first half vs second half
of a set. Gap ≥ 20 points → "Form breaking down" warning shown in summary.

### 3.7 Correction Engine

**File:** `taharrak/correction.py` — class `CorrectionEngine`

Converts raw fault signals into one prioritised coaching cue per frame.

**4 priority tiers:**

| Tier | Category | Faults included |
|------|----------|----------------|
| 1 | Safety / gross form | trunk_swing, excessive_lean_back, upper_arm_drift, elbow_flare, knee_collapse |
| 2 | ROM / structural | incomplete_rom, incomplete_lockout, insufficient_depth, raising_too_high, wrist_elbow_misstacking |
| 3 | Tempo | too_fast (handled by live coaching path) |
| 4 | Symmetry | (reserved for Phase 4) |

**Rule:** Tier 1 always surfaces before Tier 2, regardless of fault severity or frame count.
Within same tier, tiebreak by `fault_frames` count (more persistent fault wins).

**Post-rep summary verdicts:**
- `correction_new` — first faulty rep on this side
- `correction_persists` — same fault as previous rep ("Still: Keep upper arm still")
- `correction_fixed` — previous fault cleared, new one present ("Fixed!")
- `None` — clean rep (no message)

**Output: `RepCorrection` dataclass:**
```python
RepCorrection(
    main_error    = "upper_arm_drift",     # fault key (or None = clean)
    severity      = 0.72,                  # fault_frames / 20, capped at 1.0
    confidence    = 0.90,                  # GOOD=0.9, WEAK=0.5, LOST=0.1
    cue_key       = "keep_upper_arm_still",
    priority_tier = 1,                     # 1-4, or 99 for clean rep
    source        = "rep_end",             # "live" or "rep_end"
    side          = "left",
)
```

### 3.8 Pose Smoothing

**File:** `taharrak/tracker.py` — `OneEuroFilter`, `OneEuroLandmarkSmoother`

**Why One Euro Filter over sliding-window average:**
A sliding window applies the same smoothing regardless of how fast the joint is moving.
This creates lag exactly where you don't want it — at rep transitions when the arm reverses direction.

One Euro is adaptive:
- **Low velocity (joint held still):** heavy smoothing → kills jitter
- **High velocity (rep boundary):** opens cutoff → minimal lag, responsive tracking

**Reference:** Casiez, G., Roussel, N., Vogel, D. (2012). 1€ Filter. CHI 2012.

**Per-landmark application:**
- 33 landmarks × 3 axes (x, y, z) = 99 independent filters
- visibility and presence kept **raw** — filtering would delay LOST detection
- Parameters: `min_cutoff=1.5`, `beta=0.007` (configurable)

**ConfidenceSmoother:** 10-frame majority vote on GOOD/WEAK/LOST quality labels.
Prevents flickering quality that would cause FSM to jitter between counting and suppression.

### 3.9 Trust & Recovery System

**LiveTrustGate** — tracks frame-by-frame stability before allowing coaching.

Three trust levels:
- `render_allowed` — any non-LOST signal → show skeleton overlays
- `counting_allowed` — N consecutive GOOD frames → enable FSM transitions
- `coaching_allowed` — N consecutive GOOD on both sides → show form cues

**TrackingGuard** — system-level re-acquisition guard above per-tracker FSMs.

Monitors 4 signals:
1. Low reliability: key joints below threshold for 20 consecutive frames
2. Bbox jump: skeleton centre moves > 0.25 (normalised) in one frame
3. Scale jump: shoulder span changes > 30% relative in one frame
4. Recovery frequency: 4+ recovery events within a 5-second window

Any signal → triggers `tracker.reset_tracking()` (soft reset: clears FSM and filters, preserves rep_count).

**Design rationale:** Without this guard, a person leaving frame mid-rep and returning
could cause the FSM to complete a phantom rep. The recovery gate ensures the arm is
genuinely back in a known position before counting resumes.

### 3.10 UI & Messages

**File:** `taharrak/ui.py` — all screen renderers using OpenCV

**Screen renderers:**
| Function | When shown |
|----------|------------|
| `screen_exercise_select()` | App startup |
| `screen_weight_input()` | After exercise chosen |
| `screen_calibration()` | Camera setup phase |
| `screen_countdown()` | 3-2-1 before set starts |
| `screen_workout_bilateral()` | Bilateral exercise live loop |
| `screen_workout_single()` | Single-side exercise live loop |
| `screen_rest()` | Rest timer between sets |
| `screen_summary()` | End-of-session stats |
| `screen_history()` | Past sessions browser |

**Key HUD elements during workout:**
- Pose skeleton overlay (coloured by joint quality: green=GOOD, yellow=WEAK, red=LOST)
- Angle arc gauge around the vertex joint
- Rep counter (large, top corner)
- Left/right rep split (bilateral)
- Form feedback banner (one cue, colour-coded by severity)
- Tempo bar (how fast this rep is going)
- Trust indicator (shows coaching suppressed during warmup frames)

**Severity colours (BGR):**
- `error` (RED) — must fix: swinging, moving too fast
- `warning` (ORANGE) — form nudge: incomplete ROM, drift
- `ok` (GREEN) — positive cue: lower slowly, curl up

**Bilingual support:**
- English rendered via OpenCV `putText` directly
- Arabic rendered via PIL + arabic-reshaper + python-bidi (correct RTL shaping and letter joining)
- Fallback to English if Arabic font not available
- Runtime toggle via L key

**File:** `taharrak/messages.py` — 200+ message keys in EN and AR.

### 3.11 Persistence (SQLite)

**File:** `taharrak/database.py`

**Schema:**
```sql
sessions (
    id, created_at, exercise_key, exercise_name,
    weight_kg, sets_done, total_reps,
    avg_score, best_score, duration_secs, rating
)

rep_log (
    id, session_id, timestamp, side, set_num, rep_num,
    score, duration_s, min_angle, max_angle, swing_frames
)

personal_bests (
    exercise_key, best_avg_score, best_rep_score,
    best_reps, achieved_at
)
```

**Export functions** (`taharrak/session.py`):
- `save_csv(trackers)` → `workout_YYYYMMDDhhmmss.csv` (per-rep data)
- `save_events_csv(trackers)` → `events_YYYYMMDDhhmmss.csv` (abort/reject events)

### 3.12 Configuration System

**File:** `taharrak/config.py` — `_load_cfg(path)`

Load order:
1. `DEFAULT_CONFIG` (hard-coded safe values)
2. Merge user `config.json` (any key overrides the default)
3. Apply `DEFAULT_EXERCISE_THRESHOLDS` to `exercise_thresholds` sub-dict

**Key config sections:**
```json
{
  "vis_good": 0.68,
  "vis_weak": 0.38,
  "one_euro_min_cutoff": 1.5,
  "one_euro_beta": 0.007,
  "target_reps": 10,
  "min_rep_time": 1.2,
  "ideal_rep_time": 2.0,
  "rest_duration": 60,
  "language": "en",
  "mirror_mode": true,
  "warmup_mode": true,
  "fsm_recovery_frames": 3,
  "fsm_max_lost_frames": 15,
  "trust_count_frames": 1,
  "trust_coach_frames": 5,
  "swing_window": 15,
  "exercise_thresholds": {
    "bicep_curl": { "angle_down": 160, "angle_up": 50, ... },
    ...
  }
}
```

Alias support: key `"1"` resolves to `"bicep_curl"`, `"curl"` also resolves to `"bicep_curl"`.

---

## 4. Web Application

### 4.1 Architecture Overview

```
Browser (Angular 17)
    │
    ├── /api/*  ──────────────────────▶  Spring Boot :8080
    │                                        │
    │                                        ├── Proxy analysis to Python
    │                                        ├── Persist sessions, reps, feedback
    │                                        ├── User identity (anonymous UUID)
    │                                        └── Events, errors logging
    │
    └── ws://localhost:8081/ws/live/*        Python FastAPI :8081
        (WebSocket — bypasses Spring Boot)       │
                                                 ├── MediaPipe pose detection
    HTTP analysis calls also go direct:          ├── RepTracker (stateful per connection)
    http://localhost:8081/process ───────────────┘
```

**Why Python is called directly for analysis (not through Spring Boot):**
Analysis is pure computation — no auth, no user data. Routing large video files
through Spring Boot would add memory pressure and latency with no benefit.
Spring Boot owns all persistence and user-linked operations.

**Why Spring Boot exists at all:**
- User identity resolution and GDPR erasure
- Session + rep log persistence (PostgreSQL in production)
- Feedback storage (ratings, corrections, ground-truth labels)
- Analytics events (funnel, feature usage)
- Client error reporting

### 4.2 Python Model Service (FastAPI)

**File:** `web/model-service/main.py`  
**Port:** 8081  
**Stateless** — no database, no user context. Pure ML computation.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/exercises` | List all 5 exercises with key, name, bilateral flag |
| POST | `/process` | Accept video file + exercise_key, return metrics dict |
| WS | `/ws/live/{exercise_key}` | Real-time frame feedback (JPEG in → JSON out) |

**`POST /process` flow:**
1. Save uploaded video to temp directory
2. Call `taharrak.eval.replay_video(path, exercise_key, cfg)`
3. Return metrics: reps_total, reps_left/right, signal_quality, dropout_rate,
   mean_reliability, unknown_rate, aborted_reps, rejected_reps, frames_total,
   frames_detected, fps_mean
4. Delete temp directory

**`WS /ws/live/{exercise_key}` protocol:**
- Client → server: raw JPEG bytes (one message = one frame, ~10fps from browser)
- Server → client: JSON with: detected, reps_total, reps_left, reps_right,
  quality (GOOD/WEAK/LOST), feedback (text), severity (ok/warning/error), angles

**WebSocket session state (per connection):**
- `RepTracker` instances (1 or 2 depending on bilateral)
- `OneEuroLandmarkSmoother`
- `PoseLandmarker` in IMAGE mode (synchronous, no timestamps)
- Frame counters and reliability accumulators

The session is torn down on `WebSocketDisconnect` or error — `landmarker.close()` always called.

**Startup:** `_ensure_model()` downloads `pose_landmarker_lite.task` (~5MB) on first boot.
Subsequent starts are instant (file already on disk).

### 4.3 Spring Boot Backend

**File tree:** `web/backend/src/main/java/com/workout/api/`  
**Port:** 8080  
**Database:** H2 (local dev) or PostgreSQL (production, set `SPRING_PROFILES_ACTIVE=prod`)  
**Schema migration:** Flyway — `V1__init_schema.sql`

**Controllers and their endpoints:**

| Controller | Method | Path | Description |
|------------|--------|------|-------------|
| UserController | POST | `/api/users/resolve` | Create/update anonymous user by token |
| UserController | DELETE | `/api/users/{token}` | GDPR erasure (soft delete + token rotation) |
| SessionController | POST | `/api/sessions` | Save completed session + rep logs |
| SessionController | GET | `/api/sessions` | Get history for current user |
| FeedbackController | POST | `/api/feedback` | Save user rating + rep correction feedback |
| EventController | POST | `/api/events` | Batch analytics events |
| ErrorController | POST | `/api/errors` | Client error reporting |
| AnalysisController | GET | `/api/exercises` | Proxy to Python service |
| AnalysisController | POST | `/api/analyze` | Proxy video upload to Python service |

**All user-linked endpoints** read `X-User-Id` header (UUID).
The Angular `UserTokenInterceptor` adds this header automatically to every `/api/` request.

**Key design decisions:**
- `Map.ofEntries` avoided in history response — uses `HashMap` because `Map.of` does not allow null values (nullable fields like `repsLeft` would crash it)
- `StringListConverter` stores `List<String>` as JSON text — works identically on H2 and PostgreSQL
- Rep logs saved via `repLogRepo.saveAll()` — not session re-saves (bug that existed, now fixed)
- `FeedbackEntity` has nullable `session_id` and `user_id` — feedback survives GDPR erasure

### 4.4 Angular Frontend

**Framework:** Angular 17, standalone components, lazy-loaded routes  
**Styling:** Tailwind CSS  
**Port (dev):** 4200

**Pages and routes:**

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | HomeComponent | Landing page — exercise cards, how-it-works, filming tips |
| `/analyze` | AnalyzeComponent | Exercise picker + video drag-and-drop upload |
| `/results` | ResultsComponent | Rep count, quality metrics, feedback form |
| `/camera` | CameraComponent | Live webcam session with real-time HUD overlay |
| `/history` | HistoryComponent | All past sessions in a table |

**Services:**

| Service | Responsibility |
|---------|---------------|
| `ApiService` | All HTTP calls — analysis, session save, history, feedback, events, errors |
| `UserService` | localStorage token management, user resolution on app init |
| `WorkoutSocketService` | WebSocket connection lifecycle, frame sending, feedback receiving |

**Interceptor:**
`UserTokenInterceptor` — adds `X-User-Id: {userId}` header to every `/api/` request.
Excludes `/api/users/resolve` to avoid circular dependency.

**User identity flow:**
1. App starts → `APP_INITIALIZER` calls `UserService.init()`
2. Read `workout_token` from localStorage (or generate `crypto.randomUUID()`)
3. POST `/api/users/resolve` → get back `userId` and confirmed token
4. Store both in localStorage
5. All subsequent requests automatically carry `X-User-Id` via interceptor

### 4.5 Data Flow — Video Upload

```
User selects exercise + video file
        │
AnalyzeComponent.submit()
        │
ApiService.analyzeVideo(file, exerciseKey)
        │  POST http://localhost:8081/process (multipart)
        ▼
Python model service
        │  replay_video() → MediaPipe VIDEO mode
        │  returns metrics dict
        ▼
Angular receives AnalysisResult
        │
Router.navigateByUrl('/results', { state: { result } })
        │
ResultsComponent displays metrics
        │
User submits feedback (rating + was rep count accurate?)
        │
ApiService.saveSession(payload)  → POST /api/sessions  (Spring Boot)
ApiService.submitFeedback(payload) → POST /api/feedback (Spring Boot)
```

### 4.6 Data Flow — Live Camera

```
User opens /camera, selects exercise, clicks "Turn on camera"
        │
navigator.mediaDevices.getUserMedia() → MediaStream
        │
Video element renders live feed
        │
User clicks "Start"
        │
WorkoutSocketService.connect(exerciseKey)
        │  ws://localhost:8081/ws/live/{exerciseKey}
        │
setInterval(100ms) → captureAndSend()
        │  canvas.drawImage(video) → toBlob(JPEG, 0.7) → socket.send()
        │
Python processes each frame:
        │  decode JPEG → MediaPipe IMAGE mode → tracker update → build_msgs
        │  returns JSON: { detected, reps_total, quality, feedback, severity, angles }
        │
WorkoutSocketService.feedback$ → CameraComponent
        │
HUD overlay updates in real time:
        │  - Top right: rep counter
        │  - Top left: quality dot (green/yellow/red)
        │  - Bottom: form feedback banner (red/yellow/green)
        │
User clicks "Stop"
        │
ApiService.saveSession({ source: 'live', exerciseKey, repsTotal, ... })
        │  POST /api/sessions (Spring Boot)
```

### 4.7 User Identity & GDPR

**Anonymous by design:**
- No email, no password, no name
- Identity = UUID token in localStorage
- Backend stores only `ip_country` (2-letter code) and `user_agent_hash` (SHA-256) alongside the token — no raw PII

**GDPR erasure (`DELETE /api/users/{token}`):**
1. Token rotated to a new random UUID → old token immediately invalid
2. `deleted_at` timestamp set
3. `workout_sessions.deleted_at` set on all sessions → excluded from history queries
4. `feedback.user_id` and `user_events.user_id` → `ON DELETE SET NULL` → anonymised
5. Aggregate data (rep counts, signal quality) remains in DB for analytics but is unlinkable to any person

---

## 5. Database Schema (Production)

Full PostgreSQL-ready schema. H2 in PostgreSQL compatibility mode used locally.
Managed by Flyway — `web/backend/src/main/resources/db/migration/V1__init_schema.sql`

### anonymous_users
```
id              UUID  PK
token           UUID  UNIQUE NOT NULL       ← localStorage value
created_at      TIMESTAMP
last_seen_at    TIMESTAMP
deleted_at      TIMESTAMP                   ← GDPR soft delete
ip_country      VARCHAR(2)
user_agent_hash VARCHAR(64)                 ← SHA-256, not raw UA
```

### workout_sessions
```
id               UUID  PK
user_id          UUID  FK → anonymous_users
exercise_key     VARCHAR(20)
exercise_name    VARCHAR(100)
source           VARCHAR(10)               ← 'upload' | 'live'
reps_total       SMALLINT
reps_left        SMALLINT  nullable
reps_right       SMALLINT  nullable
signal_quality   DECIMAL(5,4)
dropout_rate     DECIMAL(5,4)
mean_reliability DECIMAL(5,4)
unknown_rate     DECIMAL(5,4)
frames_total     INTEGER
frames_detected  INTEGER
fps_mean         DECIMAL(6,2)
reps_aborted     SMALLINT
reps_rejected    SMALLINT
camera_issues    VARCHAR(500)              ← JSON array: ["cam_too_close"]
duration_s       INTEGER  nullable         ← live sessions only
created_at       TIMESTAMP
deleted_at       TIMESTAMP                 ← GDPR propagation
```

**Indexes:** user_id, exercise_key, created_at, (user_id, exercise_key, created_at)

### rep_logs
```
id                  BIGINT  PK AUTO_INCREMENT
session_id          UUID  FK → workout_sessions (CASCADE DELETE)
rep_number          SMALLINT
side                VARCHAR(10)             ← 'left' | 'right' | 'center'
set_number          SMALLINT
duration_ms         INTEGER
form_score          SMALLINT  (0-100)
angle_min           DECIMAL(6,2)
angle_max           DECIMAL(6,2)
faults              VARCHAR(500)            ← JSON array: ["upper_arm_drift"]
penalty_rom         SMALLINT
penalty_tempo       SMALLINT
penalty_sway_drift  SMALLINT
penalty_asymmetry   SMALLINT
penalty_instability SMALLINT
created_at          TIMESTAMP
```

**This is the most valuable table for model improvement.**
Every rep's fault pattern + form score is here.

### feedback
```
id                  BIGINT  PK AUTO_INCREMENT
session_id          UUID  FK (nullable, SET NULL on delete)
user_id             UUID  FK (nullable, SET NULL on delete)
exercise_key        VARCHAR(20)
rating              SMALLINT  (1-5)
rep_count_accurate  BOOLEAN                ← ground truth label
user_rep_correction SMALLINT  nullable     ← what the user thinks the count was
comment             VARCHAR(2000)
created_at          TIMESTAMP
```

**`rep_count_accurate` + `user_rep_correction` is the most direct model accuracy signal.**
When a user says "No, I did 12 reps not 10", that's a labelled error.

### user_events
```
id          BIGINT  PK AUTO_INCREMENT
user_id     UUID  FK
session_id  UUID  FK nullable
event_type  VARCHAR(50)
properties  VARCHAR(2000)                  ← JSON: {"exerciseKey":"1","fileSize":1400000}
occurred_at TIMESTAMP                      ← client-side time
created_at  TIMESTAMP
```

**Event taxonomy:**
`page_view`, `exercise_selected`, `upload_started`, `upload_completed`, `upload_failed`,
`live_session_started`, `live_session_ended`, `feedback_opened`, `feedback_submitted`, `history_viewed`

### client_errors
```
id          BIGINT  PK AUTO_INCREMENT
user_id     UUID  FK nullable
session_id  UUID  FK nullable
error_type  VARCHAR(50)
message     VARCHAR(500)
stack_hash  VARCHAR(64)                    ← SHA-256 for dedup
http_status SMALLINT
occurred_at TIMESTAMP
created_at  TIMESTAMP
```

---

## 6. API Reference

### Python Model Service (port 8081)

```
GET  /health
     → { "status": "ok" }

GET  /exercises
     → [ { "key": "1", "name": "Bicep Curl", "bilateral": true }, ... ]

POST /process
     Content-Type: multipart/form-data
     Fields: video (file), exercise_key (string)
     → {
         "success": true,
         "exercise_key": "1",
         "exercise_name": "Bicep Curl",
         "reps_total": 10,
         "reps_left": 5,
         "reps_right": 5,
         "signal_quality": 0.921,
         "dropout_rate": 0.034,
         "mean_reliability": 0.887,
         "unknown_rate": 0.012,
         "aborted_reps": 0,
         "rejected_reps": 1,
         "frames_total": 900,
         "frames_detected": 869,
         "fps_mean": 29.8
       }

WS   /ws/live/{exercise_key}
     Client → server: JPEG binary (one message per frame)
     Server → client: {
         "detected": true,
         "reps_total": 3,
         "reps_left": 2,
         "reps_right": 1,
         "quality": "GOOD",
         "feedback": "Keep upper arm still",
         "severity": "warning",
         "angles": [45.2, 48.1]
       }
```

### Spring Boot Backend (port 8080)

```
POST /api/users/resolve
     { "token": "uuid-string" }
     → { "userId": "uuid", "token": "uuid", "isNew": false }

DELETE /api/users/{token}
     → 204 No Content

GET  /api/exercises
     → proxied from Python service

POST /api/analyze
     Content-Type: multipart/form-data
     Fields: video (file), exerciseKey (string)
     Header: X-User-Id: {userId}
     → AnalysisResult (same as /process above)

POST /api/sessions
     Header: X-User-Id: {userId}
     Body: { exerciseKey, exerciseName, source, repsTotal, repsLeft, repsRight,
             signalQuality, dropoutRate, meanReliability, unknownRate,
             framesTotal, framesDetected, fpsMean, repsAborted, repsRejected,
             cameraIssues[], durationS, repLogs[] }
     → { "sessionId": "uuid", "createdAt": "ISO8601" }

GET  /api/sessions
     Header: X-User-Id: {userId}
     → [ { id, exerciseKey, exerciseName, source, repsTotal, repsLeft, repsRight,
            signalQuality, dropoutRate, meanReliability, framesTotal,
            framesDetected, createdAt }, ... ]

POST /api/feedback
     Header: X-User-Id: {userId}
     Body: { sessionId, exerciseKey, rating (1-5), repCountAccurate,
             userRepCorrection, comment }
     → { "message": "Thank you" }

POST /api/events
     Header: X-User-Id: {userId}
     Body: { events: [ { eventType, sessionId, properties, occurredAt } ] }
     → { "accepted": N }

POST /api/errors
     Header: X-User-Id: {userId}
     Body: { sessionId, errorType, message, stackHash, httpStatus, occurredAt }
     → 204 No Content
```

---

## 7. Test Coverage

**213 tests, all passing.** Run with: `python -m pytest tests/`

| File | Tests | What it covers |
|------|-------|---------------|
| `test_correction_engine.py` | ~50 | Priority tiers, post-rep verdicts, tier ordering, clean rep detection |
| `test_technique_runtime.py` | ~40 | TechniqueProfile scoring in simulated rep cycles |
| `test_technique_profiles.py` | ~25 | Profile field validation, EN/AR message key presence |
| `test_live_trust.py` | ~35 | LiveTrustGate state transitions, coaching suppression logic |
| `test_gating.py` | ~36 | `joint_reliability`, TrackingGuard thresholds, re-acquisition |
| `test_reason_logging.py` | 23 | Event log lifecycle (abort/reject/reset/recovery_interrupted) |
| `test_eval_metrics.py` | 20 | Metric accumulators, `signal_quality` formula correctness |
| `test_fsm.py` | 13 | Rep cycle, min-duration gate, abort logic, recovery |
| `test_camera_gate.py` | ~24 | Camera position feedback, `build_msgs` severity types |
| `test_smoother.py` | 13 | OneEuroFilter convergence, steady-state passthrough |
| +6 more | ~84 | Input handling, i18n, view reliability, kinematics, config loading |

---

## 8. Known Issues & Bugs Fixed

### Fixed in this session

| # | Severity | Location | Bug | Fix applied |
|---|----------|----------|-----|-------------|
| 1 | Critical | `SessionService.java` | Rep logs looped but only re-saved the parent session — reps never written to DB | Injected `RepLogRepository`, replaced broken loop with `repLogRepo.saveAll(repLogs)` |
| 2 | Critical | `SessionService.java` | `Map.ofEntries()` throws `NullPointerException` on nullable fields like `repsLeft` | Replaced with `HashMap` which accepts null values |
| 3 | Critical | `camera.component.ts` | Called `api.saveLiveSession()` — method does not exist in `ApiService` | Replaced with `api.saveSession()` using correct `SaveSessionPayload` interface |
| 4 | Medium | `results.component.ts` | Feedback payload used `repsDetected` and `wasAccurate` — neither field exists in `FeedbackPayload` | Renamed to `repCountAccurate`, removed `repsDetected` |
| 5 | High | `history.component.html` | All field bindings used snake_case (`r.exercise_name`, `r.reps_total`) but `HistoryRecord` interface is camelCase | Updated all bindings: `exerciseName`, `repsTotal`, `createdAt`, `signalQuality`, etc. |

### Previously fixed (earlier sessions)

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'taharrak'` in model service | `PROJECT_ROOT` was `.parent.parent` — should be `.parent.parent.parent` (3 levels up) |
| `UnicodeEncodeError` in `eval.py` on Windows (cp1252 terminal) | Replaced all Unicode chars in `_print_table`: `─`→`-`, `Δ`→`d`, `°`→`deg`, `—`→`-` |
| `build_msgs()` returning BGR tuples instead of semantic severities | Decoupled: returns `(text, severity_string)`, `severity_color()` added to `ui.py` |
| Video upload not analyzing (Spring Boot not running) | Angular now calls Python directly for analysis — Spring Boot only for persistence |
| Commit rejected: contained `Co-Authored-By: Claude` | Never include AI attribution in commit messages |

### Current known limitations

| Issue | Impact | Notes |
|-------|--------|-------|
| Spring Boot `mvn` not in PATH after new terminal | Dev friction | Use full path `C:\Users\wlaeed\tools\apache-maven-3.9.6\bin\mvn.cmd` or open a new terminal (PATH was set permanently) |
| `uvicorn` not in PATH in old terminals | Dev friction | Use full path or open new terminal (PATH was set permanently) |
| Live session rep logs not saved (only session summary) | Data gap | Camera session doesn't have per-rep detail — would require streaming rep events from Python via WebSocket |
| History page shows blank quality for live sessions | UX | Live sessions don't currently send signal_quality — planned improvement |
| Hardcoded `localhost:8081` in `api.service.ts` | Production blocker | Fine for local dev; needs env-based config for deployment |

---

## 9. Configuration Reference

**File:** `config.json` (project root)

Any key here overrides the corresponding default in `taharrak/config.py`.

```json
{
  "vis_good": 0.68,
  "vis_weak": 0.38,
  "one_euro_min_cutoff": 1.5,
  "one_euro_beta": 0.007,
  "one_euro_d_cutoff": 1.0,

  "target_reps": 10,
  "min_rep_time": 1.2,
  "ideal_rep_time": 2.0,
  "rest_duration": 60,

  "trust_count_frames": 1,
  "trust_coach_frames": 5,
  "trust_mismatch_tolerance": 2,

  "fsm_recovery_frames": 3,
  "fsm_max_lost_frames": 15,
  "confidence_smoother_window": 10,

  "swing_window": 15,
  "fatigue_score_gap": 20,

  "language": "en",
  "mirror_mode": true,
  "warmup_mode": true,
  "camera_fps": 30,

  "exercise_thresholds": {
    "bicep_curl": {
      "angle_down": 160,
      "angle_up": 50
    }
  }
}
```

---

## 10. Deployment Guide

### Local development (no Docker)

**Terminal 1 — Python model service:**
```powershell
cd web/model-service
C:\Python314\python.exe -m uvicorn main:app --port 8081 --reload
```

**Terminal 2 — Spring Boot backend:**
```powershell
cd web/backend
C:\Users\wlaeed\tools\apache-maven-3.9.6\bin\mvn.cmd spring-boot:run
```
*First run only: delete `web/backend/data/workout-dev.mv.db` if it exists (old schema)*

**Terminal 3 — Angular:**
```powershell
cd web/frontend
npm install    # first time only
npm start      # proxies /api → localhost:8080
```

**Or use the one-click script:**
```powershell
.\web\start-dev.ps1
```

Open `http://localhost:4200`

### Production (Docker Compose)

```bash
# Build Angular bundle first
cd web/frontend && npm run build:prod

# Start everything
cd web && docker compose up --build
```

Set these environment variables for production:
```
SPRING_PROFILES_ACTIVE=prod
DB_URL=jdbc:postgresql://host:5432/workout
DB_USER=your_user
DB_PASS=your_password
MODEL_SERVICE_URL=http://model-service:8081
```

### CLI app (no web)

```bash
pip install -r requirements.txt
python bicep_curl_counter.py
```

Pose model (`pose_landmarker_lite.task`) downloads automatically on first run (~5MB).

---

## 11. Data Strategy

### What you're collecting and why

| Table | Primary use |
|-------|-------------|
| `workout_sessions` | Exercise popularity, signal quality trends, model performance by exercise |
| `rep_logs` | **Most valuable** — per-rep fault frequency tells you exactly what the model catches and misses |
| `feedback` | Ground-truth labels — `rep_count_accurate=false` + `user_rep_correction` tells you when and by how much the model is wrong |
| `user_events` | Funnel analysis — where do users drop off? Which features are actually used? |
| `client_errors` | Reliability — catch systematic failures before users complain |
| `anonymous_users` | Retention — are people coming back? |

### Queries that answer key business questions

**Model accuracy per exercise:**
```sql
SELECT exercise_key,
       COUNT(*) AS sessions,
       AVG(rating) AS avg_rating,
       COUNT(*) FILTER (WHERE rep_count_accurate = false) AS inaccurate_count,
       AVG(CASE WHEN rep_count_accurate = false THEN user_rep_correction END) AS avg_correction
FROM feedback
GROUP BY exercise_key;
```

**Most common form faults:**
```sql
SELECT fault, COUNT(*) AS occurrences
FROM rep_logs, json_each(faults) AS f(fault)
WHERE session_id IN (
    SELECT id FROM workout_sessions WHERE exercise_key = '1'
)
GROUP BY fault
ORDER BY occurrences DESC;
```

**User retention:**
```sql
SELECT DATE_TRUNC('week', created_at) AS week,
       COUNT(DISTINCT user_id) AS unique_users,
       COUNT(*) AS total_sessions
FROM workout_sessions
GROUP BY week
ORDER BY week;
```

**Funnel drop-off:**
```sql
SELECT event_type, COUNT(DISTINCT user_id) AS unique_users
FROM user_events
WHERE occurred_at > NOW() - INTERVAL '30 days'
GROUP BY event_type
ORDER BY unique_users DESC;
```

**Signal quality trend (is the model getting more reliable?):**
```sql
SELECT DATE_TRUNC('week', created_at) AS week,
       AVG(signal_quality) AS avg_quality,
       AVG(dropout_rate) AS avg_dropout
FROM workout_sessions
GROUP BY week
ORDER BY week;
```

---

## 12. Development History

| Phase | Status | What was built |
|-------|--------|---------------|
| Phase 1 | ✅ Complete | Core rep counting, bilateral tracking, form scoring (ROM + swing + tempo), SQLite persistence, CSV export, voice TTS, bilingual HUD |
| Phase 1.1 | ✅ Complete | One Euro filters, recovery gates, TrackingGuard, event log (abort/reject/reset), semantic severity in analysis, eval harness |
| Phase 2 | ✅ Complete | TechniqueProfile dataclass, fault rules per exercise, kinematics-based fault detection |
| Phase 3 | ✅ Complete | CorrectionEngine, 4-tier fault priority, post-rep summaries (new/persists/fixed), one-cue policy enforcement |
| Web app | ✅ Built | Angular + Spring Boot + FastAPI, video upload, live camera WebSocket, user history, anonymous identity, production DB schema |
| Phase 4 | ⏳ Planned | Symmetry analysis, bilateral form comparison, personalized workout programs |

---

## 13. What to Build Next

### Immediate (complete the web app)

1. **Test the full upload flow** — run all three services, upload a real video, verify session appears in history
2. **Test live camera flow** — open `/camera`, do a set, verify session saves after stopping
3. **Send signal_quality from live session** — currently live sessions save `repsTotal` only; WebSocket could accumulate quality metrics and send them when session ends
4. **Environment config for production URLs** — replace hardcoded `localhost:8081` in `api.service.ts` with `environment.ts` Angular environment variables

### Near-term (model improvement loop)

5. **Review collected feedback** — once you have 20+ sessions with feedback, query `rep_count_accurate=false` rows to find which exercises the model miscounts most
6. **Per-rep fault heatmap** — query `rep_logs.faults` to see which form faults are most common; use this to prioritise coaching cue improvements
7. **Improve live session rep logs** — stream `RepRecord` objects back via the WebSocket when each rep completes, save them to `rep_logs` table

### Phase 4 (future)

8. **Symmetry analysis** — compare left vs right `form_score` per set; surface asymmetry cues in both CLI and web app
9. **User progress charts** — show signal quality and avg form score trending over time on the history page
10. **Push notifications / sharing** — let users share a session result link (public read-only view of one session)

---

*End of report. Last updated: April 2026.*
