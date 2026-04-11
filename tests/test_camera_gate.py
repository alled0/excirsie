"""
Unit tests for camera-position analysis and exercise framing gate.

Covers:
  - analyze_camera_position: each individual issue key
  - check_exercise_framing: exercise key-joint visibility check

Run:  python -m pytest tests/ -v
      python -m unittest discover tests/
"""
import unittest

from taharrak.analysis import analyze_camera_position, check_exercise_framing
from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.exercises.squat import SQUAT


# ── Mock landmark factory ─────────────────────────────────────────────────────

class _LM:
    """Minimal landmark with (x, y, z, visibility)."""
    def __init__(self, x=0.5, y=0.5, z=0.0, visibility=0.95):
        self.x, self.y, self.z, self.visibility = x, y, z, visibility


def _default_lm_list():
    """
    33 landmarks in a 'good' default position.
    Key landmarks set explicitly:
      11 = left shoulder  (x=0.40, y=0.30)
      12 = right shoulder (x=0.60, y=0.30)
    Shoulder span = 0.20, mid_x = 0.50, mid_y = 0.30 → all checks pass.
    """
    lms = [_LM() for _ in range(33)]
    lms[11] = _LM(x=0.40, y=0.30, visibility=0.95)   # left  shoulder
    lms[12] = _LM(x=0.60, y=0.30, visibility=0.95)   # right shoulder
    return lms


# ── analyze_camera_position tests ────────────────────────────────────────────

class TestAnalyzeCameraPosition(unittest.TestCase):

    def test_good_position_no_issues(self):
        lms = _default_lm_list()
        self.assertEqual(analyze_camera_position(lms), [])

    # ── Distance checks ──────────────────────────────────────────────────────

    def test_too_close_detected(self):
        """Shoulder span > 0.48 → cam_too_close."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.20, y=0.35, visibility=0.95)
        lms[12] = _LM(x=0.70, y=0.35, visibility=0.95)  # span = 0.50
        self.assertIn("cam_too_close", analyze_camera_position(lms))

    def test_too_far_detected(self):
        """Shoulder span < 0.15 → cam_too_far."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.47, y=0.30, visibility=0.95)
        lms[12] = _LM(x=0.53, y=0.30, visibility=0.95)  # span = 0.06
        self.assertIn("cam_too_far", analyze_camera_position(lms))

    # ── Centering checks ─────────────────────────────────────────────────────

    def test_off_center_left_detected(self):
        """Shoulder midpoint x > 0.65 → cam_move_left."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.68, y=0.30, visibility=0.95)
        lms[12] = _LM(x=0.80, y=0.30, visibility=0.95)  # mid_x = 0.74
        self.assertIn("cam_move_left", analyze_camera_position(lms))

    def test_off_center_right_detected(self):
        """Shoulder midpoint x < 0.35 → cam_move_right."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.15, y=0.30, visibility=0.95)
        lms[12] = _LM(x=0.25, y=0.30, visibility=0.95)  # mid_x = 0.20
        self.assertIn("cam_move_right", analyze_camera_position(lms))

    # ── Height checks ────────────────────────────────────────────────────────

    def test_camera_too_low_detected(self):
        """Shoulder midpoint y > 0.70 → cam_too_low."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.40, y=0.75, visibility=0.95)
        lms[12] = _LM(x=0.60, y=0.75, visibility=0.95)  # mid_y = 0.75
        self.assertIn("cam_too_low", analyze_camera_position(lms))

    def test_camera_too_high_detected(self):
        """Shoulder midpoint y < 0.15 → cam_too_high."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.40, y=0.10, visibility=0.95)
        lms[12] = _LM(x=0.60, y=0.10, visibility=0.95)  # mid_y = 0.10
        self.assertIn("cam_too_high", analyze_camera_position(lms))

    # ── Rotation check ───────────────────────────────────────────────────────

    def test_body_rotation_right_detected(self):
        """Left shoulder higher (lower y) than right → cam_turn_right."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.40, y=0.20, visibility=0.95)   # left shoulder higher
        lms[12] = _LM(x=0.60, y=0.30, visibility=0.95)   # right shoulder lower
        # |0.20 - 0.30| = 0.10 > 0.06, and l_sh.y < r_sh.y → cam_turn_right
        issues = analyze_camera_position(lms)
        self.assertIn("cam_turn_right", issues)

    def test_body_rotation_left_detected(self):
        lms = _default_lm_list()
        lms[11] = _LM(x=0.40, y=0.30, visibility=0.95)
        lms[12] = _LM(x=0.60, y=0.20, visibility=0.95)   # right shoulder higher
        issues = analyze_camera_position(lms)
        self.assertIn("cam_turn_left", issues)

    def test_small_rotation_ok(self):
        """Asymmetry ≤ 0.06 must not trigger rotation warning."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.40, y=0.30, visibility=0.95)
        lms[12] = _LM(x=0.60, y=0.33, visibility=0.95)   # diff = 0.03
        issues = analyze_camera_position(lms)
        self.assertNotIn("cam_turn_right", issues)
        self.assertNotIn("cam_turn_left",  issues)

    # ── Visibility check ─────────────────────────────────────────────────────

    def test_poor_visibility_short_circuits(self):
        """Low avg visibility → cam_poor_vis returned and nothing else."""
        lms = [_LM(visibility=0.1) for _ in range(33)]
        issues = analyze_camera_position(lms)
        self.assertIn("cam_poor_vis", issues)
        # Must short-circuit — only cam_poor_vis should appear
        self.assertEqual(len(issues), 1)

    def test_multiple_issues_reported(self):
        """Off-center AND too far can be reported together."""
        lms = _default_lm_list()
        lms[11] = _LM(x=0.14, y=0.30, visibility=0.95)
        lms[12] = _LM(x=0.16, y=0.30, visibility=0.95)   # too far + off-center
        issues = analyze_camera_position(lms)
        self.assertIn("cam_too_far",    issues)
        self.assertIn("cam_move_right", issues)


# ── check_exercise_framing tests ────────────────────────────────────────────

class TestCheckExerciseFraming(unittest.TestCase):
    CFG = {"vis_good": 0.68}

    def _lms_with_vis(self, overrides: dict):
        """Build 33-landmark list; overrides maps index→visibility."""
        lms = [_LM(visibility=0.95) for _ in range(33)]
        for idx, vis in overrides.items():
            lms[idx] = _LM(visibility=vis)
        return lms

    def test_no_issues_when_all_visible(self):
        lms = self._lms_with_vis({})   # all at 0.95 > 0.68
        self.assertEqual(check_exercise_framing(lms, BICEP_CURL, self.CFG), [])

    def test_hidden_left_key_joint_flagged(self):
        """Left elbow hidden → joint_hidden reported."""
        # BICEP_CURL key_joints_left = (LE=13, LW=15)
        lms = self._lms_with_vis({13: 0.30})   # LE below threshold
        issues = check_exercise_framing(lms, BICEP_CURL, self.CFG)
        self.assertIn("joint_hidden", issues)

    def test_hidden_right_key_joint_flagged(self):
        """Right wrist hidden → joint_hidden reported."""
        # BICEP_CURL key_joints_right = (RE=14, RW=16)
        lms = self._lms_with_vis({16: 0.20})   # RW below threshold
        issues = check_exercise_framing(lms, BICEP_CURL, self.CFG)
        self.assertIn("joint_hidden", issues)

    def test_non_key_joint_hidden_not_flagged(self):
        """Hiding a non-key joint (e.g. nose=0) must not trigger this check."""
        lms = self._lms_with_vis({0: 0.10})
        self.assertEqual(check_exercise_framing(lms, BICEP_CURL, self.CFG), [])

    def test_squat_key_joints(self):
        """SQUAT key joints are knee+ankle; hiding a knee should flag."""
        # SQUAT key_joints_right = (RK=26, RA=28)
        lms = self._lms_with_vis({26: 0.10})   # right knee hidden
        issues = check_exercise_framing(lms, SQUAT, self.CFG)
        self.assertIn("joint_hidden", issues)

    def test_no_duplicate_joint_hidden(self):
        """Even if both left and right are hidden, 'joint_hidden' appears once."""
        lms = self._lms_with_vis({13: 0.10, 14: 0.10})   # both elbows hidden
        issues = check_exercise_framing(lms, BICEP_CURL, self.CFG)
        self.assertEqual(issues.count("joint_hidden"), 1)

    def test_exercise_without_key_joints_safe(self):
        """
        Exercise with empty key_joints (defaults) should produce no issues
        regardless of visibility.
        """
        from taharrak.exercises.base import Exercise, LS, LE, LW, RS, RE, RW
        ex_no_keys = Exercise(
            name="Test", name_ar="", key="T",
            joints_left=(LS, LE, LW), joints_right=(RS, RE, RW),
            angle_down=160.0, angle_up=40.0,
            invert=False, bilateral=True,
            swing_joint_left=LS, swing_joint_right=RS,
            swing_threshold=0.025, rom_tolerance=10.0,
            ideal_rep_time=2.5, min_rep_time=1.2,
            stage_labels=("DOWN", "UP"), arc_joint_idx=1,
            # key_joints_left and key_joints_right default to ()
        )
        lms = self._lms_with_vis({lm: 0.0 for lm in range(33)})  # all invisible
        self.assertEqual(check_exercise_framing(lms, ex_no_keys, self.CFG), [])


if __name__ == "__main__":
    unittest.main()
