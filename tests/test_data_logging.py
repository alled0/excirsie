import json
import unittest

from taharrak.data_logging import (
    FaultRecord,
    RepRecord,
    SessionSummary,
    fault_record_to_dict,
    rep_record_to_dict,
    session_summary_to_dict,
)
from taharrak.exercises import EXERCISES
from taharrak.tracker import RepTracker
from tests.helpers_pose import make_side_squat_landmarks


class TestDataLogging(unittest.TestCase):
    def test_rep_record_serializes_to_json(self):
        record = RepRecord(
            exercise="1",
            rep_index=1,
            valid=True,
            counted=True,
            start_time=1.0,
            end_time=2.0,
            view="front",
            view_confidence=0.9,
            phase_sequence=("START", "LIFTING", "TOP_OR_LOCKOUT", "LOWERING", "COMPLETE"),
            faults=(FaultRecord("upper_arm_drift", True, 0.8, 42.0, 30.0, False, None),),
            feature_summary={"active_upper_arm_torso_angle": 42.0},
            landmark_quality={"right_arm": {"score": 0.9, "usable": True}},
            thresholds_used={"upper_arm_flexion_warn_deg": 30.0},
        )

        payload = rep_record_to_dict(record)
        encoded = json.dumps(payload)

        self.assertIn("upper_arm_drift", encoded)
        self.assertNotIn("landmarks", encoded.lower())

    def test_fault_record_includes_suppress_reason(self):
        record = FaultRecord(
            fault="knee_collapse",
            active=False,
            confidence=0.0,
            value=None,
            threshold=10.0,
            suppressed=True,
            suppress_reason="view_unreliable",
        )

        payload = fault_record_to_dict(record)

        self.assertEqual(payload["suppress_reason"], "view_unreliable")

    def test_session_summary_exports_without_raw_landmarks(self):
        record = RepRecord(
            exercise="5",
            rep_index=1,
            valid=False,
            counted=False,
            start_time=1.0,
            end_time=1.8,
            view="side",
            view_confidence=0.8,
            invalid_reasons=("insufficient_depth",),
        )
        summary = SessionSummary(
            exercise="5",
            reps_total=1,
            reps_valid=0,
            reps_invalid=1,
            common_faults=("insufficient_depth",),
            records=(record,),
        )

        payload = session_summary_to_dict(summary)
        encoded = json.dumps(payload)

        self.assertIn("insufficient_depth", encoded)
        self.assertNotIn("raw_landmarks", encoded)

    def test_tracker_structured_logs_are_typed_and_json_safe(self):
        cfg = {
            "camera_fps": 30,
            "one_euro_min_cutoff": 1.5,
            "one_euro_beta": 0.007,
            "one_euro_d_cutoff": 1.0,
            "swing_window": 15,
            "confidence_smoother_window": 3,
            "fatigue_score_gap": 20,
            "fsm_recovery_frames": 3,
            "fsm_max_lost_frames": 15,
            "min_rep_time": 1.5,
        }
        exercise = EXERCISES["5"]
        tracker = RepTracker("center", exercise, cfg)
        now = 0.0

        for angle in (170, 170, 150, 120, 90, 70, 60, 60, 60, 90, 120, 150, 170, 170, 170, 170):
            now += 0.25
            frame = make_side_squat_landmarks(angle)
            a, b, c = exercise.joints_right
            tracker.update(
                frame[a], frame[b], frame[c], frame[exercise.swing_joint_right],
                1280, 720, now=now, landmarks=frame,
            )

        records = tracker.all_structured_rep_logs()
        self.assertEqual(len(records), 1)
        self.assertIsInstance(records[0], RepRecord)
        payload = tracker.all_rep_logs()[0]["structured_record"]
        encoded = json.dumps(payload)
        self.assertNotIn("video", encoded.lower())
        self.assertNotIn("raw_landmarks", encoded.lower())


if __name__ == "__main__":
    unittest.main()
