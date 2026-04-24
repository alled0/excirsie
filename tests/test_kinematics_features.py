import unittest

from taharrak.kinematics.features import build_kinematics_frame
from tests.helpers_pose import named_landmark_dict


class TestKinematicsFeatures(unittest.TestCase):
    def test_squat_features_are_plausible(self):
        landmarks = named_landmark_dict({
            "left_shoulder": (0.48, 0.30),
            "right_shoulder": (0.52, 0.31),
            "left_hip": (0.49, 0.52),
            "right_hip": (0.53, 0.53),
            "left_knee": (0.54, 0.70),
            "right_knee": (0.56, 0.71),
            "left_ankle": (0.61, 0.88),
            "right_ankle": (0.63, 0.89),
        })
        frame = build_kinematics_frame(landmarks, side="right")
        self.assertIsNotNone(frame.get("right_knee_angle"))
        self.assertGreater(frame.get("right_knee_angle"), 110.0)
        self.assertLess(frame.get("right_knee_angle"), 170.0)
        self.assertIsNotNone(frame.get("right_tibia_angle"))
        self.assertIsNotNone(frame.get("trunk_angle"))

    def test_curl_features_are_plausible(self):
        landmarks = named_landmark_dict({
            "left_shoulder": (0.38, 0.31),
            "right_shoulder": (0.58, 0.31),
            "right_hip": (0.59, 0.63),
            "right_elbow": (0.60, 0.53),
            "right_wrist": (0.50, 0.42),
        })
        frame = build_kinematics_frame(landmarks, side="right")
        self.assertIsNotNone(frame.get("active_elbow_angle"))
        self.assertLess(frame.get("active_elbow_angle"), 130.0)
        self.assertIsNotNone(frame.get("active_upper_arm_torso_angle"))

    def test_lateral_raise_abduction_proxy_is_plausible(self):
        landmarks = named_landmark_dict({
            "left_shoulder": (0.40, 0.31),
            "right_shoulder": (0.60, 0.31),
            "left_hip": (0.42, 0.64),
            "right_hip": (0.58, 0.64),
            "right_elbow": (0.79, 0.34),
            "right_wrist": (0.90, 0.34),
        })
        frame = build_kinematics_frame(landmarks, side="right")
        self.assertIsNotNone(frame.get("shoulder_abduction_angle_right"))
        self.assertGreater(frame.get("shoulder_abduction_angle_right"), 70.0)

    def test_low_visibility_produces_low_quality(self):
        landmarks = named_landmark_dict({
            "right_shoulder": (0.60, 0.31, 0.0, 0.2, 0.2),
            "right_elbow": (0.70, 0.45, 0.0, 0.2, 0.2),
            "right_wrist": (0.78, 0.60, 0.0, 0.2, 0.2),
        }, default_visibility=0.2, default_presence=0.2)
        frame = build_kinematics_frame(landmarks, side="right")
        self.assertFalse(frame.landmark_quality["right_arm"].usable)
        self.assertLess(frame.landmark_quality["right_arm"].score, 0.38)


if __name__ == "__main__":
    unittest.main()
