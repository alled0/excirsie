"""Fault evaluation on top of shared kinematics features."""

from __future__ import annotations

from taharrak.faults.rules import FAULT_RULES
from taharrak.faults.types import FaultEvaluation, RepContext


class FaultEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def _gate(self, frame, rule) -> tuple[bool, str | None]:
        if rule.required_views != frozenset({"any"}):
            if frame.view == "unknown" or frame.view not in rule.required_views:
                return False, "view_unreliable"
            if frame.view_confidence < rule.minimum_view_confidence:
                return False, "view_low_confidence"
        for group in rule.required_quality_groups:
            quality = frame.landmark_quality.get(group)
            if quality is None:
                return False, "missing_landmarks"
            if quality.score < rule.minimum_confidence or not quality.usable:
                return False, "low_landmark_confidence"
        return True, None

    def evaluate(self, exercise, frame, context: RepContext) -> list[FaultEvaluation]:
        evaluations: list[FaultEvaluation] = []
        for rule in FAULT_RULES.get(exercise.key, ()):
            allowed, reason = self._gate(frame, rule)
            if not allowed:
                evaluations.append(FaultEvaluation(
                    fault=rule.fault,
                    active=False,
                    confidence=0.0,
                    value=None,
                    threshold=None,
                    suppressed=True,
                    suppress_reason=reason,
                    message_key=rule.message_key,
                ))
                continue

            active, value, threshold = rule.evaluator(frame, context, self.cfg)
            if threshold is None and rule.threshold_key is not None:
                evaluations.append(FaultEvaluation(
                    fault=rule.fault,
                    active=False,
                    confidence=0.0,
                    value=value,
                    threshold=threshold,
                    suppressed=True,
                    suppress_reason="threshold_unavailable",
                    message_key=rule.message_key,
                ))
                continue

            if value is None:
                evaluations.append(FaultEvaluation(
                    fault=rule.fault,
                    active=False,
                    confidence=0.0,
                    value=value,
                    threshold=threshold,
                    suppressed=True,
                    suppress_reason="feature_unavailable",
                    message_key=rule.message_key,
                ))
                continue

            confidence = frame.view_confidence if frame.view != "unknown" else 0.4
            for group in rule.required_quality_groups:
                confidence = min(confidence, frame.landmark_quality[group].score)
            evaluations.append(FaultEvaluation(
                fault=rule.fault,
                active=bool(active),
                confidence=round(confidence, 3),
                value=round(float(value), 3) if value is not None else None,
                threshold=round(float(threshold), 3) if threshold is not None else None,
                suppressed=False,
                suppress_reason=None,
                message_key=rule.message_key,
            ))
        return evaluations
