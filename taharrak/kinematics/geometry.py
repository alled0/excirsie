"""Low-level geometry helpers for 2D/2.5D landmark calculations."""

from __future__ import annotations

import math

from .types import LandmarkPoint


def _coords(point: LandmarkPoint | None) -> tuple[float, float, float | None] | None:
    if point is None:
        return None
    return point.x, point.y, point.z


def vector_between(a: LandmarkPoint | None,
                   b: LandmarkPoint | None) -> tuple[float, float, float | None] | None:
    """
    Return the vector from landmark ``a`` to landmark ``b``.

    Coordinates are assumed to be MediaPipe-normalised image coordinates where
    ``x`` increases rightward and ``y`` increases downward.
    """
    c1 = _coords(a)
    c2 = _coords(b)
    if c1 is None or c2 is None:
        return None
    z1 = c1[2]
    z2 = c2[2]
    z = None if z1 is None or z2 is None else z2 - z1
    return c2[0] - c1[0], c2[1] - c1[1], z


def _vector_length(vector: tuple[float, float, float | None] | None) -> float | None:
    if vector is None:
        return None
    x, y, z = vector
    if z is None:
        return math.hypot(x, y)
    return math.sqrt(x * x + y * y + z * z)


def angle_between_vectors(v1: tuple[float, float, float | None] | None,
                          v2: tuple[float, float, float | None] | None) -> float | None:
    if v1 is None or v2 is None:
        return None
    len1 = _vector_length(v1)
    len2 = _vector_length(v2)
    if not len1 or not len2:
        return None
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    if v1[2] is not None and v2[2] is not None:
        dot += v1[2] * v2[2]
    cos_theta = dot / (len1 * len2)
    cos_theta = max(-1.0, min(1.0, cos_theta))
    return math.degrees(math.acos(cos_theta))


def joint_angle(a: LandmarkPoint | None, b: LandmarkPoint | None,
                c: LandmarkPoint | None) -> float | None:
    """Return the angle at landmark ``b`` in degrees."""
    return angle_between_vectors(vector_between(b, a), vector_between(b, c))


def segment_angle_to_vertical(a: LandmarkPoint | None,
                              b: LandmarkPoint | None) -> float | None:
    """
    Absolute angle between segment ``a -> b`` and image vertical.

    ``0`` means vertical, ``90`` means horizontal.
    """
    vector = vector_between(a, b)
    if vector is None:
        return None
    reference = (0.0, 1.0, 0.0 if vector[2] is not None else None)
    return angle_between_vectors(vector, reference)


def segment_angle_to_horizontal(a: LandmarkPoint | None,
                                b: LandmarkPoint | None) -> float | None:
    """
    Absolute angle between segment ``a -> b`` and image horizontal.

    ``0`` means horizontal, ``90`` means vertical.
    """
    vector = vector_between(a, b)
    if vector is None:
        return None
    reference = (1.0, 0.0, 0.0 if vector[2] is not None else None)
    return angle_between_vectors(vector, reference)


def signed_2d_angle(v1: tuple[float, float, float | None] | None,
                    v2: tuple[float, float, float | None] | None) -> float | None:
    if v1 is None or v2 is None:
        return None
    x1, y1 = v1[0], v1[1]
    x2, y2 = v2[0], v2[1]
    if math.isclose(x1, 0.0, abs_tol=1e-9) and math.isclose(y1, 0.0, abs_tol=1e-9):
        return None
    if math.isclose(x2, 0.0, abs_tol=1e-9) and math.isclose(y2, 0.0, abs_tol=1e-9):
        return None
    angle = math.degrees(math.atan2(x1 * y2 - y1 * x2, x1 * x2 + y1 * y2))
    return angle


def signed_segment_angle_to_vertical(a: LandmarkPoint | None,
                                     b: LandmarkPoint | None) -> float | None:
    vector = vector_between(a, b)
    if vector is None:
        return None
    return math.degrees(math.atan2(vector[0], vector[1]))
