"""Typed containers for pose landmarks and derived kinematics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class LandmarkPoint:
    x: float
    y: float
    z: float | None = None
    visibility: float | None = None
    presence: float | None = None


@dataclass(frozen=True)
class LandmarkQuality:
    score: float
    missing: tuple[str, ...] = ()
    low_confidence: tuple[str, ...] = ()
    usable: bool = True


@dataclass
class KinematicsFrame:
    timestamp: float | None
    side_used: Literal["left", "right", "both", "unknown"]
    view: Literal["front", "side", "diagonal", "unknown"]
    view_confidence: float
    landmark_quality: dict[str, LandmarkQuality] = field(default_factory=dict)
    features: dict[str, float | None] = field(default_factory=dict)
    landmarks: dict[str, LandmarkPoint] = field(default_factory=dict)

    def get(self, name: str, default: Any = None) -> Any:
        return self.features.get(name, default)
