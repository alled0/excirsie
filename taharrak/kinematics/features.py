"""Named biomechanical features derived from pose landmarks."""

from __future__ import annotations

import math

from .confidence import assess_quality, landmark_reliability
from .geometry import (
    angle_between_vectors,
    joint_angle,
    segment_angle_to_horizontal,
    segment_angle_to_vertical,
    signed_segment_angle_to_vertical,
    vector_between,
)
from .landmarks import LandmarkSet
from .types import KinematicsFrame, LandmarkPoint
from .view import infer_view


_QUALITY_GROUPS = {
    "left_arm": ("left_shoulder", "left_elbow", "left_wrist"),
    "right_arm": ("right_shoulder", "right_elbow", "right_wrist"),
    "left_leg": ("left_hip", "left_knee", "left_ankle"),
    "right_leg": ("right_hip", "right_knee", "right_ankle"),
    "torso": ("left_shoulder", "right_shoulder", "left_hip", "right_hip"),
    "head": ("nose", "left_ear", "right_ear"),
}


def _midpoint(a: LandmarkPoint | None, b: LandmarkPoint | None) -> LandmarkPoint | None:
    if a is None or b is None:
        return None
    vis = [value for value in (a.visibility, b.visibility) if value is not None]
    pres = [value for value in (a.presence, b.presence) if value is not None]
    return LandmarkPoint(
        x=(a.x + b.x) / 2.0,
        y=(a.y + b.y) / 2.0,
        z=((a.z or 0.0) + (b.z or 0.0)) / 2.0 if a.z is not None or b.z is not None else None,
        visibility=(sum(vis) / len(vis)) if vis else None,
        presence=(sum(pres) / len(pres)) if pres else None,
    )


def _safe_round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None or math.isnan(value) else round(float(value), digits)


def _segment_ratio(a: LandmarkPoint | None, b: LandmarkPoint | None,
                   c: LandmarkPoint | None, d: LandmarkPoint | None) -> float | None:
    ab = vector_between(a, b)
    cd = vector_between(c, d)
    if ab is None or cd is None:
        return None
    ab_len = math.hypot(ab[0], ab[1])
    cd_len = math.hypot(cd[0], cd[1])
    if cd_len <= 1e-6:
        return None
    return ab_len / cd_len


def _horizontal_alignment_angle(a: LandmarkPoint | None,
                                b: LandmarkPoint | None) -> float | None:
    if a is None or b is None:
        return None
    dx = abs(a.x - b.x)
    dy = abs(a.y - b.y)
    if dy <= 1e-6:
        return 90.0 if dx > 0 else 0.0
    return math.degrees(math.atan2(dx, dy))


def _valgus_proxy(hip: LandmarkPoint | None,
                  knee: LandmarkPoint | None,
                  ankle: LandmarkPoint | None) -> float | None:
    if hip is None or knee is None or ankle is None:
        return None
    mid_x = (hip.x + ankle.x) / 2.0
    vertical = abs(hip.y - ankle.y)
    if vertical <= 1e-6:
        return None
    return math.degrees(math.atan2(abs(knee.x - mid_x), vertical))


def _shoulder_elevation_ratio(shoulder: LandmarkPoint | None,
                              ear: LandmarkPoint | None,
                              hip: LandmarkPoint | None) -> float | None:
    if shoulder is None or ear is None or hip is None:
        return None
    torso = abs(hip.y - shoulder.y)
    if torso <= 1e-6:
        return None
    return max(0.0, 1.0 - (abs(ear.y - shoulder.y) / torso))


def _choose_side(landmarks: LandmarkSet, side: str | None) -> str:
    if side in {"left", "right", "both"}:
        return side
    left_score = min(
        landmark_reliability(landmarks.get(name))
        for name in ("left_shoulder", "left_elbow", "left_wrist", "left_hip", "left_knee", "left_ankle")
    )
    right_score = min(
        landmark_reliability(landmarks.get(name))
        for name in ("right_shoulder", "right_elbow", "right_wrist", "right_hip", "right_knee", "right_ankle")
    )
    if max(left_score, right_score) < 0.35:
        return "unknown"
    return "left" if left_score >= right_score else "right"


def build_kinematics_frame(landmarks_source,
                           timestamp: float | None = None,
                           side: str | None = None) -> KinematicsFrame:
    landmarks = LandmarkSet.from_source(landmarks_source)
    quality = assess_quality(landmarks, _QUALITY_GROUPS)
    view, view_confidence = infer_view(landmarks)

    left_shoulder = landmarks.get("left_shoulder")
    right_shoulder = landmarks.get("right_shoulder")
    left_elbow = landmarks.get("left_elbow")
    right_elbow = landmarks.get("right_elbow")
    left_wrist = landmarks.get("left_wrist")
    right_wrist = landmarks.get("right_wrist")
    left_hip = landmarks.get("left_hip")
    right_hip = landmarks.get("right_hip")
    left_knee = landmarks.get("left_knee")
    right_knee = landmarks.get("right_knee")
    left_ankle = landmarks.get("left_ankle")
    right_ankle = landmarks.get("right_ankle")
    left_ear = landmarks.get("left_ear")
    right_ear = landmarks.get("right_ear")

    shoulder_mid = _midpoint(left_shoulder, right_shoulder)
    hip_mid = _midpoint(left_hip, right_hip)
    trunk_vector = vector_between(shoulder_mid, hip_mid)

    left_upper_arm = vector_between(left_shoulder, left_elbow)
    right_upper_arm = vector_between(right_shoulder, right_elbow)
    left_torso = vector_between(left_shoulder, left_hip)
    right_torso = vector_between(right_shoulder, right_hip)

    left_elbow_angle = joint_angle(left_shoulder, left_elbow, left_wrist)
    right_elbow_angle = joint_angle(right_shoulder, right_elbow, right_wrist)
    left_knee_angle = joint_angle(left_hip, left_knee, left_ankle)
    right_knee_angle = joint_angle(right_hip, right_knee, right_ankle)
    left_hip_angle = joint_angle(left_shoulder, left_hip, left_knee)
    right_hip_angle = joint_angle(right_shoulder, right_hip, right_knee)
    left_shoulder_angle = joint_angle(left_hip, left_shoulder, left_elbow)
    right_shoulder_angle = joint_angle(right_hip, right_shoulder, right_elbow)
    trunk_angle = segment_angle_to_vertical(shoulder_mid, hip_mid)
    trunk_sway_angle = abs(signed_segment_angle_to_vertical(shoulder_mid, hip_mid)) if shoulder_mid and hip_mid else None
    torso_extension_angle = trunk_sway_angle
    shoulder_line_angle = segment_angle_to_horizontal(left_shoulder, right_shoulder)
    hip_line_angle = segment_angle_to_horizontal(left_hip, right_hip)
    left_upper_arm_torso_angle = angle_between_vectors(left_upper_arm, left_torso)
    right_upper_arm_torso_angle = angle_between_vectors(right_upper_arm, right_torso)
    left_forearm_upper_arm_angle = left_elbow_angle
    right_forearm_upper_arm_angle = right_elbow_angle

    left_tibia_angle = segment_angle_to_vertical(left_knee, left_ankle)
    right_tibia_angle = segment_angle_to_vertical(right_knee, right_ankle)
    trunk_tibia_angle_left = (
        abs((trunk_angle or 0.0) - (left_tibia_angle or 0.0))
        if trunk_angle is not None and left_tibia_angle is not None else None
    )
    trunk_tibia_angle_right = (
        abs((trunk_angle or 0.0) - (right_tibia_angle or 0.0))
        if trunk_angle is not None and right_tibia_angle is not None else None
    )
    knee_valgus_proxy_left = _valgus_proxy(left_hip, left_knee, left_ankle)
    knee_valgus_proxy_right = _valgus_proxy(right_hip, right_knee, right_ankle)
    squat_depth_proxy_left = 180.0 - left_knee_angle if left_knee_angle is not None else None
    squat_depth_proxy_right = 180.0 - right_knee_angle if right_knee_angle is not None else None
    left_right_depth_asymmetry = (
        abs((squat_depth_proxy_left or 0.0) - (squat_depth_proxy_right or 0.0))
        if squat_depth_proxy_left is not None and squat_depth_proxy_right is not None else None
    )

    wrist_over_shoulder_alignment_left = _horizontal_alignment_angle(left_wrist, left_shoulder)
    wrist_over_shoulder_alignment_right = _horizontal_alignment_angle(right_wrist, right_shoulder)
    wrist_elbow_alignment_left = _horizontal_alignment_angle(left_wrist, left_elbow)
    wrist_elbow_alignment_right = _horizontal_alignment_angle(right_wrist, right_elbow)
    overhead_lockout_proxy_left = min(
        value for value in (left_elbow_angle, 180.0 - (wrist_over_shoulder_alignment_left or 180.0))
        if value is not None
    ) if left_elbow_angle is not None and wrist_over_shoulder_alignment_left is not None else left_elbow_angle
    overhead_lockout_proxy_right = min(
        value for value in (right_elbow_angle, 180.0 - (wrist_over_shoulder_alignment_right or 180.0))
        if value is not None
    ) if right_elbow_angle is not None and wrist_over_shoulder_alignment_right is not None else right_elbow_angle

    shoulder_abduction_angle_left = left_shoulder_angle
    shoulder_abduction_angle_right = right_shoulder_angle
    elbow_collapse_proxy_left = 180.0 - left_elbow_angle if left_elbow_angle is not None else None
    elbow_collapse_proxy_right = 180.0 - right_elbow_angle if right_elbow_angle is not None else None
    shoulder_elevation_proxy_left = _shoulder_elevation_ratio(left_shoulder, left_ear, left_hip)
    shoulder_elevation_proxy_right = _shoulder_elevation_ratio(right_shoulder, right_ear, right_hip)

    tricep_elbow_angle_left = left_elbow_angle
    tricep_elbow_angle_right = right_elbow_angle
    elbow_flare_proxy_left = _horizontal_alignment_angle(left_wrist, left_elbow)
    elbow_flare_proxy_right = _horizontal_alignment_angle(right_wrist, right_elbow)
    shoulder_drift_proxy_left = left_upper_arm_torso_angle
    shoulder_drift_proxy_right = right_upper_arm_torso_angle

    side_used = _choose_side(landmarks, side)
    active_elbow_angle = left_elbow_angle if side_used == "left" else right_elbow_angle if side_used == "right" else None
    active_upper_arm_torso_angle = (
        left_upper_arm_torso_angle if side_used == "left"
        else right_upper_arm_torso_angle if side_used == "right"
        else None
    )
    shoulder_flexion_compensation_proxy = active_upper_arm_torso_angle

    features = {
        "left_elbow_angle": _safe_round(left_elbow_angle),
        "right_elbow_angle": _safe_round(right_elbow_angle),
        "left_shoulder_angle": _safe_round(left_shoulder_angle),
        "right_shoulder_angle": _safe_round(right_shoulder_angle),
        "left_knee_angle": _safe_round(left_knee_angle),
        "right_knee_angle": _safe_round(right_knee_angle),
        "left_hip_angle": _safe_round(left_hip_angle),
        "right_hip_angle": _safe_round(right_hip_angle),
        "trunk_angle": _safe_round(trunk_angle),
        "trunk_sway_angle": _safe_round(trunk_sway_angle),
        "torso_extension_angle": _safe_round(torso_extension_angle),
        "shoulder_line_angle": _safe_round(shoulder_line_angle),
        "hip_line_angle": _safe_round(hip_line_angle),
        "left_upper_arm_torso_angle": _safe_round(left_upper_arm_torso_angle),
        "right_upper_arm_torso_angle": _safe_round(right_upper_arm_torso_angle),
        "left_forearm_upper_arm_angle": _safe_round(left_forearm_upper_arm_angle),
        "right_forearm_upper_arm_angle": _safe_round(right_forearm_upper_arm_angle),
        "left_tibia_angle": _safe_round(left_tibia_angle),
        "right_tibia_angle": _safe_round(right_tibia_angle),
        "trunk_tibia_angle_left": _safe_round(trunk_tibia_angle_left),
        "trunk_tibia_angle_right": _safe_round(trunk_tibia_angle_right),
        "knee_valgus_proxy_left": _safe_round(knee_valgus_proxy_left),
        "knee_valgus_proxy_right": _safe_round(knee_valgus_proxy_right),
        "squat_depth_proxy_left": _safe_round(squat_depth_proxy_left),
        "squat_depth_proxy_right": _safe_round(squat_depth_proxy_right),
        "left_right_depth_asymmetry": _safe_round(left_right_depth_asymmetry),
        "active_elbow_angle": _safe_round(active_elbow_angle),
        "active_upper_arm_torso_angle": _safe_round(active_upper_arm_torso_angle),
        "trunk_swing_angle": _safe_round(torso_extension_angle),
        "shoulder_flexion_compensation_proxy": _safe_round(shoulder_flexion_compensation_proxy),
        "press_elbow_angle_left": _safe_round(left_elbow_angle),
        "press_elbow_angle_right": _safe_round(right_elbow_angle),
        "wrist_over_shoulder_alignment_left": _safe_round(wrist_over_shoulder_alignment_left),
        "wrist_over_shoulder_alignment_right": _safe_round(wrist_over_shoulder_alignment_right),
        "wrist_elbow_alignment_left": _safe_round(wrist_elbow_alignment_left),
        "wrist_elbow_alignment_right": _safe_round(wrist_elbow_alignment_right),
        "overhead_lockout_proxy_left": _safe_round(overhead_lockout_proxy_left),
        "overhead_lockout_proxy_right": _safe_round(overhead_lockout_proxy_right),
        "shoulder_abduction_angle_left": _safe_round(shoulder_abduction_angle_left),
        "shoulder_abduction_angle_right": _safe_round(shoulder_abduction_angle_right),
        "elbow_collapse_proxy_left": _safe_round(elbow_collapse_proxy_left),
        "elbow_collapse_proxy_right": _safe_round(elbow_collapse_proxy_right),
        "shoulder_elevation_proxy_left": _safe_round(shoulder_elevation_proxy_left),
        "shoulder_elevation_proxy_right": _safe_round(shoulder_elevation_proxy_right),
        "tricep_elbow_angle_left": _safe_round(tricep_elbow_angle_left),
        "tricep_elbow_angle_right": _safe_round(tricep_elbow_angle_right),
        "elbow_flare_proxy_left": _safe_round(elbow_flare_proxy_left),
        "elbow_flare_proxy_right": _safe_round(elbow_flare_proxy_right),
        "shoulder_drift_proxy_left": _safe_round(shoulder_drift_proxy_left),
        "shoulder_drift_proxy_right": _safe_round(shoulder_drift_proxy_right),
    }

    return KinematicsFrame(
        timestamp=timestamp,
        side_used=side_used,
        view=view,
        view_confidence=view_confidence,
        landmark_quality=quality,
        features=features,
        landmarks=landmarks.by_name,
    )
