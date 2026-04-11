"""
Unit tests for the RepTracker finite state machine.

Covers:
  - Normal rep cycle (stage: None → start → end)
  - Hard min-duration block (too-fast rep must not be counted)
  - No double-count from jitter near thresholds
  - In-progress rep is aborted after prolonged LOST signal
  - Recovery gate suppresses transitions immediately after loss

Run:  python -m pytest tests/ -v
      python -m unittest discover tests/
"""
import math
import time
import unittest

from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.tracker import RepTracker


# ── Mock helpers ──────────────────────────────────────────────────────────────

class _FakeLM:
    """Minimal landmark proxy (x, y, z, visibility)."""
    def __init__(self, x: float, y: float, z: float = 0.0, visibility: float = 1.0):
        self.x, self.y, self.z, self.visibility = x, y, z, visibility


def _angle_to_lms(angle_deg: float):
    """
    Return (p_lm, v_lm, d_lm, swing_lm) such that compute_angle(p, v, d)
    with w=1, h=1 equals angle_deg.

    Geometry: vertex at origin, proximal at (1,0),
    distal at (cos θ, sin θ).
    """
    theta = math.radians(angle_deg)
    p = _FakeLM(1.0, 0.0)
    v = _FakeLM(0.0, 0.0)
    d = _FakeLM(math.cos(theta), math.sin(theta))
    s = _FakeLM(0.5, 0.5)        # stable swing landmark
    return p, v, d, s


def _make_tracker(cfg_overrides: dict | None = None):
    """Build a RepTracker for BICEP_CURL with optional config overrides."""
    cfg = {
        "vis_good": 0.68,
        "vis_weak": 0.38,
        "swing_window": 15,
        "swing_threshold": 0.025,
        "confidence_smoother_window": 1,   # no smoother lag in tests
        "fatigue_score_gap": 20,
        "camera_fps": 30,
        "one_euro_min_cutoff": 1.5,
        "one_euro_beta": 0.007,
        "one_euro_d_cutoff": 1.0,
        "fsm_recovery_frames": 3,
        "fsm_max_lost_frames": 5,
    }
    if cfg_overrides:
        cfg.update(cfg_overrides)
    return RepTracker("right", BICEP_CURL, cfg)


# ── Multi-frame helpers ────────────────────────────────────────────────────────
# The One Euro filter needs N frames to converge past a threshold after a large
# step.  These helpers simulate holding a position for enough frames, mirroring
# real use where the user holds the curl/extension for several video frames.
#
# IMPORTANT: real frames arrive ~33 ms apart.  Without injecting a proper dt,
# test calls happen in microseconds, dt ≈ 0 → alpha ≈ 0 → filter never moves.
# Each helper sets tr._last_upd_t = now - 1/fps before every update() call so
# update() computes dt = 1/fps instead of near-zero.

_SIM_FPS  = 30.0
_SIM_DT   = 1.0 / _SIM_FPS


def _hold_position(tr, angle_deg: float, n: int = 20, w: int = 1, h: int = 1):
    """Feed n simulated 30fps frames at angle_deg.
    Returns last (angle, swinging, done, score)."""
    p, v, d, s = _angle_to_lms(angle_deg)
    result = (angle_deg, False, False, None)
    for _ in range(n):
        tr._last_upd_t = time.time() - _SIM_DT
        result = tr.update(p, v, d, s, w, h)
    return result


def _hold_until_done(tr, angle_deg: float, max_frames: int = 40,
                     backdate_start: float = 2.0,
                     w: int = 1, h: int = 1):
    """
    Feed up to max_frames simulated 30fps frames at angle_deg.
    Backdates _rep_start so duration always passes the min_rep_time gate.
    Returns (done, score).
    """
    p, v, d, s = _angle_to_lms(angle_deg)
    tr._rep_start = time.time() - backdate_start
    for _ in range(max_frames):
        tr._last_upd_t = time.time() - _SIM_DT
        _, _, done, score = tr.update(p, v, d, s, w, h)
        if done:
            return True, score
    return False, None


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRepFSMNormalCycle(unittest.TestCase):
    """Happy-path: one complete slow rep."""

    def test_stage_starts_none(self):
        tr = _make_tracker()
        self.assertIsNone(tr.stage)
        self.assertEqual(tr.rep_count, 0)

    def test_extended_arm_enters_start(self):
        tr = _make_tracker()
        p, v, d, s = _angle_to_lms(165.0)   # > angle_down=160
        for _ in range(5):
            tr.update(p, v, d, s, 1, 1)
        self.assertEqual(tr.stage, "start")

    def test_full_rep_counted_when_slow(self):
        """
        Hold extended (165°) until stage='start', then hold curled (35°).
        The One Euro filter converges below angle_up=40° after several frames.
        Rep should be counted and score returned.
        """
        tr = _make_tracker()
        _hold_position(tr, 165.0)            # enter start state
        self.assertEqual(tr.stage, "start")
        done, score = _hold_until_done(tr, 35.0)
        self.assertTrue(done, "Rep should be counted")
        self.assertIsNotNone(score)
        self.assertEqual(tr.rep_count, 1)
        self.assertEqual(tr.stage, "end")

    def test_rep_count_increments(self):
        tr = _make_tracker()

        def _do_rep():
            _hold_position(tr, 165.0)
            done, _ = _hold_until_done(tr, 35.0)
            return done

        self.assertTrue(_do_rep())
        self.assertEqual(tr.rep_count, 1)
        self.assertTrue(_do_rep())
        self.assertEqual(tr.rep_count, 2)


class TestMinDurationBlock(unittest.TestCase):
    """Rep must NOT be counted if it completed faster than min_rep_time."""

    def test_fast_rep_not_counted(self):
        tr = _make_tracker()
        W = H = 1

        # Enter start position
        p, v, d, s = _angle_to_lms(165.0)
        for _ in range(5):
            tr.update(p, v, d, s, W, H)
        self.assertEqual(tr.stage, "start")

        # _rep_start is now set; do NOT patch time — rep_start is effectively
        # 'just now', so duration will be < min_rep_time (1.2 s)
        p, v, d, s = _angle_to_lms(35.0)
        _, _, done, score = tr.update(p, v, d, s, W, H)
        self.assertFalse(done, "Rep must not be counted when too fast")
        self.assertIsNone(score)
        self.assertEqual(tr.rep_count, 0)

    def test_slow_rep_counted(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0)
        done, _ = _hold_until_done(tr, 35.0, backdate_start=1.5)
        self.assertTrue(done)
        self.assertEqual(tr.rep_count, 1)


class TestJitterResistance(unittest.TestCase):
    """Jitter spike should not double-count."""

    def test_jitter_at_end_position_no_double_count(self):
        """
        After a rep is counted (stage='end'), oscillating around the end
        angle should NOT produce additional counts.
        """
        tr = _make_tracker()

        # Complete one full rep
        _hold_position(tr, 165.0)
        done, _ = _hold_until_done(tr, 35.0)
        self.assertTrue(done, "First rep must complete for this test to be valid")
        self.assertEqual(tr.rep_count, 1)
        self.assertEqual(tr.stage, "end")

        # Jitter around end angle — stage is "end" so no FSM re-trigger
        for i in range(10):
            p, v, d, s = _angle_to_lms(37.0 if i % 2 == 0 else 33.0)
            _, _, again, _ = tr.update(p, v, d, s, 1, 1)
            self.assertFalse(again)
        self.assertEqual(tr.rep_count, 1)

    def test_sub_threshold_jitter_at_start_no_count(self):
        """
        Angle jitter that briefly crosses the end threshold while stage is
        still being established (< min_rep_time) must not count.
        """
        tr = _make_tracker()
        W = H = 1

        # Just entered start position (rep_start very recent = fast)
        p, v, d, s = _angle_to_lms(165.0)
        for _ in range(5):
            tr.update(p, v, d, s, W, H)

        # Immediately spike to end position (< min_rep_time has elapsed)
        p, v, d, s = _angle_to_lms(35.0)
        _, _, done, _ = tr.update(p, v, d, s, W, H)
        self.assertFalse(done)
        self.assertEqual(tr.rep_count, 0)


class TestAbortOnLoss(unittest.TestCase):
    """In-progress rep must be discarded after prolonged LOST signal."""

    def test_abort_resets_stage_to_none(self):
        tr = _make_tracker({"fsm_max_lost_frames": 5})
        W = H = 1

        # Enter start position (stage → "start", _in_rep = True)
        p, v, d, s = _angle_to_lms(165.0)
        for _ in range(5):
            tr.update(p, v, d, s, W, H)
        self.assertTrue(tr._in_rep)

        # Signal LOST for max_lost_frames frames
        for _ in range(5):
            tr.update_quality("LOST")

        self.assertFalse(tr._in_rep, "_in_rep should be False after abort")
        self.assertIsNone(tr.stage,  "stage should reset to None after abort")

    def test_short_loss_does_not_abort(self):
        """A brief loss (< max_lost_frames) must NOT abort the rep."""
        tr = _make_tracker({"fsm_max_lost_frames": 10})
        W = H = 1

        p, v, d, s = _angle_to_lms(165.0)
        for _ in range(5):
            tr.update(p, v, d, s, W, H)
        self.assertTrue(tr._in_rep)

        # Short loss burst — below threshold
        for _ in range(4):
            tr.update_quality("LOST")

        # Rep should still be in-progress
        self.assertTrue(tr._in_rep)


class TestRecoveryGating(unittest.TestCase):
    """FSM transitions must be suppressed during recovery window."""

    def test_no_rep_counted_during_recovery(self):
        tr = _make_tracker({"fsm_recovery_frames": 3})
        W = H = 1

        # Enter start position normally
        p, v, d, s = _angle_to_lms(165.0)
        for _ in range(5):
            tr.update(p, v, d, s, W, H)
        self.assertEqual(tr.stage, "start")

        # Simulate brief LOST then recovery
        tr.update_quality("LOST")
        tr.update_quality("LOST")
        tr.update_quality("GOOD")   # triggers recovery mode
        self.assertTrue(tr._recovering)

        # Wind clock so duration looks valid
        tr._rep_start = time.time() - 2.0

        # Attempt to complete rep during recovery window
        p, v, d, s = _angle_to_lms(35.0)
        for _ in range(2):         # still within recovery_frames=3
            _, _, done, _ = tr.update(p, v, d, s, W, H)
            self.assertFalse(done, "No rep during recovery window")
        self.assertEqual(tr.rep_count, 0)

    def test_rep_allowed_after_recovery_window(self):
        tr = _make_tracker({"fsm_recovery_frames": 3,
                             "confidence_smoother_window": 1})

        # Enter start, then simulate loss + recovery
        _hold_position(tr, 165.0)
        self.assertEqual(tr.stage, "start")

        tr.update_quality("LOST")
        tr.update_quality("GOOD")  # starts recovery countdown
        # Complete 3 × GOOD to exit recovery
        for _ in range(3):
            tr.update_quality("GOOD")
        self.assertFalse(tr._recovering)

        # Now do a real end-position hold; rep must be counted
        done, _ = _hold_until_done(tr, 35.0)
        self.assertTrue(done, "Rep should be counted after recovery window")


class TestResetSet(unittest.TestCase):
    """reset_set() must clear all per-set state including recovery flags."""

    def test_reset_clears_rep_count_and_recovery(self):
        tr = _make_tracker()
        tr._recovering       = True
        tr._consecutive_lost = 5
        tr.rep_count         = 3
        tr.reset_set()
        self.assertEqual(tr.rep_count, 0)
        self.assertFalse(tr._recovering)
        self.assertEqual(tr._consecutive_lost, 0)
        self.assertEqual(tr._consecutive_good, 0)
        self.assertIsNone(tr.stage)


if __name__ == "__main__":
    unittest.main()
