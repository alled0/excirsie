"""Exercise-specific fault rules."""

from __future__ import annotations

from taharrak.config import get_threshold
from taharrak.faults.types import FaultRule


def _get_feature(frame, *names):
    values = [frame.get(name) for name in names if frame.get(name) is not None]
    if not values:
        return None
    return max(values)


def _side_feature(frame, context, left_name: str, right_name: str) -> float | None:
    if context.side == "left":
        return frame.get(left_name)
    if context.side == "right":
        return frame.get(right_name)
    return frame.get(left_name) if frame.side_used == "left" else frame.get(right_name)


def _value_threshold(value, threshold, *, greater_than: bool = True) -> bool:
    if value is None or threshold is None:
        return False
    return value > threshold if greater_than else value < threshold


def _upper_arm_drift(frame, context, cfg):
    value = frame.get("active_upper_arm_torso_angle")
    threshold = get_threshold("bicep_curl", "upper_arm_flexion_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _bicep_trunk_swing(frame, context, cfg):
    value = frame.get("trunk_swing_angle")
    threshold = get_threshold("bicep_curl", "trunk_swing_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _incomplete_rom(frame, context, cfg):
    if not context.in_rep or context.rep_elapsed <= 0.35 or context.angle is None:
        return False, context.angle, None
    threshold = 75.0
    return context.angle > threshold, context.angle, threshold


def _shoulder_press_back_arch(frame, context, cfg):
    value = frame.get("torso_extension_angle")
    threshold = get_threshold("shoulder_press", "lumbar_extension_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _incomplete_lockout(frame, context, cfg):
    if not context.in_rep:
        return False, None, None
    value = _side_feature(frame, context, "press_elbow_angle_left", "press_elbow_angle_right")
    threshold = get_threshold("shoulder_press", "lockout_elbow_angle_min_deg", cfg)
    return _value_threshold(value, threshold, greater_than=False), value, threshold


def _wrist_elbow_misstacking(frame, context, cfg):
    value = _side_feature(frame, context, "wrist_elbow_alignment_left", "wrist_elbow_alignment_right")
    threshold = get_threshold("shoulder_press", "wrist_elbow_alignment_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _raising_too_high(frame, context, cfg):
    value = _side_feature(frame, context, "shoulder_abduction_angle_left", "shoulder_abduction_angle_right")
    threshold = get_threshold("lateral_raise", "overheight_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _elbow_collapse(frame, context, cfg):
    value = _side_feature(frame, context, "elbow_collapse_proxy_left", "elbow_collapse_proxy_right")
    threshold = get_threshold("lateral_raise", "elbow_collapse_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _shrugging(frame, context, cfg):
    value = _side_feature(frame, context, "shoulder_elevation_proxy_left", "shoulder_elevation_proxy_right")
    threshold = get_threshold("lateral_raise", "shrug_warn_ratio", cfg)
    return _value_threshold(value, threshold), value, threshold


def _tricep_elbow_flare(frame, context, cfg):
    value = _side_feature(frame, context, "elbow_flare_proxy_left", "elbow_flare_proxy_right")
    threshold = get_threshold("tricep_extension", "elbow_flare_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _tricep_shoulder_drift(frame, context, cfg):
    value = _side_feature(frame, context, "shoulder_drift_proxy_left", "shoulder_drift_proxy_right")
    threshold = get_threshold("tricep_extension", "shoulder_drift_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _tricep_back_arch(frame, context, cfg):
    value = frame.get("torso_extension_angle")
    threshold = get_threshold("tricep_extension", "lumbar_extension_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _incomplete_extension(frame, context, cfg):
    if not context.in_rep:
        return False, None, None
    value = _side_feature(frame, context, "tricep_elbow_angle_left", "tricep_elbow_angle_right")
    threshold = get_threshold("tricep_extension", "lockout_elbow_angle_min_deg", cfg)
    return _value_threshold(value, threshold, greater_than=False), value, threshold


def _insufficient_depth(frame, context, cfg):
    if not context.in_rep:
        return False, None, None
    depth = _get_feature(frame, "squat_depth_proxy_left", "squat_depth_proxy_right")
    threshold = get_threshold("squat", "depth_min_knee_flexion_deg", cfg)
    return _value_threshold(depth, threshold, greater_than=False), depth, threshold


def _excessive_forward_lean(frame, context, cfg):
    value = _get_feature(frame, "trunk_tibia_angle_left", "trunk_tibia_angle_right")
    threshold = get_threshold("squat", "trunk_tibia_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


def _knee_collapse(frame, context, cfg):
    value = _get_feature(frame, "knee_valgus_proxy_left", "knee_valgus_proxy_right")
    threshold = get_threshold("squat", "knee_valgus_warn_deg", cfg)
    return _value_threshold(value, threshold), value, threshold


FAULT_RULES: dict[str, tuple[FaultRule, ...]] = {
    "1": (
        FaultRule("upper_arm_drift", "bicep_curl", _upper_arm_drift,
                  threshold_key="upper_arm_flexion_warn_deg",
                  required_views=frozenset({"front", "side", "diagonal"}),
                  required_quality_groups=("torso", "right_arm", "left_arm"),
                  message_key="keep_upper_arm_still"),
        FaultRule("trunk_swing", "bicep_curl", _bicep_trunk_swing,
                  threshold_key="trunk_swing_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso",),
                  minimum_view_confidence=0.35,
                  message_key="dont_swing_body"),
        FaultRule("incomplete_rom", "bicep_curl", _incomplete_rom,
                  message_key="curl_higher"),
    ),
    "2": (
        FaultRule("excessive_lean_back", "shoulder_press", _shoulder_press_back_arch,
                  threshold_key="lumbar_extension_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso",),
                  minimum_view_confidence=0.35,
                  message_key="dont_lean_back"),
        FaultRule("incomplete_lockout", "shoulder_press", _incomplete_lockout,
                  threshold_key="lockout_elbow_angle_min_deg",
                  required_quality_groups=("left_arm", "right_arm"),
                  message_key="finish_overhead"),
        FaultRule("wrist_elbow_misstacking", "shoulder_press", _wrist_elbow_misstacking,
                  threshold_key="wrist_elbow_alignment_warn_deg",
                  required_quality_groups=("left_arm", "right_arm"),
                  message_key="stack_wrists_over_elbows"),
    ),
    "3": (
        FaultRule("raising_too_high", "lateral_raise", _raising_too_high,
                  threshold_key="overheight_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="raise_to_shoulder_height"),
        FaultRule("shrugging", "lateral_raise", _shrugging,
                  threshold_key="shrug_warn_ratio",
                  required_views=frozenset({"front"}),
                  required_quality_groups=("torso", "head"),
                  minimum_view_confidence=0.45,
                  message_key="shoulders_down"),
        FaultRule("elbow_collapse", "lateral_raise", _elbow_collapse,
                  threshold_key="elbow_collapse_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="keep_soft_bend"),
    ),
    "4": (
        FaultRule("elbow_flare", "tricep_extension", _tricep_elbow_flare,
                  threshold_key="elbow_flare_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="keep_elbows_in"),
        FaultRule("shoulder_drift", "tricep_extension", _tricep_shoulder_drift,
                  threshold_key="shoulder_drift_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso", "left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="keep_shoulders_still"),
        FaultRule("excessive_lean_back", "tricep_extension", _tricep_back_arch,
                  threshold_key="lumbar_extension_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso",),
                  minimum_view_confidence=0.35,
                  message_key="dont_lean_back"),
        FaultRule("incomplete_extension", "tricep_extension", _incomplete_extension,
                  threshold_key="lockout_elbow_angle_min_deg",
                  required_quality_groups=("left_arm", "right_arm"),
                  message_key="finish_extension"),
    ),
    "5": (
        FaultRule("insufficient_depth", "squat", _insufficient_depth,
                  threshold_key="depth_min_knee_flexion_deg",
                  required_quality_groups=("left_leg", "right_leg"),
                  message_key="sit_deeper"),
        FaultRule("excessive_forward_lean", "squat", _excessive_forward_lean,
                  threshold_key="trunk_tibia_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso", "left_leg", "right_leg"),
                  minimum_view_confidence=0.35,
                  message_key="chest_up"),
        FaultRule("knee_collapse", "squat", _knee_collapse,
                  threshold_key="knee_valgus_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_leg", "right_leg"),
                  minimum_view_confidence=0.35,
                  message_key="knees_over_toes"),
    ),
}
