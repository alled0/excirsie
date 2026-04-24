import unittest

from taharrak.config import merge_config
from taharrak.exercises import EXERCISES
from taharrak.faults import FaultEngine, RepContext
from taharrak.kinematics.features import build_kinematics_frame
from tests.helpers_pose import named_landmark_dict


CFG = merge_config({})


def _context(angle: float = 118.0) -> RepContext:
    return RepContext(
        side="center",
        stage="start",
        rep_elapsed=0.7,
        in_rep=True,
        angle=angle,
        swinging=False,
    )


class TestViewReliability(unittest.TestCase):
    def setUp(self):
        self.engine = FaultEngine(CFG)

    def test_front_view_squat_allows_knee_collapse_and_suppresses_forward_lean(self):
        frame = build_kinematics_frame({
            "left_shoulder": {"x": 0.40, "y": 0.28},
            "right_shoulder": {"x": 0.60, "y": 0.28},
            "left_hip": {"x": 0.44, "y": 0.52},
            "right_hip": {"x": 0.56, "y": 0.52},
            "left_knee": {"x": 0.49, "y": 0.72},
            "right_knee": {"x": 0.51, "y": 0.72},
            "left_ankle": {"x": 0.40, "y": 0.90},
            "right_ankle": {"x": 0.60, "y": 0.90},
        }, side="both")
        evaluations = {item.fault: item for item in self.engine.evaluate(EXERCISES["5"], frame, _context())}

        self.assertTrue(evaluations["knee_collapse"].active)
        self.assertTrue(evaluations["excessive_forward_lean"].suppressed)
        self.assertEqual(evaluations["excessive_forward_lean"].suppress_reason, "view_unreliable")

    def test_side_view_squat_allows_forward_lean_and_suppresses_knee_collapse(self):
        frame = build_kinematics_frame({
            "left_shoulder": {"x": 0.48, "y": 0.30},
            "right_shoulder": {"x": 0.52, "y": 0.31},
            "left_hip": {"x": 0.49, "y": 0.56},
            "right_hip": {"x": 0.53, "y": 0.57},
            "left_knee": {"x": 0.56, "y": 0.72},
            "right_knee": {"x": 0.58, "y": 0.73},
            "left_ankle": {"x": 0.64, "y": 0.89},
            "right_ankle": {"x": 0.66, "y": 0.90},
        }, side="both")
        evaluations = {item.fault: item for item in self.engine.evaluate(EXERCISES["5"], frame, _context())}

        self.assertTrue(evaluations["excessive_forward_lean"].active)
        self.assertTrue(evaluations["knee_collapse"].suppressed)
        self.assertEqual(evaluations["knee_collapse"].suppress_reason, "view_unreliable")

    def test_low_confidence_suppresses_faults(self):
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
        evaluations = {item.fault: item for item in self.engine.evaluate(EXERCISES["5"], frame, _context())}

        self.assertTrue(evaluations["knee_collapse"].suppressed)
        self.assertTrue(evaluations["excessive_forward_lean"].suppressed)

    def test_unknown_view_is_conservative(self):
        frame = build_kinematics_frame({
            "left_shoulder": {"x": 0.48, "y": 0.30},
            "right_shoulder": {"x": 0.52, "y": 0.31},
        }, side="both")
        evaluations = {item.fault: item for item in self.engine.evaluate(EXERCISES["5"], frame, _context())}

        self.assertTrue(evaluations["knee_collapse"].suppressed)
        self.assertTrue(evaluations["excessive_forward_lean"].suppressed)


if __name__ == "__main__":
    unittest.main()
