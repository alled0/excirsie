"""Camera-view inference for single-person pose landmarks."""

from __future__ import annotations

from .confidence import landmark_reliability
from .landmarks import LandmarkSet


def infer_view(landmarks: LandmarkSet) -> tuple[str, float]:
    left_shoulder = landmarks.get("left_shoulder")
    right_shoulder = landmarks.get("right_shoulder")
    left_hip = landmarks.get("left_hip")
    right_hip = landmarks.get("right_hip")

    core_scores = [
        landmark_reliability(point)
        for point in (left_shoulder, right_shoulder, left_hip, right_hip)
        if point is not None
    ]
    if len(core_scores) < 3 or min(core_scores) < 0.35:
        return "unknown", 0.0

    shoulder_width = abs(left_shoulder.x - right_shoulder.x) if left_shoulder and right_shoulder else 0.0
    hip_width = abs(left_hip.x - right_hip.x) if left_hip and right_hip else 0.0
    mean_width = (shoulder_width + hip_width) / 2.0

    if mean_width >= 0.16:
        confidence = min(1.0, 0.55 + (mean_width - 0.16) * 4.0)
        return "front", round(confidence, 3)
    if mean_width <= 0.08:
        confidence = min(1.0, 0.55 + (0.08 - mean_width) * 7.0)
        return "side", round(confidence, 3)
    confidence = max(0.35, 0.8 - abs(mean_width - 0.12) * 6.0)
    return "diagonal", round(confidence, 3)
