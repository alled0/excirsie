"""Schema objects for future learned-quality pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FaultRecord:
    fault: str
    active: bool
    confidence: float
    value: float | None
    threshold: float | None
    suppressed: bool
    suppress_reason: str | None = None


@dataclass(frozen=True)
class RepRecord:
    exercise: str
    rep_index: int | None
    valid: bool
    counted: bool
    start_time: float | None
    end_time: float | None
    view: str
    view_confidence: float
    phase_sequence: tuple[str, ...] = ()
    invalid_reasons: tuple[str, ...] = ()
    faults: tuple[FaultRecord, ...] = ()
    feature_summary: dict[str, float | None] = field(default_factory=dict)
    landmark_quality: dict[str, dict] = field(default_factory=dict)
    thresholds_used: dict[str, float | int | None] = field(default_factory=dict)
    version: str = "1.0"
    schema_version: str = "rep_record.v1"


@dataclass(frozen=True)
class SessionSummary:
    exercise: str
    reps_total: int
    reps_valid: int
    reps_invalid: int
    common_faults: tuple[str, ...] = ()
    records: tuple[RepRecord, ...] = ()
