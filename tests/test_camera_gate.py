"""
Unit tests for camera-position analysis and exercise framing gate.

Covers:
  - analyze_camera_position: each individual issue key
  - check_exercise_framing: exercise key-joint visibility check

Run:  python -m pytest tests/ -v
      python -m unittest discover tests/
"""
import unittest

from taharrak.analysis import analyze_camera_position, build_msgs, check_exercise_framing
from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.exercises.squat import SQUAT
from taharrak.tracker import LiveTrustState


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


# ── build_msgs semantic output tests ────────────────────────────────────────


class _StubTracker:
    """Minimal tracker stub sufficient for build_msgs."""
    def __init__(self, stage=None, rep_elapsed=0.0):
        self.stage       = stage
        self.rep_elapsed = rep_elapsed
        self.side        = "right"


_VALID_SEVERITIES = {"error", "warning", "ok"}
_CFG_MSGS = {"min_rep_time": 1.2}


class TestBuildMsgsSemantics(unittest.TestCase):
    """build_msgs must return (str, severity_str) — no BGR colour tuples."""

    def _call(self, trackers, angles, swings):
        return build_msgs(trackers, angles, swings, BICEP_CURL, _CFG_MSGS, "en")

    # -- contract: types -------------------------------------------------------

    def test_returns_text_and_severity_string(self):
        """Every message must be (str, severity_str) — not (str, BGR_tuple)."""
        tr   = _StubTracker(stage="start", rep_elapsed=0.4)
        msgs = self._call([tr], [165.0], [False])
        for txt, sev in msgs:
            self.assertIsInstance(txt, str)
            self.assertIsInstance(sev, str)

    def test_severity_values_are_valid(self):
        """All severity strings must be one of the defined semantic values."""
        tr   = _StubTracker(stage="start", rep_elapsed=0.4)
        msgs = self._call([tr], [165.0], [True])
        for _, sev in msgs:
            self.assertIn(sev, _VALID_SEVERITIES,
                          f"Unexpected severity: {sev!r}")

    def test_no_bgr_tuples_in_severity(self):
        """Severities must never be tuples (old colour values)."""
        tr   = _StubTracker(stage="start", rep_elapsed=0.3)
        msgs = self._call([tr], [165.0], [True])
        for _, sev in msgs:
            self.assertNotIsInstance(sev, tuple,
                "Severity must be a string, not a BGR colour tuple")

    # -- contract: severity mapping -------------------------------------------

    def test_swinging_produces_error(self):
        tr   = _StubTracker(stage="start")
        msgs = self._call([tr], [165.0], [True])
        severities = [sev for _, sev in msgs]
        self.assertIn("error", severities)

    def test_too_fast_rep_produces_error(self):
        """rep_elapsed in (0, min_rep_time) → error."""
        tr   = _StubTracker(stage="start", rep_elapsed=0.5)
        msgs = self._call([tr], [165.0], [False])
        severities = [sev for _, sev in msgs]
        self.assertIn("error", severities)

    def test_rom_guidance_produces_warning(self):
        """Angle still near start threshold while in start stage → warning."""
        # angle > angle_down - 12 = 148 triggers extend_fully
        tr   = _StubTracker(stage="start")
        msgs = self._call([tr], [BICEP_CURL.angle_down - 6], [False])
        severities = [sev for _, sev in msgs]
        self.assertIn("warning", severities)

    def test_positive_hint_produces_ok(self):
        """No issues at stage='end' → ok hint (lower_slowly cue)."""
        tr   = _StubTracker(stage="end")
        msgs = self._call([tr], [35.0], [False])
        self.assertTrue(msgs, "Expected at least one hint message")
        severities = [sev for _, sev in msgs]
        self.assertIn("ok", severities)

    def test_no_messages_when_no_stage(self):
        """stage=None and no swing → empty list (nothing to hint at)."""
        tr   = _StubTracker(stage=None)
        msgs = self._call([tr], [90.0], [False])
        self.assertEqual(msgs, [])


class _FaultTracker:
    def __init__(self, faults=(), stage=None):
        self.stage = stage
        self.rep_elapsed = 0.0
        self.side = "center"
        self.technique_state = {
            "faults": tuple(faults),
            "signals": {"end_range": (90.0, 120.0)},
            "view": "unknown",
            "fault_evaluations": {
                "excessive_forward_lean": {
                    "active": False,
                    "suppressed": True,
                    "suppress_reason": "view_unreliable",
                }
            },
        }


class TestSuppressionAndCameraFeedback(unittest.TestCase):
    def test_suppressed_fault_is_not_surface_as_biomechanical_correction(self):
        tracker = _FaultTracker(faults=(), stage=None)

        msgs = build_msgs(
            [tracker], [None], [False], SQUAT, _CFG_MSGS, "en", qualities=["GOOD"]
        )

        self.assertEqual(msgs, [])

    def test_camera_setup_message_prefers_setup_feedback_in_english_and_arabic(self):
        trust = LiveTrustState(
            render_allowed=True,
            counting_allowed=False,
            coaching_allowed=False,
            bilateral_compare_allowed=False,
            counting_sides=(False,),
            coaching_sides=(False,),
            good_frames=(0,),
            visible_frames=(0,),
        )
        tracker = _FaultTracker(faults=("upper_arm_drift",), stage="start")

        msgs_en = build_msgs(
            [tracker], [165.0], [False], BICEP_CURL, _CFG_MSGS, "en",
            qualities=["WEAK"], trust=trust, cam_feedback=["cam_turn_left"],
        )
        msgs_ar = build_msgs(
            [tracker], [165.0], [False], BICEP_CURL, _CFG_MSGS, "ar",
            qualities=["WEAK"], trust=trust, cam_feedback=["cam_turn_left"],
        )

        self.assertTrue(msgs_en)
        self.assertTrue(msgs_ar)
        self.assertIn("turn", msgs_en[0][0].lower())
        self.assertNotEqual(msgs_en[0][0], msgs_ar[0][0])


class _NoFaultTracker:
    """Tracker that has no active faults — exercises the primary-signal angle fallback."""
    def __init__(self, stage, rep_elapsed, end_range):
        self.stage = stage
        self.rep_elapsed = rep_elapsed
        self.side = "right"
        self.technique_state = {
            "faults": (),
            "signals": {"end_range": end_range},
            "view": "unknown",
            "fault_evaluations": {},
        }


class TestPrimarySignalAngleFallback(unittest.TestCase):
    """
    _profile_feedback() has a secondary path that fires when the fault engine
    produced no faults but the primary-signal angle is out of range.  These
    tests verify that path surfaces coaching even without a fault-engine hit.
    """

    _CFG = {"min_rep_time": 1.2, "exercise_thresholds": {}}

    def _bicep_tracker(self, angle_above_end):
        end_range = BICEP_CURL.technique_profile.end_thresholds["elbow_angle_deg"]
        return _NoFaultTracker(stage="start", rep_elapsed=0.5,
                               end_range=end_range), angle_above_end

    def test_bicep_curl_high_angle_surfaces_curl_higher(self):
        """Arm not curled enough → 'curl_higher' cue via angle fallback."""
        end_range = BICEP_CURL.technique_profile.end_thresholds["elbow_angle_deg"]
        # rep_elapsed must exceed min_rep_time (1.2 s) so slow_down doesn't win
        tracker = _NoFaultTracker(stage="start", rep_elapsed=2.0, end_range=end_range)
        angle = end_range[1] + 10.0   # clearly above the end threshold

        msgs = build_msgs([tracker], [angle], [False], BICEP_CURL, self._CFG, "en",
                          qualities=["GOOD"])

        self.assertTrue(msgs, "Expected a coaching cue but got none")
        text = msgs[0][0]
        self.assertIn("higher", text.lower())

    def test_no_cue_when_angle_is_within_range(self):
        """Angle inside end_range → no ROM coaching from the fallback."""
        end_range = BICEP_CURL.technique_profile.end_thresholds["elbow_angle_deg"]
        mid = (end_range[0] + end_range[1]) / 2
        tracker = _NoFaultTracker(stage="start", rep_elapsed=0.5, end_range=end_range)

        msgs = build_msgs([tracker], [mid], [False], BICEP_CURL, self._CFG, "en",
                          qualities=["GOOD"])

        # No ROM cue — may get a positive hint but not a warning
        for _, sev in msgs:
            self.assertNotEqual(sev, "warning", "Unexpected warning when angle is in range")

    def test_no_cue_when_quality_is_weak_for_primary_signal(self):
        """WEAK quality blocks the primary-signal fallback (GOOD required for bicep curl)."""
        end_range = BICEP_CURL.technique_profile.end_thresholds["elbow_angle_deg"]
        tracker = _NoFaultTracker(stage="start", rep_elapsed=0.5, end_range=end_range)
        angle = end_range[1] + 10.0

        msgs = build_msgs([tracker], [angle], [False], BICEP_CURL, self._CFG, "en",
                          qualities=["WEAK"])

        warnings = [sev for _, sev in msgs if sev == "warning"]
        self.assertEqual(warnings, [], "Fallback should be blocked under WEAK quality")

    def test_elapsed_guard_prevents_immediate_cue(self):
        """rep_elapsed ≤ 0.35 → no fallback cue (guards against start-of-rep noise)."""
        end_range = BICEP_CURL.technique_profile.end_thresholds["elbow_angle_deg"]
        tracker = _NoFaultTracker(stage="start", rep_elapsed=0.1, end_range=end_range)
        angle = end_range[1] + 10.0

        msgs = build_msgs([tracker], [angle], [False], BICEP_CURL, self._CFG, "en",
                          qualities=["GOOD"])

        warnings = [sev for _, sev in msgs if sev == "warning"]
        self.assertEqual(warnings, [], "Fallback should not fire this early in a rep")


if __name__ == "__main__":
    unittest.main()
