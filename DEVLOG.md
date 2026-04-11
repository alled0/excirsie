# Taharrak — Development Log

> This file documents everything done on the project: goals, decisions,
> technical implementations, and the reasoning behind each change.

---

## Project Overview

**Taharrak** (تحرك) is an AI-powered fitness trainer that runs entirely on
your local machine using your webcam. It uses MediaPipe BlazePose to track
body landmarks in real time, counts exercise reps, scores your form 0–100,
gives voice and on-screen feedback, and logs every session to a local SQLite
database.

**Stack:** Python 3 · OpenCV · MediaPipe · pyttsx3 (TTS) · SQLite · Pillow (Arabic font rendering)

**Supported exercises:** Bicep Curl · Shoulder Press · Lateral Raise · Tricep Extension · Squat

---

## Commit History (summary)

| Hash | Date | Description |
|------|------|-------------|
| `60e5d2c` | 2026-04-02 | Initial commit — full working prototype |
| `80f3479` | 2026-04-02 | Add `.gitignore` |
| `33e6a1d` | 2026-04-11 | Refactor + 3 pose-analysis improvements |
| *(next)*  | 2026-04-11 | Phase 1 — robustness + evaluation improvements |

---

## What Was Built in the Initial Commit (`60e5d2c`)

The first working version was a single large file (`bicep_curl_counter.py`,
573 lines) plus a `taharrak/` support package.

### Features at initial commit

- **Rep counting** using joint angle state machine (START → END → START)
- **Form scoring 0–100** penalising: incomplete range-of-motion, too-fast reps,
  elbow/shoulder sway, asymmetry between left and right arms
- **Bilateral tracking** — left and right sides counted and scored independently
  for upper-body exercises
- **Single-side tracking** — used for full-body moves (squat) where both sides
  move together
- **Calibration screen** — before starting, the app waits until MediaPipe can
  see both arms at GOOD confidence, with an "improve lighting / distance" hint
- **Countdown** (3-2-1) between calibration and workout
- **Rest timer** between sets with configurable duration
- **Session summary** — total reps, avg and best form score, duration, letter
  grade (S / A / B / C) at the end of each session
- **SQLite persistence** — every session and every individual rep is saved to
  `taharrak.db` via `taharrak/database.py`
- **CSV export** — each completed session writes a timestamped `workout_*.csv`
- **History screen** — press H to review past sessions stored in SQLite
- **Voice cues** — background TTS thread (pyttsx3) announces rep milestones,
  form warnings, and set completions
- **Fatigue detection** — form score trend triggers a "form breakdown" warning
  mid-set
- **Progressive overload suggestion** — if avg score is high, the summary
  screen suggests increasing weight
- **Warm-up mode** — lighter weight + higher rep target for the first set
- **EN / AR language toggle** — press L to switch between English and Arabic
  mid-session; Arabic text rendered via Pillow + Noto Naskh Arabic font
- **Fullscreen OpenCV window**
- **Config-driven** — `config.json` controls thresholds, rep targets, rest
  duration, voice rate, visibility thresholds, etc.

### Initial file layout

```
bicep_curl_counter.py       ← entire app logic (~573 lines)
config.json
requirements.txt
assets/
  Noto_Naskh_Arabic/        ← Arabic font files
taharrak/
  __init__.py
  database.py               ← SQLite schema + read/write helpers
  exercises.py              ← Exercise dataclass + all 5 exercise definitions
  messages.py               ← EN/AR string table
  tracker.py                ← RepTracker, ConfidenceSmoother, FatigueDetector, VoiceEngine
  ui.py                     ← All OpenCV drawing functions
```

---

## Refactor Session — 2026-04-11 (commit `33e6a1d`)

Two main goals were tackled in this session:

1. **Three technical improvements** to make the computer vision more robust
2. **Project reorganization** to make adding new exercises easy and clean

---

### Goal 1 — Three Technical Improvements

#### 1. Background Segmentation

**Problem:** The workout backdrop is distracting and makes it harder to focus
on pose landmarks.

**Solution:** Enable MediaPipe's built-in segmentation mask
(`output_segmentation_masks=True` in `PoseLandmarkerOptions`). On each frame:

1. The mask is a float32 array (0.0 = background, 1.0 = person), same size as
   the frame.
2. Convert it to uint8 (multiply × 255).
3. Blend the original frame with a solid dark background colour using the mask
   as alpha: `display = frame * mask + bg * (1 - mask)`.
4. The segmentation is applied **before** the mirror flip so the mask aligns
   correctly with the display frame.

**Config keys added:**
```json
"segmentation_enabled": true,
"segmentation_bg_color": [10, 10, 25]
```

**Where it lives:** `bicep_curl_counter.py` — in the per-frame processing block.

---

#### 2. Landmark Averaging (Loose Clothing Jitter Reduction)

**Problem:** Loose clothing (sleeves, baggy shirts) causes MediaPipe landmark
predictions to jump frame-to-frame, making angle calculations noisy and
triggering false form warnings.

**Solution:** A **sliding-window average** over the last N frames per landmark.
Two new classes added to `taharrak/tracker.py`:

```
SmoothedLandmark   — lightweight proxy with .x .y .z .visibility
                     uses __slots__ for minimal memory overhead

LandmarkSmoother   — holds a deque(maxlen=window) per landmark
                     .smooth(raw_landmarks) → List[SmoothedLandmark]
                     .reset()               → clears buffers (called at set start)
```

Key design choice: **x/y/z are averaged, visibility is kept raw.**
Averaging visibility would delay detection-loss signals and make GOOD/WEAK/LOST
feedback sluggish.

**Config key added:**
```json
"landmark_smooth_window": 7
```

**Where it lives:** `taharrak/tracker.py` · instantiated in `bicep_curl_counter.py`
as `lm_smoother`; `reset()` called when entering CALIBRATION state.

---

#### 3. Smart Camera Position Feedback During Calibration

**Problem:** The old calibration screen only showed a generic "improve lighting
or move closer" message. Users didn't know *what* was wrong with their camera
position.

**Solution:** A new `analyze_camera_position(lm)` function in
`taharrak/analysis.py` analyses pose geometry and returns a list of specific
message keys:

| Check | How detected | Message key |
|-------|-------------|-------------|
| Poor visibility | avg key-landmark visibility < 0.35 | `cam_poor_vis` |
| Too close | shoulder span > 0.48 (normalised width) | `cam_too_close` |
| Too far | shoulder span < 0.15 | `cam_too_far` |
| Off-center right | shoulder midpoint X < 0.35 | `cam_move_right` |
| Off-center left | shoulder midpoint X > 0.65 | `cam_move_left` |
| Camera too low | shoulder midpoint Y > 0.70 | `cam_too_low` |
| Camera too high | shoulder midpoint Y < 0.15 | `cam_too_high` |
| Body rotated | shoulder Y asymmetry > 0.06 | `cam_turn_right/left` |

All analysis is done in **normalised 0–1 coordinates** (no pixel math needed).

The calibration screen UI was updated in `taharrak/ui.py`:
- If issues found → orange panel listing each issue as a bullet
- If arm confidence is LOST → old "improve lighting" hint
- If all clear → green "Camera position: GOOD" badge

11 new message keys added to both EN and AR in `taharrak/messages.py`.

---

### Goal 2 — Project Reorganization

#### The problem with the old layout

- All 5 exercise definitions lived in `taharrak/exercises.py` (140 lines)
- Adding a new exercise meant editing that file
- The main file `bicep_curl_counter.py` was 573 lines mixing state machine
  logic, drawing calls, pose analysis, session saving, and exercise definitions

#### New layout

```
taharrak/
  exercises/              ← NEW package
    __init__.py           ← exercise registry + how-to-add instructions
    base.py               ← Exercise dataclass + BlazePose landmark constants
    bicep_curl.py         ← BICEP_CURL = Exercise(...)
    shoulder_press.py     ← SHOULDER_PRESS = Exercise(...)
    lateral_raise.py      ← LATERAL_RAISE = Exercise(...)
    tricep_extension.py   ← TRICEP_EXTENSION = Exercise(...)
    squat.py              ← SQUAT = Exercise(...)
  analysis.py             ← NEW: det_quality_ex, build_msgs, analyze_camera_position
  session.py              ← NEW: save_csv, persist_session
  tracker.py              ← EXTENDED: + SmoothedLandmark, LandmarkSmoother
  messages.py             ← EXTENDED: + 11 camera feedback keys
  ui.py                   ← EXTENDED: calibration screen camera feedback panel
  database.py             ← UNCHANGED
  __init__.py             ← UNCHANGED
bicep_curl_counter.py     ← SLIMMED: ~220 lines, state machine + camera loop only
```

#### How to add a new exercise now

1. Create `taharrak/exercises/my_exercise.py` — define one `Exercise(...)` instance
2. Add one import line and one dict entry in `taharrak/exercises/__init__.py`

Nothing else in the codebase changes.

#### What was extracted from `bicep_curl_counter.py`

| Function | Moved to |
|----------|----------|
| `det_quality_ex` | `taharrak/analysis.py` |
| `build_msgs` | `taharrak/analysis.py` |
| `analyze_camera_position` | `taharrak/analysis.py` |
| `save_csv` | `taharrak/session.py` |
| `persist_session` | `taharrak/session.py` |
| `SmoothedLandmark` | `taharrak/tracker.py` |
| `LandmarkSmoother` | `taharrak/tracker.py` |
| All `Exercise` definitions | `taharrak/exercises/*.py` |
| `Exercise` dataclass | `taharrak/exercises/base.py` |

#### Circular import issue and fix

`analysis.py` needs `ui.py` colours (RED, ORANGE, GREEN) for `build_msgs`.
`ui.py` imports from `analysis.py`. A direct top-level import would create a
circular dependency.

**Fix:** late import — `from taharrak.ui import RED, ORANGE, GREEN` is placed
**inside the `build_msgs` function body**, not at the top of `analysis.py`.
Python caches modules after first import so there is no performance cost.

#### Old `taharrak/exercises.py`

CPython 3 gives package directories priority over `.py` modules with the same
name. Once `taharrak/exercises/` existed, the old `exercises.py` was never
loaded. It was deleted in the final cleanup.

---

### Files Removed

| File | Why |
|------|-----|
| `taharrak/exercises.py` | Superseded by the `exercises/` package |
| `workout_*.csv` | Dev test artifacts |

---

## Technical Reference

### BlazePose landmark indices (from `taharrak/exercises/base.py`)

```python
LS, LE, LW = 11, 13, 15   # left  shoulder / elbow / wrist
RS, RE, RW = 12, 14, 16   # right shoulder / elbow / wrist
LH, RH     = 23, 24       # left / right hip
LK, RK     = 25, 26       # left / right knee
LA, RA     = 27, 28       # left / right ankle
```

### config.json keys

```json
{
  "sets":                    3,
  "reps_per_set":            10,
  "rest_seconds":            60,
  "min_rep_time":            1.2,
  "vis_good":                0.68,
  "vis_weak":                0.38,
  "landmark_smooth_window":  7,
  "segmentation_enabled":    true,
  "segmentation_bg_color":   [10, 10, 25],
  "default_language":        "en"
}
```

### Workout state machine

```
EXERCISE_SELECT
      ↓ (key press)
WEIGHT_INPUT
      ↓ (Enter)
CALIBRATION  ←── lm_smoother.reset() called here
      ↓ (both arms GOOD)
COUNTDOWN (3-2-1)
      ↓
WORKOUT
      ↓ (set complete)
REST
      ↓ (timer expires or skip)
WORKOUT (next set) … or …
SUMMARY  (all sets done)
      ↓ (H key)
HISTORY
```

---

---

## Phase 1 — Robustness & Evaluation Improvements (2026-04-11)

Goal: make rep counting more stable under occlusion, jitter, bad framing, and
temporary landmark loss, and add an offline evaluation harness with unit tests.

### 1. One Euro Filter for Landmark & Angle Smoothing

**Problem:** The previous sliding-window average had constant lag regardless of
motion speed: heavy at rep boundaries (sluggish response), but still too weak
against sensor noise during holds.

**Solution:** Replace with the **1€ filter** (Casiez et al., CHI 2012).
The 1€ filter is an adaptive low-pass:
- At low velocity → opens up smoothing (kills jitter during holds)
- At high velocity (rep peak) → reduces smoothing (minimal lag at boundary)

```
tau = 1 / (2π × cutoff)
alpha = 1 / (1 + tau / dt)
x_hat = alpha × x + (1 − alpha) × x_prev
```

`cutoff = min_cutoff + beta × |dx_hat|` — the derivative magnitude adaptively
opens the cutoff so fast motion stays responsive.

**New classes in `taharrak/tracker.py`:**
- `OneEuroFilter` — single scalar, pure Python, no new deps
- `OneEuroLandmarkSmoother` — applies one `OneEuroFilter` per (x, y, z) per landmark
- `LandmarkSmoother` — backward-compat subclass; ignores `window` kwarg

**`RepTracker` change:** `_angle_buf` (5-element mean) replaced by a dedicated
`OneEuroFilter` per tracker instance, with `dt` computed from wall-clock time
between `update()` calls.

**Config keys added:**
```json
"one_euro_min_cutoff": 1.5,
"one_euro_beta":       0.007,
"one_euro_d_cutoff":   1.0
```

**Key test insight:** With dt ≈ 0 (test calls happen in microseconds),
`alpha → 0` and the filter never moves.  Test helpers inject `_SIM_DT = 1/30`
before each `update()` call to simulate real 30fps pacing.

---

### 2. Confidence-Aware Recovery Gating

**Problem:** When a landmark briefly disappears (sleeve occlusion, person
leaving frame) and reappears, the FSM could immediately trigger a state
transition on a stale or inconsistent angle — producing a phantom rep or a
missed rep boundary.

**Solution:** `RepTracker` now tracks landmark quality state across frames.

```
States per tracker:
  Normal       → _recovering = False, FSM transitions allowed
  Lost         → _consecutive_lost increments each frame
  Recovering   → _recovering = True; FSM transitions suppressed until
                 _consecutive_good >= fsm_recovery_frames (default 3)
  AbortedRep   → in-progress rep discarded if LOST ≥ fsm_max_lost_frames (15)
```

**New method:** `update_quality(raw_q)` replaces `smooth_quality()` (kept as
alias for backward compat). Call it every frame regardless of whether
`update()` is called.  It:
1. Feeds raw quality to `ConfidenceSmoother` (majority-vote window)
2. Updates lost/good counters
3. If LOST too long while in-rep → calls `_abort_rep()`
4. On GOOD after LOST → sets `_recovering = True`
5. After `fsm_recovery_frames` consecutive GOOD → clears `_recovering`

**`_abort_rep()`** resets `stage = None` (unknown), clears `_in_rep`, resets
the angle filter.  This forces the FSM to wait for a clean starting position
before the next rep, preventing phantom counts on re-appear.

**Hard min-duration block:** Previously `min_rep_time` only penalised the
score; now the FSM will not complete a rep transition at all if
`dur < exercise.min_rep_time`.  Combined with the One Euro filter this
eliminates jitter-spike false counts.

**Config keys added:**
```json
"fsm_recovery_frames": 3,
"fsm_max_lost_frames": 15
```

---

### 3. Exercise-Specific Key Joints

**Problem:** `det_quality_ex` checks all 3 joints in a limb triplet and
returns a coarse GOOD/WEAK/LOST.  The calibration screen couldn't tell the user
*which* specific joint is hidden.

**Solution:** New fields on `Exercise`:
```python
key_joints_left:  tuple = ()   # MUST be visible (subset of joints_left)
key_joints_right: tuple = ()
```

Each exercise sets its critical joints:
- Bicep curl / shoulder press / tricep extension: `(elbow, wrist)`
- Lateral raise: `(shoulder, elbow)`
- Squat: `(knee, ankle)`

**New function `check_exercise_framing(lm, exercise, cfg)`** in
`taharrak/analysis.py` checks these and returns `["joint_hidden"]` if any
are below `vis_good`.  Combined with `analyze_camera_position`, the calibration
screen now gives the user exact joint-level feedback.

**In `bicep_curl_counter.py`:**
```python
cam_feedback = (analyze_camera_position(lm_smooth) +
                check_exercise_framing(lm_smooth, exercise, cfg))
```

**New message key** `"joint_hidden"` added to EN and AR dicts.

---

### 4. Offline Replay Evaluation Harness (`taharrak/eval.py`)

A CLI tool that replays any video file through the full pipeline and reports
quantitative metrics — no GUI, no camera needed.

```
python -m taharrak.eval --video clip.mp4 --exercise 1
python -m taharrak.eval --video clip.mp4 --exercise 1 --out results.json
```

**Metrics output:**

| Metric | Description |
|--------|-------------|
| `frames_total` | Total frames in the video |
| `frames_detected` | Frames where MediaPipe found a pose |
| `dropout_rate` | 1 − detected/total (0 = perfect) |
| `angle_delta_mean` | Mean \|angle[t] − angle[t−1]\| per arm (jitter) |
| `angle_delta_p95` | 95th-percentile frame-to-frame angle jump |
| `reps_total` | Total reps counted across all trackers |
| `reps_left/right` | Per-arm counts (bilateral exercises) |
| `fps_mean` | Wall-clock processing throughput |

The harness runs the same `RepTracker` + `OneEuroLandmarkSmoother` + `det_quality_ex`
logic as the live app so metrics are directly comparable.

---

### 5. Unit Tests (`tests/`)

53 tests across 4 files, all green.  Run with:
```
python -m unittest discover tests/ -v
```

| File | What it covers |
|------|----------------|
| `tests/test_smoother.py` | `OneEuroFilter` convergence, reset, noise attenuation, alpha bounds; `OneEuroLandmarkSmoother` passthrough, visibility raw-pass |
| `tests/test_fsm.py` | Normal rep cycle, min-duration hard block, jitter no-double-count, abort-on-loss, recovery gating, `reset_set` |
| `tests/test_gating.py` | `update_quality` state transitions, recovery counter, abort thresholds, `smooth_quality` alias |
| `tests/test_camera_gate.py` | All 8 `analyze_camera_position` checks; all 6 `check_exercise_framing` scenarios |

**Test design note:** The `_hold_position` / `_hold_until_done` helpers set
`tr._last_upd_t = time.time() - 1/30` before each `update()` call so the
One Euro filter sees a realistic 33ms dt instead of sub-millisecond test time.

---

### Files changed in Phase 1

| File | Change |
|------|--------|
| `taharrak/exercises/base.py` | + `key_joints_left`, `key_joints_right` fields (default `()`) |
| `taharrak/exercises/bicep_curl.py` | + `key_joints_left=(LE,LW)`, `key_joints_right=(RE,RW)` |
| `taharrak/exercises/shoulder_press.py` | + key joints |
| `taharrak/exercises/lateral_raise.py` | + key joints `(LS,LE)` / `(RS,RE)` |
| `taharrak/exercises/tricep_extension.py` | + key joints |
| `taharrak/exercises/squat.py` | + key joints `(LK,LA)` / `(RK,RA)` |
| `taharrak/tracker.py` | + `OneEuroFilter`, `OneEuroLandmarkSmoother`, `LandmarkSmoother` alias; upgraded `RepTracker` |
| `taharrak/analysis.py` | + `check_exercise_framing()` |
| `taharrak/messages.py` | + `joint_hidden` EN + AR |
| `taharrak/eval.py` | NEW — offline evaluation CLI |
| `tests/__init__.py` | NEW — test package |
| `tests/test_smoother.py` | NEW — 13 tests |
| `tests/test_fsm.py` | NEW — 13 tests |
| `tests/test_gating.py` | NEW — 11 tests |
| `tests/test_camera_gate.py` | NEW — 16 tests |
| `config.json` | + 5 new keys |
| `bicep_curl_counter.py` | Updated imports; `OneEuroLandmarkSmoother` instantiation; `check_exercise_framing` wired in calibration |

---

## Repository

GitHub: [https://github.com/alled0/excirsie](https://github.com/alled0/excirsie)
