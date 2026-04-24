"""Landmark confidence utilities."""

from __future__ import annotations

from .landmarks import LandmarkSet
from .types import LandmarkPoint, LandmarkQuality


def landmark_reliability(point: LandmarkPoint | None) -> float:
    if point is None:
        return 0.0
    visibility = getattr(point, "visibility", 1.0)
    if visibility is None:
        visibility = 1.0
    presence = getattr(point, "presence", None)
    presence = visibility if presence is None else presence
    return float(min(visibility, presence))


def assess_quality(landmarks: LandmarkSet, groups: dict[str, tuple[str, ...]],
                   minimum_confidence: float = 0.38) -> dict[str, LandmarkQuality]:
    quality: dict[str, LandmarkQuality] = {}
    for name, required_points in groups.items():
        missing = []
        low_confidence = []
        scores = []
        for point_name in required_points:
            point = landmarks.get(point_name)
            if point is None:
                missing.append(point_name)
                continue
            score = landmark_reliability(point)
            scores.append(score)
            if score < minimum_confidence:
                low_confidence.append(point_name)
        usable = not missing and not low_confidence
        score = min(scores) if scores else 0.0
        quality[name] = LandmarkQuality(
            score=round(score, 4),
            missing=tuple(missing),
            low_confidence=tuple(low_confidence),
            usable=usable,
        )
    return quality
