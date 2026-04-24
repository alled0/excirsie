# Form Logic

Taharrak now uses a kinematics-first pipeline for exercise assessment:

`MediaPipe landmarks -> trust/filtering -> KinematicsFrame -> view reliability -> phase FSM -> fault engine -> correction policy`

## Kinematics

`taharrak/kinematics/` converts raw landmarks into named features such as:

- `active_elbow_angle`
- `active_upper_arm_torso_angle`
- `torso_extension_angle`
- `trunk_tibia_angle_left/right`
- `knee_valgus_proxy_left/right`
- `shoulder_abduction_angle_left/right`
- `elbow_flare_proxy_left/right`
- `shoulder_drift_proxy_left/right`

Features are explicitly named as angles or proxies. A proxy means the value is a conservative 2D estimate from a single RGB camera, not a true 3D biomechanical measurement.

## View Gating

`taharrak/kinematics/view.py` classifies the camera as `front`, `side`, `diagonal`, or `unknown`.

`taharrak/faults/engine.py` suppresses faults when the current view or landmark quality is not reliable enough.

Examples:

- Squat `knee_collapse` is coached only from `front` or `diagonal`.
- Squat `excessive_forward_lean` is coached only from `side` or `diagonal`.
- Shoulder/triceps back-arch cues are gated to `side` or `diagonal`.
- Low-confidence landmarks suppress the cue instead of producing a false accusation.

## Phase FSM

`taharrak/phase/fsm.py` tracks ordered movement phases with hysteresis and dwell:

- setup/start pose
- movement away from start
- target pose (`TOP_OR_LOCKOUT` or `BOTTOM_OR_STRETCH`)
- return phase
- complete or invalid

The desktop/web runtime uses the full-landmark path and counts only after the expected sequence completes. The legacy narrow-input tracker path is still kept for backward-compatible unit-style callers.

`RepTracker` now exposes the active processing route via `last_processing_path` and `technique_state["processing_path"]` so any fallback to the legacy path is explicit instead of silent.

Current rep-counting semantics are conservative:

- Only completed, valid full-landmark sequences increment `rep_count`.
- Shallow or partial attempts are recorded as non-completion events in `event_log`, not as counted reps.
- Low-confidence or wrong-view faults are suppressed rather than surfaced as form accusations.

## Fault Thresholds

All new exercise-specific thresholds live under `exercise_thresholds` in `config.json`.

Key defaults:

- `squat.trunk_tibia_warn_deg = 10`
- `squat.knee_valgus_warn_deg = 10`
- `lateral_raise.overheight_warn_deg = 110`
- `bicep_curl.upper_arm_flexion_warn_deg = 30`
- `bicep_curl.trunk_swing_warn_deg = 15`
- `shoulder_press.lumbar_extension_warn_deg = 10`
- `shoulder_press.lockout_elbow_angle_min_deg = 165`
- `tricep_extension.lumbar_extension_warn_deg = 10`
- `tricep_extension.elbow_flare_warn_deg = 30`
- `tricep_extension.shoulder_drift_warn_deg = 15`
- `tricep_extension.lockout_elbow_angle_min_deg = 160`

## Known Limitations

- Single-camera 2D pose cannot produce true 3D valgus, flare, or scapular measurements.
- `shrugging` is implemented conservatively and may be suppressed when ear/shoulder visibility is weak or the threshold is unset.
- The legacy 3-landmark tracker path still uses a narrow fallback heuristic for backward compatibility; the real app/web path should pass the full landmark set.

## Adding A New Exercise

1. Add the exercise profile in `taharrak/exercises/`.
2. Add config thresholds under `exercise_thresholds`.
3. Add or reuse kinematic features in `taharrak/kinematics/features.py`.
4. Add phase logic expectations in `taharrak/phase/validators.py`.
5. Add fault rules in `taharrak/faults/rules.py`.
6. Add correction priority/cue mapping in `taharrak/correction.py` and `taharrak/messages.py`.
7. Add tests for geometry, view gating, faults, and rep validation.
