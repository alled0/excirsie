import unittest

from taharrak.exercises import EXERCISES
from taharrak.tracker import RepTracker
from tests.helpers_pose import make_bicep_curl_landmarks, make_landmark


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


class TestTrackerProcessingPaths(unittest.TestCase):
    def test_full_landmark_update_uses_kinematics_path(self):
        tracker = RepTracker("right", EXERCISES["1"], CFG)
        landmarks = make_bicep_curl_landmarks(160.0)
        a, b, c = EXERCISES["1"].joints_right

        tracker.update(
            landmarks[a], landmarks[b], landmarks[c], landmarks[EXERCISES["1"].swing_joint_right],
            1280, 720, now=1.0, landmarks=landmarks,
        )

        self.assertEqual(tracker.last_processing_path, "kinematics")
        self.assertEqual(tracker.technique_state["processing_path"], "kinematics")
        self.assertIsNotNone(tracker.last_kinematics)

    def test_narrow_input_update_uses_fallback_without_crashing(self):
        tracker = RepTracker("right", EXERCISES["1"], CFG)
        shoulder = make_landmark(0.50, 0.30)
        elbow = make_landmark(0.50, 0.50)
        wrist = make_landmark(0.58, 0.62)

        angle, swinging, rep_done, score = tracker.update(
            shoulder, elbow, wrist, shoulder, 1280, 720, now=1.0
        )

        self.assertIsInstance(angle, float)
        self.assertFalse(swinging)
        self.assertFalse(rep_done)
        self.assertIsNone(score)
        self.assertEqual(tracker.last_processing_path, "fallback")
        self.assertEqual(tracker.technique_state["processing_path"], "fallback")
        self.assertIsNone(tracker.last_kinematics)


if __name__ == "__main__":
    unittest.main()
