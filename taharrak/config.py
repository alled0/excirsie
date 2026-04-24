"""
Shared configuration helpers for Taharrak.

This module centralises config loading so the desktop app, offline evaluator,
and web model service all see the same defaults and exercise thresholds.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any


DEFAULT_EXERCISE_THRESHOLDS: dict[str, dict[str, Any]] = {
    "squat": {
        "trunk_tibia_warn_deg": 10.0,
        "knee_valgus_warn_deg": 10.0,
        "depth_min_knee_flexion_deg": 90.0,
        "full_depth_knee_flexion_deg": 110.0,
    },
    "bicep_curl": {
        "upper_arm_flexion_warn_deg": 30.0,
        "trunk_swing_warn_deg": 15.0,
    },
    "shoulder_press": {
        "lumbar_extension_warn_deg": 10.0,
        "lockout_elbow_angle_min_deg": 165.0,
        "wrist_elbow_alignment_warn_deg": 20.0,
    },
    "lateral_raise": {
        "overheight_warn_deg": 110.0,
        "elbow_collapse_warn_deg": 35.0,
        "shrug_warn_ratio": None,
    },
    "tricep_extension": {
        "lumbar_extension_warn_deg": 10.0,
        "elbow_flare_warn_deg": 30.0,
        "shoulder_drift_warn_deg": 15.0,
        "lockout_elbow_angle_min_deg": 160.0,
    },
}


DEFAULT_CONFIG: dict[str, Any] = {
    "angle_down": 160,
    "angle_up": 45,
    "swing_threshold": 0.025,
    "swing_window": 15,
    "vis_good": 0.68,
    "vis_weak": 0.38,
    "rest_duration": 60,
    "countdown_secs": 3,
    "score_flash_duration": 2.5,
    "symmetry_warn_ratio": 0.15,
    "summary_auto_close": 12,
    "target_reps": 12,
    "ideal_rep_time": 2.5,
    "min_rep_time": 1.2,
    "mirror_mode": True,
    "voice_enabled": True,
    "voice_rate": 160,
    "confidence_smoother_window": 10,
    "fatigue_score_gap": 20,
    "overload_sessions_needed": 3,
    "overload_min_avg_score": 75,
    "overload_step_kg": 2.5,
    "weight_step_kg": 2.5,
    "weight_min_kg": 0.0,
    "weight_max_kg": 200.0,
    "db_path": "~/.taharrak/sessions.db",
    "arabic_font_path": "assets/Noto_Naskh_Arabic/static/NotoNaskhArabic-Regular.ttf",
    "default_language": "en",
    "warmup_mode": True,
    "landmark_smooth_window": 7,
    "segmentation_enabled": True,
    "segmentation_bg_color": [10, 10, 25],
    "camera_fps": 30,
    "one_euro_min_cutoff": 1.5,
    "one_euro_beta": 0.007,
    "one_euro_d_cutoff": 1.0,
    "fsm_recovery_frames": 3,
    "fsm_max_lost_frames": 15,
    "legacy_upper_arm_offset_warn_norm": 0.08,
    "legacy_wrist_elbow_offset_warn_norm": 0.10,
    "exercise_thresholds": copy.deepcopy(DEFAULT_EXERCISE_THRESHOLDS),
}


_EXERCISE_NAME_ALIASES: dict[str, str] = {
    "1": "bicep_curl",
    "2": "shoulder_press",
    "3": "lateral_raise",
    "4": "tricep_extension",
    "5": "squat",
    "curl": "bicep_curl",
    "press": "shoulder_press",
    "lateral": "lateral_raise",
    "tricep": "tricep_extension",
    "triceps": "tricep_extension",
}

_FLAT_THRESHOLD_ALIASES: dict[tuple[str, str], tuple[str, ...]] = {
    ("squat", "trunk_tibia_warn_deg"): ("squat_trunk_tibia_warn_deg",),
    ("squat", "knee_valgus_warn_deg"): ("squat_knee_valgus_warn_deg",),
    ("squat", "depth_min_knee_flexion_deg"): ("squat_depth_min_knee_flexion_deg",),
    ("squat", "full_depth_knee_flexion_deg"): ("squat_full_depth_knee_flexion_deg",),
    ("bicep_curl", "upper_arm_flexion_warn_deg"): ("bicep_curl_upper_arm_flexion_warn_deg",),
    ("bicep_curl", "trunk_swing_warn_deg"): ("bicep_curl_trunk_swing_warn_deg",),
    ("shoulder_press", "lumbar_extension_warn_deg"): ("shoulder_press_lumbar_extension_warn_deg",),
    ("shoulder_press", "lockout_elbow_angle_min_deg"): ("shoulder_press_lockout_elbow_angle_min_deg",),
    ("shoulder_press", "wrist_elbow_alignment_warn_deg"): ("shoulder_press_wrist_elbow_alignment_warn_deg",),
    ("lateral_raise", "overheight_warn_deg"): (
        "lateral_raise_overheight_warn_deg",
        "raising_too_high_warn_deg",
    ),
    ("lateral_raise", "elbow_collapse_warn_deg"): ("lateral_raise_elbow_collapse_warn_deg",),
    ("lateral_raise", "shrug_warn_ratio"): ("lateral_raise_shrug_warn_ratio",),
    ("tricep_extension", "lumbar_extension_warn_deg"): ("tricep_extension_lumbar_extension_warn_deg",),
    ("tricep_extension", "elbow_flare_warn_deg"): ("tricep_extension_elbow_flare_warn_deg",),
    ("tricep_extension", "shoulder_drift_warn_deg"): ("tricep_extension_shoulder_drift_warn_deg",),
    ("tricep_extension", "lockout_elbow_angle_min_deg"): ("tricep_extension_lockout_elbow_angle_min_deg",),
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_exercise_name(exercise: str | None) -> str:
    if not exercise:
        return ""
    name = str(exercise).strip().lower()
    return _EXERCISE_NAME_ALIASES.get(name, name)


def _coerce_threshold_value(default: Any, value: Any) -> Any:
    if value is None:
        return None if default is None else default

    if isinstance(default, bool):
        return value if isinstance(value, bool) else default

    if isinstance(default, (int, float)) and not isinstance(default, bool):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return default
        return default

    if default is None:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None

    return value


def merge_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    cfg.setdefault("exercise_thresholds", {})
    for exercise_name, defaults in DEFAULT_EXERCISE_THRESHOLDS.items():
        current = cfg["exercise_thresholds"].get(exercise_name, {})
        cfg["exercise_thresholds"][exercise_name] = _deep_merge(defaults, current)
    return cfg


def load_config(path: str | None = "config.json") -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg_path = path or "config.json"
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as handle:
            user_cfg = json.load(handle)
        cfg = _deep_merge(cfg, user_cfg)
    return merge_config(cfg)


def get_exercise_thresholds(exercise: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    name = normalize_exercise_name(exercise)
    merged = merge_config(cfg)
    thresholds = copy.deepcopy(DEFAULT_EXERCISE_THRESHOLDS.get(name, {}))
    thresholds.update(merged.get("exercise_thresholds", {}).get(name, {}))
    for key, aliases in _FLAT_THRESHOLD_ALIASES.items():
        exercise_name, threshold_key = key
        if exercise_name != name:
            continue
        for alias in aliases:
            if alias in merged:
                thresholds[threshold_key] = merged[alias]
                break
    defaults = DEFAULT_EXERCISE_THRESHOLDS.get(name, {})
    for threshold_key, default in defaults.items():
        thresholds[threshold_key] = _coerce_threshold_value(
            default,
            thresholds.get(threshold_key, default),
        )
    return thresholds


def get_threshold(exercise: str, key: str, cfg: dict[str, Any] | None = None,
                  default: Any = None) -> Any:
    return get_exercise_thresholds(exercise, cfg).get(key, default)
