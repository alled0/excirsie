import unittest
from unittest.mock import patch

import numpy as np

import taharrak.ui as ui
from taharrak.analysis import build_msgs
from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.tracker import LiveDiagnostics, LiveTrustGate


class _Voice:
    def say(self, *args, **kwargs):
        pass


class _Tracker:
    def __init__(self, side="left", stage=None, rep_elapsed=0.0, rep_count=0):
        self.side = side
        self.stage = stage
        self.rep_elapsed = rep_elapsed
        self.rep_count = rep_count
        self.form_scores = []

    @property
    def avg_score(self):
        return 0.0

    def is_fatigued(self):
        return False


class TestLiveTrustGate(unittest.TestCase):
    def test_trust_levels_escalate_with_stable_good_frames(self):
        gate = LiveTrustGate({
            "trust_count_frames": 1,
            "trust_coach_frames": 4,
            "trust_mismatch_tolerance": 1,
        }, bilateral=True)

        s1 = gate.update(["GOOD", "GOOD"], [False, False])
        s2 = gate.update(["GOOD", "GOOD"], [False, False])
        s4 = gate.update(["GOOD", "GOOD"], [False, False])
        s4 = gate.update(["GOOD", "GOOD"], [False, False])

        self.assertTrue(s1.render_allowed)
        self.assertTrue(s1.counting_allowed)
        self.assertFalse(s1.coaching_allowed)
        self.assertTrue(s2.counting_allowed)
        self.assertFalse(s2.coaching_allowed)
        self.assertTrue(s4.coaching_allowed)
        self.assertTrue(s4.bilateral_compare_allowed)

    def test_weak_or_mismatched_sides_disable_counting_and_comparison(self):
        gate = LiveTrustGate({
            "trust_count_frames": 1,
            "trust_coach_frames": 3,
            "trust_mismatch_tolerance": 1,
        }, bilateral=True)
        for _ in range(3):
            state = gate.update(["GOOD", "GOOD"], [False, False])
        self.assertTrue(state.bilateral_compare_allowed)

        weak = gate.update(["GOOD", "WEAK"], [False, False])
        self.assertTrue(weak.render_allowed)
        self.assertTrue(weak.counting_allowed)
        self.assertFalse(weak.coaching_allowed)
        self.assertFalse(weak.bilateral_compare_allowed)
        self.assertTrue(weak.counting_sides[0])
        self.assertTrue(weak.counting_sides[1])
        self.assertFalse(weak.coaching_sides[1])

    def test_single_side_trust_requires_only_relevant_side(self):
        gate = LiveTrustGate({
            "trust_count_frames": 1,
            "trust_coach_frames": 3,
        }, bilateral=False)
        state = gate.update(["GOOD"], [False])
        self.assertTrue(state.counting_allowed)
        self.assertTrue(state.counting_sides[0])
        self.assertFalse(state.coaching_allowed)

    def test_lost_side_blocks_only_that_side_for_counting(self):
        gate = LiveTrustGate({
            "trust_count_frames": 1,
            "trust_coach_frames": 3,
        }, bilateral=True)
        state = gate.update(["GOOD", "LOST"], [False, False])
        self.assertTrue(state.counting_sides[0])
        self.assertFalse(state.counting_sides[1])
        self.assertFalse(state.coaching_allowed)
        self.assertFalse(state.bilateral_compare_allowed)

    def test_counting_can_unlock_before_smoothed_coaching_quality(self):
        gate = LiveTrustGate({
            "trust_count_frames": 1,
            "trust_coach_frames": 3,
        }, bilateral=True)
        state = gate.update(["LOST", "LOST"], [False, False],
                            count_qualities=["WEAK", "LOST"])
        self.assertTrue(state.render_allowed)
        self.assertTrue(state.counting_allowed)
        self.assertTrue(state.counting_sides[0])
        self.assertFalse(state.coaching_allowed)
        self.assertFalse(state.coaching_sides[0])

    def test_recovery_does_not_deadlock_counting(self):
        gate = LiveTrustGate({
            "trust_count_frames": 1,
            "trust_coach_frames": 3,
        }, bilateral=False)
        blocked = gate.update(["GOOD"], [True], count_qualities=["WEAK"])
        recovered = gate.update(["GOOD"], [False], count_qualities=["WEAK"])
        self.assertFalse(blocked.counting_allowed)
        self.assertTrue(recovered.counting_allowed)


class TestCoachingFallback(unittest.TestCase):
    def test_build_msgs_returns_setup_guidance_before_coaching_is_allowed(self):
        trust_gate = LiveTrustGate({
            "trust_count_frames": 2,
            "trust_coach_frames": 5,
        }, bilateral=True)
        trust = trust_gate.update(["WEAK", "GOOD"], [False, False])
        msgs = build_msgs(
            [_Tracker("left", stage="start"), _Tracker("right", stage="start")],
            [170.0, 170.0],
            [True, True],
            BICEP_CURL,
            _Voice(),
            {"min_rep_time": 1.2},
            "en",
            qualities=["WEAK", "GOOD"],
            trust=trust,
            cam_feedback=["cam_too_far"],
        )
        text = " ".join(msg for msg, _ in msgs)
        self.assertIn("Step forward", text)
        self.assertNotIn("Extend fully", text)
        self.assertNotIn("swing", text.lower())


class TestLiveDiagnostics(unittest.TestCase):
    def test_snapshot_reports_fps_dt_jitter_and_quality_fractions(self):
        diag = LiveDiagnostics(window=4)
        diag.update(0.020, ["GOOD", "GOOD"], [False, False])
        diag.update(0.030, ["WEAK", "GOOD"], [True, False])
        diag.update(0.010, ["LOST", "GOOD"], [False, False])
        snap = diag.snapshot()

        self.assertAlmostEqual(snap["dt_ms"], 20.0, delta=0.1)
        self.assertAlmostEqual(snap["fps"], 50.0, delta=0.5)
        self.assertGreater(snap["jitter_ms"], 0.0)
        self.assertAlmostEqual(snap["weak_frac"], 1 / 3, delta=0.01)
        self.assertAlmostEqual(snap["lost_frac"], 1 / 3, delta=0.01)
        self.assertAlmostEqual(snap["recovery_frac"], 1 / 3, delta=0.01)


class TestUiSuppression(unittest.TestCase):
    def test_bilateral_ui_hides_angles_tempo_and_lagging_warning_when_disallowed(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        captured = []
        left = _Tracker("left", stage="start", rep_elapsed=0.6, rep_count=5)
        right = _Tracker("right", stage="start", rep_elapsed=0.6, rep_count=2)

        with patch.object(ui, "put", side_effect=lambda img, text, *a, **k: captured.append(text)):
            ui.screen_workout_bilateral(
                frame, left, right,
                111.0, 111.0, False, False,
                "GOOD", "WEAK", 1,
                {}, [], BICEP_CURL, {"target_reps": 12, "min_rep_time": 1.2}, "en",
                angle_visible=(False, False),
                tempo_visible=(False, False),
                comparison_allowed=False,
            )

        combined = " | ".join(captured)
        self.assertNotIn("111", combined)
        self.assertNotIn("TEMPO", combined)
        self.assertNotIn("lagging", combined.lower())

    def test_single_ui_hides_unstable_angle_and_tempo(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        captured = []
        tracker = _Tracker("center", stage="start", rep_elapsed=0.5, rep_count=1)

        with patch.object(ui, "put", side_effect=lambda img, text, *a, **k: captured.append(text)):
            ui.screen_workout_single(
                frame, tracker, 111.0, False, "WEAK", 1, {}, [],
                BICEP_CURL, {"target_reps": 12, "min_rep_time": 1.2}, "en",
                angle_visible=False, tempo_visible=False,
            )

        combined = " | ".join(captured)
        self.assertNotIn("111", combined)
        self.assertNotIn("TEMPO", combined)


if __name__ == "__main__":
    unittest.main()
