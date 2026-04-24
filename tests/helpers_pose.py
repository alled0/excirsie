"""Synthetic landmark helpers for pose-based unit tests."""

from __future__ import annotations

import math
from dataclasses import dataclass

from taharrak.kinematics.landmarks import LANDMARK_INDEX_TO_NAME, LANDMARK_NAME_TO_INDEX


@dataclass
class FakeLandmark:
    x: float = 0.5
    y: float = 0.5
    z: float = 0.0
    visibility: float = 0.99
    presence: float = 0.99


def make_landmark(x: float, y: float, z: float = 0.0,
                  visibility: float = 0.99,
                  presence: float = 0.99) -> FakeLandmark:
    return FakeLandmark(x=x, y=y, z=z, visibility=visibility, presence=presence)


def make_landmark_list(overrides: dict[str | int, FakeLandmark | tuple | dict],
                       default_visibility: float = 0.99,
                       default_presence: float = 0.99) -> list[FakeLandmark]:
    landmarks = [
        FakeLandmark(visibility=default_visibility, presence=default_presence)
        for _ in range(33)
    ]
    for key, value in overrides.items():
        if isinstance(key, str):
            index = LANDMARK_NAME_TO_INDEX[key]
        else:
            index = key
        if isinstance(value, FakeLandmark):
            landmarks[index] = value
        elif isinstance(value, dict):
            landmarks[index] = make_landmark(
                value["x"], value["y"], value.get("z", 0.0),
                value.get("visibility", default_visibility),
                value.get("presence", default_presence),
            )
        else:
            x, y = value[0], value[1]
            z = value[2] if len(value) > 2 else 0.0
            visibility = value[3] if len(value) > 3 else default_visibility
            presence = value[4] if len(value) > 4 else default_presence
            landmarks[index] = make_landmark(x, y, z, visibility, presence)
    return landmarks


def named_landmark_dict(overrides: dict[str, FakeLandmark | tuple | dict],
                        default_visibility: float = 0.99,
                        default_presence: float = 0.99) -> dict[str, FakeLandmark]:
    named: dict[str, FakeLandmark] = {
        name: FakeLandmark(visibility=default_visibility, presence=default_presence)
        for name in LANDMARK_NAME_TO_INDEX
    }
    for name, value in overrides.items():
        if isinstance(value, FakeLandmark):
            named[name] = value
        elif isinstance(value, dict):
            named[name] = make_landmark(
                value["x"], value["y"], value.get("z", 0.0),
                value.get("visibility", default_visibility),
                value.get("presence", default_presence),
            )
        else:
            x, y = value[0], value[1]
            z = value[2] if len(value) > 2 else 0.0
            visibility = value[3] if len(value) > 3 else default_visibility
            presence = value[4] if len(value) > 4 else default_presence
            named[name] = make_landmark(x, y, z, visibility, presence)
    return named


def _rotate(origin: tuple[float, float], length: float, degrees_clockwise_from_down: float) -> tuple[float, float]:
    radians = math.radians(degrees_clockwise_from_down)
    return (
        origin[0] + (length * math.sin(radians)),
        origin[1] + (length * math.cos(radians)),
    )


def make_lateral_raise_landmarks(abduction_deg: float,
                                 visibility: float = 0.99,
                                 presence: float = 0.99) -> list[FakeLandmark]:
    left_shoulder = (0.40, 0.34)
    right_shoulder = (0.60, 0.34)
    left_hip = (0.40, 0.64)
    right_hip = (0.60, 0.64)
    arm_length = 0.24

    right_elbow = _rotate(right_shoulder, arm_length, abduction_deg)
    left_elbow = (
        left_shoulder[0] - (right_elbow[0] - right_shoulder[0]),
        right_elbow[1],
    )
    right_wrist = _rotate(right_elbow, 0.18, abduction_deg)
    left_wrist = (
        left_elbow[0] - (right_wrist[0] - right_elbow[0]),
        right_wrist[1],
    )

    return make_landmark_list({
        "left_shoulder": (*left_shoulder, 0.0, visibility, presence),
        "right_shoulder": (*right_shoulder, 0.0, visibility, presence),
        "left_hip": (*left_hip, 0.0, visibility, presence),
        "right_hip": (*right_hip, 0.0, visibility, presence),
        "left_elbow": (*left_elbow, 0.0, visibility, presence),
        "right_elbow": (*right_elbow, 0.0, visibility, presence),
        "left_wrist": (*left_wrist, 0.0, visibility, presence),
        "right_wrist": (*right_wrist, 0.0, visibility, presence),
        "nose": (0.50, 0.18, 0.0, visibility, presence),
        "left_ear": (0.46, 0.20, 0.0, visibility, presence),
        "right_ear": (0.54, 0.20, 0.0, visibility, presence),
    }, default_visibility=visibility, default_presence=presence)


def make_bicep_curl_landmarks(elbow_angle_deg: float,
                              torso_sway_deg: float = 0.0,
                              visibility: float = 0.99,
                              presence: float = 0.99) -> list[FakeLandmark]:
    hip_mid = (0.50, 0.68)
    shoulder_mid = _rotate(hip_mid, 0.28, 180.0 + torso_sway_deg)
    left_shoulder = (shoulder_mid[0] - 0.07, shoulder_mid[1])
    right_shoulder = (shoulder_mid[0] + 0.07, shoulder_mid[1])
    left_hip = (hip_mid[0] - 0.06, hip_mid[1])
    right_hip = (hip_mid[0] + 0.06, hip_mid[1])
    right_elbow = (right_shoulder[0], right_shoulder[1] + 0.20)
    left_elbow = (left_shoulder[0], left_shoulder[1] + 0.20)

    delta = max(0.0, min(180.0, 180.0 - elbow_angle_deg))
    right_wrist = _rotate(right_elbow, 0.18, delta)
    left_wrist = (left_elbow[0] - (right_wrist[0] - right_elbow[0]), right_wrist[1])

    return make_landmark_list({
        "left_shoulder": (*left_shoulder, 0.0, visibility, presence),
        "right_shoulder": (*right_shoulder, 0.0, visibility, presence),
        "left_hip": (*left_hip, 0.0, visibility, presence),
        "right_hip": (*right_hip, 0.0, visibility, presence),
        "left_elbow": (*left_elbow, 0.0, visibility, presence),
        "right_elbow": (*right_elbow, 0.0, visibility, presence),
        "left_wrist": (*left_wrist, 0.0, visibility, presence),
        "right_wrist": (*right_wrist, 0.0, visibility, presence),
        "nose": (0.50, shoulder_mid[1] - 0.10, 0.0, visibility, presence),
    }, default_visibility=visibility, default_presence=presence)


def make_side_squat_landmarks(knee_angle_deg: float,
                              trunk_lean_deg: float = 5.0,
                              visibility: float = 0.99,
                              presence: float = 0.99) -> list[FakeLandmark]:
    right_knee = (0.58, 0.72)
    ankle_dir = 78.0
    hip_dir = ankle_dir + knee_angle_deg
    right_ankle = (
        right_knee[0] + 0.18 * math.cos(math.radians(ankle_dir)),
        right_knee[1] + 0.18 * math.sin(math.radians(ankle_dir)),
    )
    right_hip = (
        right_knee[0] + 0.24 * math.cos(math.radians(hip_dir)),
        right_knee[1] + 0.24 * math.sin(math.radians(hip_dir)),
    )
    right_shoulder = (
        right_hip[0] - 0.24 * math.sin(math.radians(trunk_lean_deg)),
        right_hip[1] - 0.24 * math.cos(math.radians(trunk_lean_deg)),
    )

    left_knee = (right_knee[0] - 0.03, right_knee[1] + 0.01)
    left_ankle = (right_ankle[0] - 0.03, right_ankle[1] + 0.01)
    left_hip = (right_hip[0] - 0.03, right_hip[1] + 0.01)
    left_shoulder = (right_shoulder[0] - 0.03, right_shoulder[1] + 0.01)

    return make_landmark_list({
        "left_shoulder": (*left_shoulder, 0.0, visibility, presence),
        "right_shoulder": (*right_shoulder, 0.0, visibility, presence),
        "left_hip": (*left_hip, 0.0, visibility, presence),
        "right_hip": (*right_hip, 0.0, visibility, presence),
        "left_knee": (*left_knee, 0.0, visibility, presence),
        "right_knee": (*right_knee, 0.0, visibility, presence),
        "left_ankle": (*left_ankle, 0.0, visibility, presence),
        "right_ankle": (*right_ankle, 0.0, visibility, presence),
        "nose": (right_shoulder[0] - 0.01, right_shoulder[1] - 0.12, 0.0, visibility, presence),
    }, default_visibility=visibility, default_presence=presence)
