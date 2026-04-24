"""Exercise-specific phase labels and invalid-reason helpers."""

from __future__ import annotations

from .base import MovementPhase


_PHASE_NAMES = {
    "1": (MovementPhase.LIFTING, MovementPhase.TOP_OR_LOCKOUT, MovementPhase.LOWERING),
    "2": (MovementPhase.PRESSING, MovementPhase.TOP_OR_LOCKOUT, MovementPhase.LOWERING),
    "3": (MovementPhase.RAISING, MovementPhase.TOP_OR_LOCKOUT, MovementPhase.LOWERING),
    "4": (MovementPhase.EXTENDING, MovementPhase.TOP_OR_LOCKOUT, MovementPhase.LOWERING),
    "5": (MovementPhase.DESCENT, MovementPhase.BOTTOM_OR_STRETCH, MovementPhase.ASCENT),
}

_INVALID_REASON = {
    "1": "incomplete_rom",
    "2": "incomplete_lockout",
    "3": "incomplete_raise",
    "4": "incomplete_extension",
    "5": "insufficient_depth",
}


def phase_triplet(exercise_key: str) -> tuple[MovementPhase, MovementPhase, MovementPhase]:
    return _PHASE_NAMES.get(exercise_key, _PHASE_NAMES["1"])


def incomplete_reason(exercise_key: str) -> str:
    return _INVALID_REASON.get(exercise_key, "incomplete_rom")
