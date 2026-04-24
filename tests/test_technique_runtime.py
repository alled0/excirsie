import unittest

from taharrak.analysis import build_msgs
from taharrak.exercises import EXERCISES
from taharrak.kinematics.features import build_kinematics_frame
from taharrak.tracker import RepTracker
from tests.helpers_pose import named_landmark_dict


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
            ("3", "raising_too_high", 115.0, 0.5, (0.30, 0.5), (0.40, 0.5), (0.56, 0.5), False),
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

    def test_front_view_squat_knee_collapse_detected(self):
        tracker = RepTracker("center", EXERCISES["5"], CFG)
        tracker.stage = "start"
        tracker.rep_elapsed = 0.7
        frame = build_kinematics_frame(named_landmark_dict({
            "left_shoulder": (0.40, 0.28),
            "right_shoulder": (0.60, 0.28),
            "left_hip": (0.44, 0.52),
            "right_hip": (0.56, 0.52),
            "left_knee": (0.49, 0.72),
            "right_knee": (0.51, 0.72),
            "left_ankle": (0.40, 0.90),
            "right_ankle": (0.60, 0.90),
        }), side="both")

        tracker._update_technique_state(118.0, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), False, landmarks=frame)

        self.assertIn("knee_collapse", tracker.technique_state["faults"])
        self.assertEqual(tracker.technique_state["view"], "front")

    def test_side_view_squat_forward_lean_detected(self):
        tracker = RepTracker("center", EXERCISES["5"], CFG)
        tracker.stage = "start"
        tracker.rep_elapsed = 0.7
        frame = build_kinematics_frame(named_landmark_dict({
            "left_shoulder": (0.48, 0.30),
            "right_shoulder": (0.52, 0.31),
            "left_hip": (0.49, 0.56),
            "right_hip": (0.53, 0.57),
            "left_knee": (0.56, 0.72),
            "right_knee": (0.58, 0.73),
            "left_ankle": (0.64, 0.89),
            "right_ankle": (0.66, 0.90),
        }), side="both")

        tracker._update_technique_state(118.0, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), False, landmarks=frame)

        self.assertIn("excessive_forward_lean", tracker.technique_state["faults"])
        self.assertEqual(tracker.technique_state["view"], "side")

    def test_lateral_raise_overheight_uses_config_threshold(self):
        tracker = RepTracker("right", EXERCISES["3"], CFG)
        tracker.stage = "start"
        tracker.rep_elapsed = 0.5

        tracker._update_technique_state(100.0, (0.30, 0.5), (0.40, 0.5), (0.56, 0.5), False)
        self.assertNotIn("raising_too_high", tracker.technique_state["faults"])

        tracker._update_technique_state(115.0, (0.30, 0.5), (0.40, 0.5), (0.56, 0.5), False)
        self.assertIn("raising_too_high", tracker.technique_state["faults"])

    def test_tricep_shoulder_drift_detected(self):
        tracker = RepTracker("right", EXERCISES["4"], CFG)
        tracker.stage = "start"
        tracker.rep_elapsed = 0.6
        frame = build_kinematics_frame(named_landmark_dict({
            "left_shoulder": (0.48, 0.30),
            "right_shoulder": (0.52, 0.30),
            "left_hip": (0.49, 0.58),
            "right_hip": (0.53, 0.58),
            "right_elbow": (0.68, 0.40),
            "right_wrist": (0.72, 0.57),
        }), side="right")

        tracker._update_technique_state(150.0, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), False, landmarks=frame)

        self.assertIn("shoulder_drift", tracker.technique_state["faults"])

    def test_bicep_drift_no_longer_depends_on_raw_x_offset(self):
        tracker = RepTracker("right", EXERCISES["1"], CFG)
        tracker.stage = "start"
        tracker.rep_elapsed = 0.6
        frame = build_kinematics_frame(named_landmark_dict({
            "left_shoulder": (0.42, 0.31),
            "right_shoulder": (0.50, 0.30),
            "left_hip": (0.44, 0.62),
            "right_hip": (0.51, 0.62),
            "right_elbow": (0.579, 0.33),  # x drift stays below the old 0.08 cutoff
            "right_wrist": (0.61, 0.48),
        }), side="right")

        tracker._update_technique_state(95.0, (0.50, 0.30), (0.579, 0.33), (0.61, 0.48), False, landmarks=frame)

        self.assertIn("upper_arm_drift", tracker.technique_state["faults"])

    def test_low_confidence_suppresses_risky_faults(self):
        tracker = RepTracker("center", EXERCISES["5"], CFG)
        tracker.stage = "start"
        tracker.rep_elapsed = 0.7
        frame = build_kinematics_frame(named_landmark_dict({
            "left_shoulder": (0.48, 0.30, 0.0, 0.2, 0.2),
            "right_shoulder": (0.52, 0.31, 0.0, 0.2, 0.2),
            "left_hip": (0.49, 0.56, 0.0, 0.2, 0.2),
            "right_hip": (0.53, 0.57, 0.0, 0.2, 0.2),
            "left_knee": (0.56, 0.72, 0.0, 0.2, 0.2),
            "right_knee": (0.58, 0.73, 0.0, 0.2, 0.2),
            "left_ankle": (0.64, 0.89, 0.0, 0.2, 0.2),
            "right_ankle": (0.66, 0.90, 0.0, 0.2, 0.2),
        }, default_visibility=0.2, default_presence=0.2), side="both")

        tracker._update_technique_state(118.0, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), False, landmarks=frame)

        self.assertNotIn("excessive_forward_lean", tracker.technique_state["faults"])
        self.assertTrue(
            tracker.technique_state["fault_evaluations"]["excessive_forward_lean"]["suppressed"]
        )


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

    def test_new_knee_collapse_fault_is_coached(self):
        exercise = EXERCISES["5"]
        tracker = _StubTracker(
            side="center",
            faults=("knee_collapse",),
            signals={"end_range": exercise.technique_profile.end_thresholds["knee_angle_deg"]},
        )

        msgs = build_msgs(
            [tracker], [None], [False], exercise, _Voice(), CFG, "en", qualities=["GOOD"]
        )

        self.assertTrue(msgs)
        self.assertIn("knees", msgs[0][0].lower())


if __name__ == "__main__":
    unittest.main()
