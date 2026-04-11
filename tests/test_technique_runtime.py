import unittest

from taharrak.analysis import build_msgs
from taharrak.exercises import EXERCISES
from taharrak.tracker import RepTracker


CFG = {
    "camera_fps": 30,
    "one_euro_min_cutoff": 1.5,
    "one_euro_beta": 0.007,
    "one_euro_d_cutoff": 1.0,
    "swing_window": 15,
    "confidence_smoother_window": 3,
    "fatigue_score_gap": 20,
    "fsm_recovery_frames": 3,
    "fsm_max_lost_frames": 15,
    "min_rep_time": 1.2,
}


class _Voice:
    def say(self, *args, **kwargs):
        pass


class _StubTracker:
    def __init__(self, side="right", stage=None, rep_elapsed=0.0, faults=(), signals=None):
        self.side = side
        self.stage = stage
        self.rep_elapsed = rep_elapsed
        self.technique_state = {
            "faults": tuple(faults),
            "signals": signals or {},
            "view": "unknown",
        }


class TestTechniqueScoring(unittest.TestCase):
    def test_profile_thresholds_drive_rom_penalty(self):
        tracker = RepTracker("right", EXERCISES["1"], CFG)
        tracker._rep_max_a = 145.0
        tracker._rep_min_a = 90.0

        breakdown = tracker._build_score_breakdown(duration=1.5, warmup_mode=False)

        self.assertGreater(breakdown["rom"], 0)
        self.assertEqual(
            set(breakdown.keys()),
            {"rom", "tempo", "sway_drift", "asymmetry", "instability", "score"},
        )


class TestTechniqueFaultDetection(unittest.TestCase):
    def test_representative_faults_detected_per_exercise(self):
        cases = [
            ("1", "upper_arm_drift", 100.0, 0.5, (0.20, 0.5), (0.32, 0.5), (0.40, 0.5), False),
            ("2", "wrist_elbow_misstacking", 130.0, 0.5, (0.30, 0.5), (0.40, 0.5), (0.56, 0.5), False),
            ("3", "raising_too_high", 110.0, 0.5, (0.30, 0.5), (0.40, 0.5), (0.56, 0.5), False),
            ("4", "elbow_flare", 130.0, 0.5, (0.30, 0.5), (0.40, 0.5), (0.56, 0.5), False),
            ("5", "insufficient_depth", 140.0, 0.6, (0.30, 0.5), (0.40, 0.5), (0.56, 0.5), False),
        ]

        for key, expected_fault, angle, elapsed, p_n, v_n, d_n, swinging in cases:
            with self.subTest(exercise=key, fault=expected_fault):
                tracker = RepTracker("right", EXERCISES[key], CFG)
                tracker.stage = "start"
                tracker.rep_elapsed = elapsed
                tracker._update_technique_state(angle, p_n, v_n, d_n, swinging)
                self.assertIn(expected_fault, tracker.technique_state["faults"])


class TestTechniqueFeedbackSelection(unittest.TestCase):
    def test_profile_cue_selected_for_representative_faults(self):
        cases = [
            ("1", "upper_arm_drift", "Keep your upper arm still"),
            ("2", "incomplete_lockout", "Finish overhead"),
            ("3", "raising_too_high", "Raise to shoulder height"),
            ("4", "elbow_flare", "Keep elbows in"),
            ("5", "insufficient_depth", "Sit deeper"),
        ]

        for key, fault, text in cases:
            with self.subTest(exercise=key, fault=fault):
                exercise = EXERCISES[key]
                tracker = _StubTracker(
                    side="right",
                    faults=(fault,),
                    signals={"end_range": exercise.technique_profile.end_thresholds.get("elbow_angle_deg", exercise.technique_profile.end_thresholds.get("shoulder_abduction_deg", exercise.technique_profile.end_thresholds.get("knee_angle_deg", (0.0, 0.0))))},
                )
                msgs = build_msgs(
                    [tracker], [None], [False], exercise, _Voice(), CFG, "en", qualities=["GOOD"]
                )
                self.assertTrue(msgs)
                self.assertIn(text, msgs[0][0])

    def test_secondary_signal_fault_suppressed_under_weak_quality(self):
        exercise = EXERCISES["2"]
        tracker = _StubTracker(
            faults=("wrist_elbow_misstacking",),
            signals={"end_range": exercise.technique_profile.end_thresholds["elbow_angle_deg"]},
        )

        msgs = build_msgs(
            [tracker], [None], [False], exercise, _Voice(), CFG, "en", qualities=["WEAK"]
        )

        self.assertEqual(msgs, [])

    def test_unmapped_or_view_unreliable_fault_is_not_coached(self):
        exercise = EXERCISES["5"]
        tracker = _StubTracker(
            side="center",
            faults=("knee_collapse",),
            signals={"end_range": exercise.technique_profile.end_thresholds["knee_angle_deg"]},
        )

        msgs = build_msgs(
            [tracker], [None], [False], exercise, _Voice(), CFG, "en", qualities=["GOOD"]
        )

        self.assertEqual(msgs, [])


if __name__ == "__main__":
    unittest.main()
