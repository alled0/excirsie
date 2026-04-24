import unittest

from taharrak.kinematics.geometry import angle_between_vectors, joint_angle
from taharrak.kinematics.types import LandmarkPoint


class TestKinematicsGeometry(unittest.TestCase):
    def test_joint_angle_90_deg(self):
        a = LandmarkPoint(1.0, 0.0)
        b = LandmarkPoint(0.0, 0.0)
        c = LandmarkPoint(0.0, 1.0)
        self.assertAlmostEqual(joint_angle(a, b, c), 90.0, places=4)

    def test_joint_angle_180_deg(self):
        a = LandmarkPoint(-1.0, 0.0)
        b = LandmarkPoint(0.0, 0.0)
        c = LandmarkPoint(1.0, 0.0)
        self.assertAlmostEqual(joint_angle(a, b, c), 180.0, places=4)

    def test_joint_angle_acute(self):
        a = LandmarkPoint(1.0, 0.0)
        b = LandmarkPoint(0.0, 0.0)
        c = LandmarkPoint(1.0, 1.0)
        self.assertAlmostEqual(joint_angle(a, b, c), 45.0, places=4)

    def test_missing_points_do_not_crash(self):
        self.assertIsNone(joint_angle(None, LandmarkPoint(0.0, 0.0), LandmarkPoint(1.0, 0.0)))

    def test_cosine_clamp_handles_floating_point_noise(self):
        v1 = (1.0, 0.0, None)
        v2 = (1.0000000001, 0.0, None)
        self.assertAlmostEqual(angle_between_vectors(v1, v2), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
