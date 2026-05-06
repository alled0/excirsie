"""Typed fault-engine containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class RepContext:
    side: str
    stage: str | None
    rep_elapsed: float
    in_rep: bool
    angle: float | None
    swinging: bool
    phase: str | None = None
    phase_sequence: tuple[str, ...] = ()
    invalid_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class FaultEvaluation:
    fault: str
    active: bool
    confidence: float
    value: float | None
    threshold: float | None
    suppressed: bool = False
    suppress_reason: str | None = None
    message_key: str | None = None


@dataclass(frozen=True)
class FaultRule:
    fault: str
    exercise: str
    evaluator: Callable
    threshold_key: str | None = None
    required_views: frozenset[str] = field(default_factory=lambda: frozenset({"any"}))
    required_quality_groups: tuple[str, ...] = ()
    minimum_confidence: float = 0.38
    minimum_view_confidence: float = 0.0
    message_key: str | None = None
    # HUD display metadata — "error" renders red, "warning" renders orange.
    # "primary_signal" faults measure ROM directly; "secondary_signals" faults
    # measure form quality and are suppressed under weaker tracking.
    severity: str = "warning"
    signal_kind: str = "secondary_signals"
