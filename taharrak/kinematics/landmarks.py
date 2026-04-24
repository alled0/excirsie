"""Stable landmark accessors for MediaPipe pose landmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .types import LandmarkPoint


LANDMARK_INDEX_TO_NAME: dict[int, str] = {
    0: "nose",
    1: "left_eye_inner",
    2: "left_eye",
    3: "left_eye_outer",
    4: "right_eye_inner",
    5: "right_eye",
    6: "right_eye_outer",
    7: "left_ear",
    8: "right_ear",
    9: "mouth_left",
    10: "mouth_right",
    11: "left_shoulder",
    12: "right_shoulder",
    13: "left_elbow",
    14: "right_elbow",
    15: "left_wrist",
    16: "right_wrist",
    17: "left_pinky",
    18: "right_pinky",
    19: "left_index",
    20: "right_index",
    21: "left_thumb",
    22: "right_thumb",
    23: "left_hip",
    24: "right_hip",
    25: "left_knee",
    26: "right_knee",
    27: "left_ankle",
    28: "right_ankle",
    29: "left_heel",
    30: "right_heel",
    31: "left_foot_index",
    32: "right_foot_index",
}
LANDMARK_NAME_TO_INDEX: dict[str, int] = {
    name: index for index, name in LANDMARK_INDEX_TO_NAME.items()
}


def coerce_landmark_point(value) -> LandmarkPoint | None:
    if value is None:
        return None
    if isinstance(value, LandmarkPoint):
        return value
    if isinstance(value, dict):
        if "x" not in value or "y" not in value:
            return None
        return LandmarkPoint(
            x=float(value["x"]),
            y=float(value["y"]),
            z=float(value["z"]) if value.get("z") is not None else None,
            visibility=float(value["visibility"]) if value.get("visibility") is not None else None,
            presence=float(value["presence"]) if value.get("presence") is not None else None,
        )
    if hasattr(value, "x") and hasattr(value, "y"):
        return LandmarkPoint(
            x=float(value.x),
            y=float(value.y),
            z=float(getattr(value, "z", 0.0)) if getattr(value, "z", None) is not None else None,
            visibility=float(getattr(value, "visibility", 1.0))
            if getattr(value, "visibility", None) is not None else None,
            presence=float(getattr(value, "presence", 1.0))
            if getattr(value, "presence", None) is not None else None,
        )
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return LandmarkPoint(
            x=float(value[0]),
            y=float(value[1]),
            z=float(value[2]) if len(value) > 2 and value[2] is not None else None,
            visibility=float(value[3]) if len(value) > 3 and value[3] is not None else None,
            presence=float(value[4]) if len(value) > 4 and value[4] is not None else None,
        )
    return None


@dataclass(frozen=True)
class LandmarkSet:
    by_name: dict[str, LandmarkPoint]

    @classmethod
    def from_source(cls, landmarks) -> "LandmarkSet":
        if isinstance(landmarks, LandmarkSet):
            return landmarks
        mapping: dict[str, LandmarkPoint] = {}
        if isinstance(landmarks, dict):
            for key, value in landmarks.items():
                point = coerce_landmark_point(value)
                if point is None:
                    continue
                if isinstance(key, int):
                    name = LANDMARK_INDEX_TO_NAME.get(key)
                    if name is not None:
                        mapping[name] = point
                else:
                    mapping[str(key)] = point
            return cls(mapping)
        if isinstance(landmarks, Iterable):
            for index, value in enumerate(landmarks):
                name = LANDMARK_INDEX_TO_NAME.get(index)
                point = coerce_landmark_point(value)
                if name is not None and point is not None:
                    mapping[name] = point
        return cls(mapping)

    def get(self, name: str) -> LandmarkPoint | None:
        if name in self.by_name:
            return self.by_name[name]
        alias = LANDMARK_INDEX_TO_NAME.get(LANDMARK_NAME_TO_INDEX.get(name, -1))
        if alias is not None:
            return self.by_name.get(alias)
        return None

    def midpoint(self, left_name: str, right_name: str) -> LandmarkPoint | None:
        left = self.get(left_name)
        right = self.get(right_name)
        if left is None or right is None:
            return None
        vis_values = [v for v in (left.visibility, right.visibility) if v is not None]
        pres_values = [v for v in (left.presence, right.presence) if v is not None]
        return LandmarkPoint(
            x=(left.x + right.x) / 2.0,
            y=(left.y + right.y) / 2.0,
            z=((left.z or 0.0) + (right.z or 0.0)) / 2.0 if left.z is not None or right.z is not None else None,
            visibility=(sum(vis_values) / len(vis_values)) if vis_values else None,
            presence=(sum(pres_values) / len(pres_values)) if pres_values else None,
        )
