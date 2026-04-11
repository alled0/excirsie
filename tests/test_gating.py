"""
Unit tests for confidence-aware gating logic inside RepTracker.

Covers:
  - update_quality() transitions: GOOD → LOST → GOOD triggers recovery mode
  - Recovery counter increments and exits correctly
  - backward-compat: smooth_quality() is an alias for update_quality()

Run:  python -m pytest tests/ -v
      python -m unittest discover tests/
"""
import unittest

from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.tracker import RepTracker


def _make_tracker(**overrides):
    cfg = {
        "vis_good": 0.68, "vis_weak": 0.38,
        "swing_window": 15,
        "confidence_smoother_window": 1,   # no lag — raw quality passes through
        "fatigue_score_gap": 20,
        "camera_fps": 30,
        "one_euro_min_cutoff": 1.5, "one_euro_beta": 0.007, "one_euro_d_cutoff": 1.0,
        "fsm_recovery_frames": 3,
        "fsm_max_lost_frames": 5,
    }
    cfg.update(overrides)
    return RepTracker("right", BICEP_CURL, cfg)


class TestQualityTransitions(unittest.TestCase):

    def test_good_signal_increments_consecutive_good(self):
        tr = _make_tracker()
        tr.update_quality("GOOD")
        self.assertEqual(tr._consecutive_good, 1)
        tr.update_quality("GOOD")
        self.assertEqual(tr._consecutive_good, 2)

    def test_lost_signal_resets_consecutive_good(self):
        tr = _make_tracker()
        tr.update_quality("GOOD")
        tr.update_quality("GOOD")
        tr.update_quality("LOST")
        self.assertEqual(tr._consecutive_good, 0)
        self.assertEqual(tr._consecutive_lost, 1)

    def test_lost_increments_consecutive_lost(self):
        tr = _make_tracker()
        for i in range(3):
            tr.update_quality("LOST")
        self.assertEqual(tr._consecutive_lost, 3)

    def test_good_after_lost_triggers_recovery(self):
        tr = _make_tracker()
        tr.update_quality("LOST")
        tr.update_quality("LOST")
        self.assertEqual(tr._consecutive_lost, 2)
        tr.update_quality("GOOD")          # transition back
        self.assertTrue(tr._recovering, "Should enter recovery mode")
        self.assertEqual(tr._consecutive_lost, 0)

    def test_recovery_exits_after_n_good_frames(self):
        tr = _make_tracker(fsm_recovery_frames=3)
        tr.update_quality("LOST")
        tr.update_quality("GOOD")   # triggers recovery
        self.assertTrue(tr._recovering)
        tr.update_quality("GOOD")
        self.assertTrue(tr._recovering)   # still recovering after 2nd
        tr.update_quality("GOOD")
        self.assertFalse(tr._recovering, "Should exit recovery after 3 GOOD frames")

    def test_no_recovery_on_uninterrupted_good(self):
        tr = _make_tracker()
        for _ in range(10):
            tr.update_quality("GOOD")
        self.assertFalse(tr._recovering)

    def test_consecutive_lost_resets_on_recovery(self):
        tr = _make_tracker()
        for _ in range(4):
            tr.update_quality("LOST")
        tr.update_quality("GOOD")
        self.assertEqual(tr._consecutive_lost, 0)

    def test_smooth_quality_is_alias(self):
        """smooth_quality must call the same logic as update_quality."""
        tr1 = _make_tracker()
        tr2 = _make_tracker()
        for q in ["GOOD", "GOOD", "LOST", "GOOD"]:
            r1 = tr1.update_quality(q)
            r2 = tr2.smooth_quality(q)
            self.assertEqual(r1, r2)
        self.assertEqual(tr1._recovering,       tr2._recovering)
        self.assertEqual(tr1._consecutive_good, tr2._consecutive_good)
        self.assertEqual(tr1._consecutive_lost, tr2._consecutive_lost)

    def test_returned_quality_is_smoothed(self):
        """Return value is the majority-voted quality, not the raw input."""
        # confidence_smoother_window=1 → no smoothing, raw == smoothed
        tr = _make_tracker(confidence_smoother_window=1)
        self.assertEqual(tr.update_quality("GOOD"), "GOOD")
        self.assertEqual(tr.update_quality("LOST"), "LOST")


class TestAbortOnExcessiveLoss(unittest.TestCase):
    """In-progress rep aborted when LOST exceeds max_lost_frames."""

    def _enter_rep(self, tr):
        """Force the tracker into an in-progress rep state."""
        from tests.test_fsm import _hold_position
        _hold_position(tr, 165.0)
        self.assertTrue(tr._in_rep)

    def test_abort_after_max_lost_frames(self):
        tr = _make_tracker(fsm_max_lost_frames=5)
        self._enter_rep(tr)
        for _ in range(5):
            tr.update_quality("LOST")
        self.assertFalse(tr._in_rep)
        self.assertIsNone(tr.stage)

    def test_no_abort_before_max_lost_frames(self):
        tr = _make_tracker(fsm_max_lost_frames=10)
        self._enter_rep(tr)
        for _ in range(4):
            tr.update_quality("LOST")
        self.assertTrue(tr._in_rep)


if __name__ == "__main__":
    unittest.main()
