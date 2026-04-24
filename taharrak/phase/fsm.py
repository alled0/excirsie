"""Deterministic phase FSM for conservative rep validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from taharrak.phase.base import MovementPhase, RepValidationResult
from taharrak.phase.validators import incomplete_reason, phase_triplet


@dataclass
class ExercisePhaseFSM:
    exercise: object
    cfg: dict
    hysteresis_deg: float = field(init=False)
    dwell_frames: int = field(init=False)
    rep_index: int = 0

    def __post_init__(self) -> None:
        self.hysteresis_deg = float(self.cfg.get("fsm_phase_hysteresis_deg", 6.0))
        self.dwell_frames = int(self.cfg.get("fsm_phase_min_dwell_frames", 2))
        self.reset()

    def reset(self) -> None:
        self.phase = MovementPhase.SETUP.value
        self.phase_sequence: list[str] = []
        self._last_angle: float | None = None
        self._ready = False
        self._rep_active = False
        self._target_reached = False
        self._departed_start = False
        self._start_pose_frames = 0
        self._target_pose_frames = 0
        self._await_departure = False

    def _append_phase(self, phase: MovementPhase | str) -> None:
        value = phase.value if isinstance(phase, MovementPhase) else str(phase)
        if not self.phase_sequence or self.phase_sequence[-1] != value:
            self.phase_sequence.append(value)
        self.phase = value

    def _is_start_pose(self, angle: float) -> bool:
        if self.exercise.invert:
            return angle <= self.exercise.angle_down + self.hysteresis_deg
        return angle >= self.exercise.angle_down - self.hysteresis_deg

    def _is_target_pose(self, angle: float) -> bool:
        if self.exercise.invert:
            return angle >= self.exercise.angle_up - self.hysteresis_deg
        return angle <= self.exercise.angle_up + self.hysteresis_deg

    def update(self, angle: float, confidence: float = 1.0) -> RepValidationResult:
        move_phase, target_phase, return_phase = phase_triplet(self.exercise.key)
        start_pose = self._is_start_pose(angle)
        target_pose = self._is_target_pose(angle)

        self._start_pose_frames = self._start_pose_frames + 1 if start_pose else 0
        self._target_pose_frames = self._target_pose_frames + 1 if target_pose else 0

        if self._last_angle is None:
            self._last_angle = angle

        counted = False
        valid = False
        invalid_reasons: tuple[str, ...] = ()
        started = False

        if start_pose:
            self._append_phase(MovementPhase.START)
            if self._start_pose_frames >= self.dwell_frames:
                self._ready = True
            if self._await_departure:
                self._last_angle = angle
                return RepValidationResult(
                    counted=False,
                    valid=False,
                    phase=self.phase,
                    phase_sequence=tuple(self.phase_sequence),
                    invalid_reasons=(),
                    faults=(),
                    confidence=round(confidence, 3),
                    rep_index=self.rep_index,
                )

        if not self._rep_active and self._ready and not start_pose:
            self._rep_active = True
            self._target_reached = False
            self._departed_start = True
            self._await_departure = False
            started = True
            self._append_phase(move_phase)

        if self._rep_active:
            if not self._target_reached:
                self._append_phase(move_phase)
                if self._target_pose_frames >= self.dwell_frames:
                    self._target_reached = True
                    self._append_phase(target_phase)
                elif self._departed_start and self._start_pose_frames >= self.dwell_frames:
                    self._rep_active = False
                    self._await_departure = True
                    self._ready = True
                    self._append_phase(MovementPhase.INVALID)
                    invalid_reasons = (incomplete_reason(self.exercise.key),)
            else:
                if not start_pose:
                    self._append_phase(return_phase)
                if self._start_pose_frames >= self.dwell_frames:
                    self._rep_active = False
                    self._target_reached = False
                    self._ready = True
                    self._await_departure = True
                    self.rep_index += 1
                    self._append_phase(MovementPhase.COMPLETE)
                    counted = True
                    valid = True

        self._last_angle = angle
        return RepValidationResult(
            counted=counted,
            valid=valid,
            phase=self.phase,
            phase_sequence=tuple(self.phase_sequence),
            invalid_reasons=invalid_reasons,
            faults=(),
            confidence=round(confidence, 3),
            rep_index=self.rep_index if counted else self.rep_index or None,
            started=started,
        )
