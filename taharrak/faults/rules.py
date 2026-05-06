"""Exercise-specific fault rules.

Evaluator functions receive a pre-resolved ``thresholds`` dict (keyed by
threshold name, e.g. ``"upper_arm_flexion_warn_deg"``) rather than the raw
cfg dict.  The dict is built once per exercise per FaultEngine instance by
``FaultEngine._get_thresholds()`` and cached, so there is no per-frame
``deepcopy`` overhead.
"""

from __future__ import annotations

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


def _upper_arm_drift(frame, context, thresholds):
    value = frame.get("active_upper_arm_torso_angle")
    threshold = thresholds.get("upper_arm_flexion_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _bicep_trunk_swing(frame, context, thresholds):
    value = frame.get("trunk_swing_angle")
    threshold = thresholds.get("trunk_swing_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _incomplete_rom(frame, context, thresholds):
    if not context.in_rep or context.rep_elapsed <= 0.35 or context.angle is None:
        return False, context.angle, None
    threshold = 75.0
    return context.angle > threshold, context.angle, threshold


def _shoulder_press_back_arch(frame, context, thresholds):
    value = frame.get("torso_extension_angle")
    threshold = thresholds.get("lumbar_extension_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _incomplete_lockout(frame, context, thresholds):
    if not context.in_rep:
        return False, None, None
    value = _side_feature(frame, context, "press_elbow_angle_left", "press_elbow_angle_right")
    threshold = thresholds.get("lockout_elbow_angle_min_deg")
    return _value_threshold(value, threshold, greater_than=False), value, threshold


def _wrist_elbow_misstacking(frame, context, thresholds):
    value = _side_feature(frame, context, "wrist_elbow_alignment_left", "wrist_elbow_alignment_right")
    threshold = thresholds.get("wrist_elbow_alignment_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _raising_too_high(frame, context, thresholds):
    value = _side_feature(frame, context, "shoulder_abduction_angle_left", "shoulder_abduction_angle_right")
    threshold = thresholds.get("overheight_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _elbow_collapse(frame, context, thresholds):
    value = _side_feature(frame, context, "elbow_collapse_proxy_left", "elbow_collapse_proxy_right")
    threshold = thresholds.get("elbow_collapse_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _shrugging(frame, context, thresholds):
    value = _side_feature(frame, context, "shoulder_elevation_proxy_left", "shoulder_elevation_proxy_right")
    threshold = thresholds.get("shrug_warn_ratio")
    return _value_threshold(value, threshold), value, threshold


def _tricep_elbow_flare(frame, context, thresholds):
    value = _side_feature(frame, context, "elbow_flare_proxy_left", "elbow_flare_proxy_right")
    threshold = thresholds.get("elbow_flare_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _tricep_shoulder_drift(frame, context, thresholds):
    value = _side_feature(frame, context, "shoulder_drift_proxy_left", "shoulder_drift_proxy_right")
    threshold = thresholds.get("shoulder_drift_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _tricep_back_arch(frame, context, thresholds):
    value = frame.get("torso_extension_angle")
    threshold = thresholds.get("lumbar_extension_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _incomplete_extension(frame, context, thresholds):
    if not context.in_rep:
        return False, None, None
    value = _side_feature(frame, context, "tricep_elbow_angle_left", "tricep_elbow_angle_right")
    threshold = thresholds.get("lockout_elbow_angle_min_deg")
    return _value_threshold(value, threshold, greater_than=False), value, threshold


def _insufficient_depth(frame, context, thresholds):
    if not context.in_rep:
        return False, None, None
    depth = _get_feature(frame, "squat_depth_proxy_left", "squat_depth_proxy_right")
    threshold = thresholds.get("depth_min_knee_flexion_deg")
    return _value_threshold(depth, threshold, greater_than=False), depth, threshold


def _excessive_forward_lean(frame, context, thresholds):
    value = _get_feature(frame, "trunk_tibia_angle_left", "trunk_tibia_angle_right")
    threshold = thresholds.get("trunk_tibia_warn_deg")
    return _value_threshold(value, threshold), value, threshold


def _knee_collapse(frame, context, thresholds):
    value = _get_feature(frame, "knee_valgus_proxy_left", "knee_valgus_proxy_right")
    threshold = thresholds.get("knee_valgus_warn_deg")
    return _value_threshold(value, threshold), value, threshold


FAULT_RULES: dict[str, tuple[FaultRule, ...]] = {
    "1": (
        FaultRule("upper_arm_drift", "bicep_curl", _upper_arm_drift,
                  threshold_key="upper_arm_flexion_warn_deg",
                  required_views=frozenset({"front", "side", "diagonal"}),
                  required_quality_groups=("torso", "right_arm", "left_arm"),
                  message_key="keep_upper_arm_still",
                  severity="warning", signal_kind="secondary_signals"),
        FaultRule("trunk_swing", "bicep_curl", _bicep_trunk_swing,
                  threshold_key="trunk_swing_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso",),
                  minimum_view_confidence=0.35,
                  message_key="dont_swing_body",
                  severity="error", signal_kind="secondary_signals"),
        FaultRule("incomplete_rom", "bicep_curl", _incomplete_rom,
                  message_key="curl_higher",
                  severity="warning", signal_kind="primary_signal"),
    ),
    "2": (
        FaultRule("excessive_lean_back", "shoulder_press", _shoulder_press_back_arch,
                  threshold_key="lumbar_extension_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso",),
                  minimum_view_confidence=0.35,
                  message_key="dont_lean_back",
                  severity="error", signal_kind="secondary_signals"),
        FaultRule("incomplete_lockout", "shoulder_press", _incomplete_lockout,
                  threshold_key="lockout_elbow_angle_min_deg",
                  required_quality_groups=("left_arm", "right_arm"),
                  message_key="finish_overhead",
                  severity="warning", signal_kind="primary_signal"),
        FaultRule("wrist_elbow_misstacking", "shoulder_press", _wrist_elbow_misstacking,
                  threshold_key="wrist_elbow_alignment_warn_deg",
                  required_quality_groups=("left_arm", "right_arm"),
                  message_key="stack_wrists_over_elbows",
                  severity="warning", signal_kind="secondary_signals"),
    ),
    "3": (
        FaultRule("raising_too_high", "lateral_raise", _raising_too_high,
                  threshold_key="overheight_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="raise_to_shoulder_height",
                  severity="warning", signal_kind="primary_signal"),
        FaultRule("shrugging", "lateral_raise", _shrugging,
                  threshold_key="shrug_warn_ratio",
                  required_views=frozenset({"front"}),
                  required_quality_groups=("torso", "head"),
                  minimum_view_confidence=0.45,
                  message_key="shoulders_down",
                  severity="warning", signal_kind="secondary_signals"),
        FaultRule("elbow_collapse", "lateral_raise", _elbow_collapse,
                  threshold_key="elbow_collapse_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="keep_soft_bend",
                  severity="warning", signal_kind="secondary_signals"),
    ),
    "4": (
        FaultRule("elbow_flare", "tricep_extension", _tricep_elbow_flare,
                  threshold_key="elbow_flare_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="keep_elbows_in",
                  severity="warning", signal_kind="secondary_signals"),
        FaultRule("shoulder_drift", "tricep_extension", _tricep_shoulder_drift,
                  threshold_key="shoulder_drift_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso", "left_arm", "right_arm"),
                  minimum_view_confidence=0.35,
                  message_key="keep_shoulders_still",
                  severity="warning", signal_kind="secondary_signals"),
        FaultRule("excessive_lean_back", "tricep_extension", _tricep_back_arch,
                  threshold_key="lumbar_extension_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso",),
                  minimum_view_confidence=0.35,
                  message_key="dont_lean_back",
                  severity="error", signal_kind="secondary_signals"),
        FaultRule("incomplete_extension", "tricep_extension", _incomplete_extension,
                  threshold_key="lockout_elbow_angle_min_deg",
                  required_quality_groups=("left_arm", "right_arm"),
                  message_key="finish_extension",
                  severity="warning", signal_kind="primary_signal"),
    ),
    "5": (
        FaultRule("insufficient_depth", "squat", _insufficient_depth,
                  threshold_key="depth_min_knee_flexion_deg",
                  required_quality_groups=("left_leg", "right_leg"),
                  message_key="sit_deeper",
                  severity="warning", signal_kind="primary_signal"),
        FaultRule("excessive_forward_lean", "squat", _excessive_forward_lean,
                  threshold_key="trunk_tibia_warn_deg",
                  required_views=frozenset({"side", "diagonal"}),
                  required_quality_groups=("torso", "left_leg", "right_leg"),
                  minimum_view_confidence=0.35,
                  message_key="chest_up",
                  severity="warning", signal_kind="secondary_signals"),
        FaultRule("knee_collapse", "squat", _knee_collapse,
                  threshold_key="knee_valgus_warn_deg",
                  required_views=frozenset({"front", "diagonal"}),
                  required_quality_groups=("left_leg", "right_leg"),
                  minimum_view_confidence=0.35,
                  message_key="knees_over_toes",
                  severity="error", signal_kind="secondary_signals"),
    ),
}
