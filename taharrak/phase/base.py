"""Core phase types for rep validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MovementPhase(str, Enum):
    SETUP = "SETUP"
    START = "START"
    DESCENT = "DESCENT"
    ASCENT = "ASCENT"
    LOWERING = "LOWERING"
    LIFTING = "LIFTING"
    PRESSING = "PRESSING"
    RAISING = "RAISING"
    EXTENDING = "EXTENDING"
    BOTTOM_OR_STRETCH = "BOTTOM_OR_STRETCH"
    TOP_OR_LOCKOUT = "TOP_OR_LOCKOUT"
    COMPLETE = "COMPLETE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class RepValidationResult:
    counted: bool
    valid: bool
    phase: str
    phase_sequence: tuple[str, ...]
    invalid_reasons: tuple[str, ...]
    faults: tuple[str, ...]
    confidence: float
    rep_index: int | None = None
    started: bool = False
