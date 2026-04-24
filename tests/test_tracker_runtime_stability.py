import json
import unittest

from taharrak.exercises import EXERCISES
from taharrak.tracker import OneEuroLandmarkSmoother, RepTracker
from tests.helpers_pose import (
    make_bicep_curl_landmarks,
    make_lateral_raise_landmarks,
    make_side_squat_landmarks,
)


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
    "fsm_phase_hysteresis_deg": 6.0,
    "fsm_phase_min_dwell_frames": 2,
    "min_rep_time": 1.2,
}


def _drive_tracker(tracker, exercise, landmarks_seq, dt: float = 0.15):
    now = 0.0
    joint_triplet = exercise.joints_right
    swing_joint = exercise.swing_joint_right
    for frame in landmarks_seq:
        now += dt
        a, b, c = joint_triplet
        tracker.update(
            frame[a], frame[b], frame[c], frame[swing_joint], 1280, 720,
            now=now, landmarks=frame,
        )


class TestTrackerRuntimeStability(unittest.TestCase):
    def test_jittery_full_landmark_curl_counts_once(self):
        exercise = EXERCISES["1"]
        tracker = RepTracker("right", exercise, CFG)
        frames = [
            make_bicep_curl_landmarks(angle)
            for angle in (165, 165, 130, 90, 50, 20, 20, 20, 20, 50, 90, 130, 165, 165, 165, 165, 165)
        ]

        _drive_tracker(tracker, exercise, frames, dt=0.25)

        self.assertEqual(tracker.rep_count, 1)
        self.assertEqual(len(tracker.all_rep_logs()), 1)
        self.assertEqual(tracker.last_processing_path, "kinematics")

    def test_synthetic_squat_replay_produces_serializable_structured_record(self):
        exercise = EXERCISES["5"]
        tracker = RepTracker("center", exercise, CFG | {"min_rep_time": 1.5})
        frames = [
            make_side_squat_landmarks(angle, trunk_lean_deg=5.0)
            for angle in (170, 170, 150, 120, 90, 70, 60, 60, 60, 90, 120, 150, 170, 170, 170, 170)
        ]

        _drive_tracker(tracker, exercise, frames, dt=0.25)

        self.assertEqual(tracker.rep_count, 1)
        self.assertTrue(tracker.last_phase_validation is not None)
        self.assertGreaterEqual(len(tracker.last_phase_validation.phase_sequence), 1)
        structured_records = tracker.all_structured_rep_logs()
        self.assertEqual(len(structured_records), 1)
        self.assertEqual(structured_records[0].schema_version, "rep_record.v1")
        payload = tracker.all_rep_logs()[0]["structured_record"]
        encoded = json.dumps(payload)
        self.assertNotIn("raw_landmarks", encoded)
        self.assertNotIn("video", encoded.lower())

    def test_filtered_near_threshold_faults_do_not_flicker_wildly(self):
        exercise = EXERCISES["3"]
        tracker = RepTracker("right", exercise, CFG)
        smoother = OneEuroLandmarkSmoother(
            num_landmarks=33,
            freq=30.0,
            min_cutoff=CFG["one_euro_min_cutoff"],
            beta=CFG["one_euro_beta"],
        )
        states = []
        now = 0.0

        for raw_angle in (109.4, 110.6, 109.7, 110.4, 109.8, 110.5, 109.9):
            now += 0.10
            smoothed = smoother.smooth(make_lateral_raise_landmarks(raw_angle))
            a, b, c = exercise.joints_right
            tracker.update(
                smoothed[a], smoothed[b], smoothed[c], smoothed[exercise.swing_joint_right],
                1280, 720, now=now, landmarks=smoothed,
            )
            states.append("raising_too_high" in tracker.technique_state["faults"])

        transitions = sum(states[i] != states[i - 1] for i in range(1, len(states)))
        self.assertLessEqual(transitions, 2)

    def test_performance_smoke_full_landmark_path_stays_bounded(self):
        exercise = EXERCISES["1"]
        tracker = RepTracker("right", exercise, CFG)
        frame = make_bicep_curl_landmarks(165.0)
        a, b, c = exercise.joints_right

        for i in range(1000):
            tracker.update(
                frame[a], frame[b], frame[c], frame[exercise.swing_joint_right],
                1280, 720, now=(i + 1) / 30.0, landmarks=frame,
            )

        self.assertEqual(tracker.processing_path_counts["kinematics"], 1000)
        self.assertEqual(tracker.rep_count, 0)
        self.assertEqual(len(tracker.all_rep_logs()), 0)
        self.assertEqual(len(tracker.all_event_logs()), 0)


if __name__ == "__main__":
    unittest.main()
