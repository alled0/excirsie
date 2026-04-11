# Taharrak — Codebase Reference

> Last updated: 2026-04-11  
> 213 tests · all green · 4,188 lines across 17 source files

---

## Product Identity

**Taharrak** (تحرك) is a local-first AI fitness coach that helps beginners learn correct exercise
form through real-time feedback.  The correction engine is the product — rep counting is
support infrastructure.

**Stack:** Python 3 · OpenCV · MediaPipe BlazePose · pyttsx3 · SQLite · Pillow (Arabic)

**Supported exercises:** Bicep Curl · Shoulder Press · Lateral Raise · Tricep Extension · Squat

---

## File Map

```
bicep_curl_counter.py         entry point — camera loop + state machine (624 lines)

taharrak/
  correction.py               Phase 3 — CorrectionEngine, RepCorrection, FAULT_PRIORITY (266)
  analysis.py                 pose analysis + one-cue feedback builder (376)
  tracker.py                  RepTracker, filters, trust gate, guards (957)
  ui.py                       all OpenCV drawing functions (724)
  messages.py                 EN/AR string table + Arabic PIL renderer (290)
  eval.py                     offline video replay harness (369)
  database.py                 SQLite schema + helpers (183)
  session.py                  save_csv, save_events_csv, persist_session (75)
  exercises/
    base.py                   Exercise + TechniqueProfile dataclasses, landmark constants
    bicep_curl.py             BICEP_CURL exercise + Technique Rules v1 profile
    shoulder_press.py         SHOULDER_PRESS
    lateral_raise.py          LATERAL_RAISE
    tricep_extension.py       TRICEP_EXTENSION
    squat.py                  SQUAT
    __init__.py               EXERCISES registry dict

tests/
  test_correction_engine.py   50 tests — Phase 3 correction engine
  test_technique_runtime.py   ~40 — profile scoring, fault detection, cue selection
  test_technique_profiles.py  ~25 — profile presence, field validation, EN/AR keys
  test_live_trust.py          ~35 — LiveTrustGate, coaching suppression, diagnostics
  test_gating.py              ~36 — joint_reliability, TrackingGuard, reset_tracking
  test_reason_logging.py      23  — event categories, lifecycle across resets
  test_eval_metrics.py        20  — counters, signal_quality formula
  test_fsm.py                 13  — rep cycle, hard min-duration, abort, recovery
  test_camera_gate.py         ~24 — camera position checks, build_msgs severity
  test_smoother.py            13  — OneEuroFilter convergence, passthrough
  test_input_keys.py          —   key handling
  test_ui_i18n.py             —   Arabic rendering
```

---

## State Machine

```
EXERCISE_SELECT → WEIGHT_INPUT → CALIBRATION → COUNTDOWN
→ WORKOUT → REST → WORKOUT → … → SUMMARY → (exit)
EXERCISE_SELECT → HISTORY → EXERCISE_SELECT
```

**Key transitions:**
- `SPACE` on CALIBRATION (both arms GOOD, no camera issues) → COUNTDOWN
- Set target reached / `S` key → REST
- REST timer expires or `SPACE` → next WORKOUT
- `Q` / `ESC` anywhere in WORKOUT → SUMMARY

---

## Live Frame Data Flow

```
Camera
  └─ MediaPipe PoseLandmarker (VIDEO mode, lite model)
       └─ OneEuroLandmarkSmoother.smooth()
            └─ det_quality_ex()  →  (left_q, right_q)  GOOD / WEAK / LOST
                 ├─ tracker.update_quality()            recovery gating
                 ├─ LiveTrustGate.update()              trust state
                 │    counting_sides, coaching_sides,
                 │    bilateral_compare_allowed
                 │
                 ├─ [if counting_allowed]
                 │    tracker.update()
                 │      ├─ OneEuroFilter angle
                 │      ├─ swing detection
                 │      ├─ FSM: None → start → end
                 │      ├─ _update_technique_state()  →  faults Counter
                 │      └─ if rep_done:
                 │           CorrectionEngine.assess_rep()
                 │             → RepCorrection + summary tuple
                 │           build_post_rep_summary()
                 │             → post_rep_flash (shown for score_flash_duration s)
                 │
                 ├─ TrackingGuard.update()              re-acquisition
                 │    bbox jump · scale jump · low reliability · recovery frequency
                 │
                 └─ [if post_rep_flash active]
                       msgs = post_rep_flash
                    [else]
                       msgs = build_msgs()              one-cue policy
                                 → collect all candidates per tracker
                                 → sort by severity (error > warning > ok)
                                 → return [ top_one ]
                 └─ ui.screen_workout_*()
```

---

## Correction Engine (Phase 3)

### Priority tiers — `FAULT_PRIORITY`

| Tier | Faults | Rule |
|------|--------|------|
| 1 — safety / gross form | `trunk_swing`, `excessive_lean_back`, `upper_arm_drift`, `elbow_flare` | Always surface first, regardless of frame count |
| 2 — ROM / structural | `incomplete_rom`, `incomplete_lockout`, `incomplete_extension`, `insufficient_depth`, `raising_too_high`, `wrist_elbow_misstacking`, `excessive_forward_lean` | Surface when no tier-1 fault present |
| 3 — tempo | `too_fast` | Handled by existing slow_down path |
| 4 — symmetry | `asymmetry` | Reserved — Phase 4 |

### `RepCorrection` shape

```python
RepCorrection(
    main_error    = "upper_arm_drift",   # fault key, or None for clean rep
    severity      = 0.72,               # fault_frames / 20  (capped at 1.0)
    confidence    = 0.90,               # GOOD=0.9  WEAK=0.5  LOST=0.1
    cue_key       = "keep_upper_arm_still",
    priority_tier = 1,
    source        = "rep_end",          # "live" | "rep_end"
    side          = "left",             # "left" | "right" | "center"
)
```

### `CorrectionEngine` API

```python
engine = CorrectionEngine()

# Every frame while rep is in progress:
live = engine.assess_live(tracker, quality)
# → RepCorrection | None  (suppressed if LOST, or fault < 5 frames)

# Immediately after tracker.update() returns rep_done=True:
correction, summary = engine.assess_rep(tracker, quality, lang)
# → summary is (verdict_key, cue_text) or None

# Between sets:
engine.reset()
```

### Post-rep summary verdicts

| Verdict key | Condition | Display |
|---|---|---|
| `correction_new` | First faulty rep on this side | show cue directly |
| `correction_persists` | Same fault as last rep | "Still: {cue}" |
| `correction_fixed` | Previous fault gone | "Fixed!" |
| `None` | Clean rep | nothing |

### One-cue policy in `build_msgs`

Collects all candidate corrections from every tracker, sorts by severity
(`error` → `warning` → `ok`), returns exactly one `(text, severity)` pair.
Voice is only called for the winning correction.

---

## RepTracker internals

| Attribute | Type | What it holds |
|---|---|---|
| `stage` | `str \| None` | `"start"` / `"end"` / `None` (unknown after loss) |
| `rep_count` | `int` | reps this set |
| `total_reps` | `int` | all-time reps |
| `form_scores` | `list[int]` | score per finished rep this set |
| `rep_log` | `list[dict]` | full per-rep record (score, components, fault_frames…) |
| `technique_state` | `dict` | `{faults, signals, view}` — updated every frame |
| `last_score_components` | `dict` | `{rom, tempo, sway_drift, asymmetry, instability}` |
| `last_correction` | `RepCorrection \| None` | set by CorrectionEngine after each rep |
| `_fault_frames` | `Counter` | fault → frame count for the current rep |
| `aborted_reps` | `int` | reps discarded by prolonged LOST |
| `rejected_reps` | `int` | reps blocked by min-duration gate |
| `event_log` | `list[dict]` | non-completion events (abort / reject / reset) |
| `_recovering` | `bool` | True while waiting for stable signal after loss |

### Resets

| Method | What it clears | What it keeps |
|---|---|---|
| `reset_set()` | everything — hard reset | nothing |
| `reset_tracking()` | FSM + filters + in-rep state | `rep_count`, `event_log` (accumulated stats preserved) |

---

## TechniqueProfile fields

```python
TechniqueProfile(
    preferred_view         = "front",
    primary_signal         = "elbow_flexion_angle",
    secondary_signals      = ("upper_arm_drift", "trunk_swing"),
    start_thresholds       = {"elbow_angle_deg": (150.0, 165.0)},  # acceptable range at start
    end_thresholds         = {"elbow_angle_deg": (55.0, 75.0)},    # acceptable range at peak
    top_faults             = ("upper_arm_drift", "trunk_swing", "incomplete_rom"),
    coaching_cues          = ("keep_upper_arm_still", "dont_swing_body", "curl_higher", ...),
    confidence_requirements = {
        "primary_signal":    "GOOD",
        "secondary_signals": "WEAK_OR_BETTER",
    },
)
```

Confidence requirements control when each signal can be coached.
Secondary-signal faults (sway, drift) are suppressed under weak tracking.

---

## TrackingGuard triggers

| Trigger | Condition | Config key |
|---|---|---|
| Low reliability | mean key-joint reliability < `vis_weak` for N consecutive frames | `guard_max_low_rel_frames` (20) |
| Bbox centroid jump | skeleton centre moves > threshold in one frame | `guard_bbox_jump` (0.25) |
| Scale jump | shoulder span changes > threshold relatively in one frame | `guard_scale_jump` (0.30) |
| Recovery frequency | ≥ N recovery entries within sliding time window | `guard_recovery_window` (5 s), `guard_max_recoveries` (4) |

When fired: `reset_tracking()` on all trackers + `lm_smoother.reset()` + `guard.reset()`.

---

## LiveTrustGate levels

| Level | Condition | Gate |
|---|---|---|
| `render_allowed` | any side not LOST | draw skeleton / overlays |
| `counting_allowed` | visible frames ≥ `trust_count_frames` | update rep FSM |
| `coaching_allowed` | GOOD frames ≥ `trust_coach_frames` on all sides | show form corrections |
| `bilateral_compare_allowed` | both sides coaching-level + frame-count close | show left/right comparison |

When `coaching_allowed` is False, `build_msgs` returns setup guidance only
(step back, improve lighting, hold still).

---

## Eval harness (`taharrak/eval.py`)

```bash
python -m taharrak.eval --video clip.mp4 --exercise 1
python -m taharrak.eval --video clip.mp4 --exercise 1 --out results.json
```

Output metrics: `frames_total`, `frames_detected`, `dropout_rate`, `angle_delta_mean`,
`angle_delta_p95`, `reps_total`, `reps_left/right`, `fps_mean`, `mean_reliability`,
`recovery_rate`, `unknown_rate`, `aborted_reps`, `rejected_reps`, `signal_quality`,
`event_log`.

`signal_quality = (1 − dropout) × reliability × (1 − recovery)` ∈ [0, 1]

---

## config.json — key settings

```json
{
  "sets":                     3,
  "reps_per_set":             10,
  "rest_seconds":             60,
  "vis_good":                 0.68,
  "vis_weak":                 0.38,
  "one_euro_min_cutoff":      1.5,
  "one_euro_beta":            0.007,
  "one_euro_d_cutoff":        1.0,
  "fsm_recovery_frames":      3,
  "fsm_max_lost_frames":      15,
  "guard_max_low_rel_frames": 20,
  "guard_bbox_jump":          0.25,
  "guard_scale_jump":         0.30,
  "guard_recovery_window":    5.0,
  "guard_max_recoveries":     4,
  "trust_count_frames":       1,
  "trust_coach_frames":       5,
  "segmentation_enabled":     true,
  "segmentation_bg_color":    [10, 10, 25],
  "default_language":         "en",
  "score_flash_duration":     2.5
}
```

---

## Keyboard controls

| Key | State | Action |
|---|---|---|
| `1`–`5` | EXERCISE_SELECT | select exercise |
| `H` | EXERCISE_SELECT | view history |
| `L` | any | toggle EN / AR |
| `M` | any | toggle mirror mode |
| `D` | WORKOUT | toggle diagnostics overlay |
| `SPACE` | CALIBRATION | start (if GOOD) |
| `S` | WORKOUT | end set → REST |
| `R` | WORKOUT | reset current set |
| `Q` / `ESC` | WORKOUT | finish session → SUMMARY |
| `SPACE` | REST | skip rest |
| `↑` / `↓` | WEIGHT_INPUT | adjust weight |

---

## Adding a new exercise

1. Create `taharrak/exercises/my_exercise.py` — define one `Exercise(...)` with a `TechniqueProfile`
2. Add one import + one dict entry in `taharrak/exercises/__init__.py`
3. Add fault rules for the new exercise key in `taharrak/analysis._FAULT_RULES`
4. Add any new cue message keys to both EN and AR dicts in `taharrak/messages.py`

Nothing else changes.

---

## Phase history

| Phase | Commits | What shipped |
|---|---|---|
| Initial | `60e5d2c` | Rep counting, form scoring, bilateral tracking, TTS, SQLite, CSV, history, Arabic, calibration |
| Refactor | `33e6a1d` | Modular exercise package, background segmentation, landmark averaging, smart camera feedback |
| Phase 1 | `9642188` | 1€ filter, confidence-aware recovery gating, exercise-specific key joints, eval harness, 53 tests |
| Phase 1.1 | `2fcb192` | Visibility+presence scoring, TrackingGuard, eval expansion, event log, semantic analysis/UI separation, 130 tests |
| Phase 1.2 | `780ad25`–`7f92a56` | LiveTrustGate, conservative coaching, bilateral suppression, diagnostics overlay, Arabic/input fixes, 163 tests |
| Phase 2 | `4b9c0ac` | TechniqueProfile system, per-exercise fault profiles for all 5 exercises, profile-driven scoring + coaching, 163 tests |
| Phase 3 | *(current, uncommitted)* | CorrectionEngine, RepCorrection, FAULT_PRIORITY, one-cue policy, post-rep summaries, 213 tests |
