"""
Unit tests for structured rep abort / reject / suppress reason logging.

Covers:
  - lost_visibility  logged by _abort_rep() with correct context fields
  - below_min_duration logged once per crossing (not once per frame)
  - recovery_interrupted logged when recovery enters while rep is in-progress
  - recovery_interrupted NOT logged when rep is not in-progress
  - tracking_reset logged by reset_tracking() when in-rep
  - tracking_reset NOT logged when not in-rep
  - event_log cleared by reset_set()
  - event_log preserved by reset_tracking()
  - every event has the required base fields
  - successful rep produces no events

Run:  python -m unittest discover tests/
"""
import time
import unittest

from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.tracker import RepTracker

from tests.test_fsm import (
    _angle_to_lms,
    _hold_position,
    _hold_until_done,
    _SIM_DT,
)

_REQUIRED_FIELDS = {"timestamp", "side", "set_num", "category"}


# ── Tracker factory ───────────────────────────────────────────────────────────

def _make_tracker(**overrides):
    cfg = {
        "vis_good": 0.68, "vis_weak": 0.38,
        "swing_window": 15,
        "confidence_smoother_window": 1,
        "fatigue_score_gap": 20,
        "camera_fps": 30,
        "one_euro_min_cutoff": 1.5, "one_euro_beta": 0.007,
        "one_euro_d_cutoff": 1.0,
        "fsm_recovery_frames": 3,
        "fsm_max_lost_frames": 5,
    }
    cfg.update(overrides)
    return RepTracker("right", BICEP_CURL, cfg)


# ── lost_visibility ───────────────────────────────────────────────────────────

class TestLostVisibilityEvent(unittest.TestCase):

    def _abort_tracker(self):
        tr = _make_tracker(fsm_max_lost_frames=3)
        _hold_position(tr, 165.0)        # enter start → _in_rep=True
        self.assertTrue(tr._in_rep)
        for _ in range(3):
            tr.update_quality("LOST")    # triggers _abort_rep() on 3rd
        return tr

    def test_event_logged_on_abort(self):
        tr = self._abort_tracker()
        self.assertEqual(len(tr.event_log), 1)

    def test_event_category_is_lost_visibility(self):
        tr = self._abort_tracker()
        self.assertEqual(tr.event_log[0]["category"], "lost_visibility")

    def test_event_has_required_fields(self):
        tr = self._abort_tracker()
        evt = tr.event_log[0]
        self.assertTrue(_REQUIRED_FIELDS.issubset(evt.keys()))

    def test_event_has_consecutive_lost(self):
        tr = self._abort_tracker()
        self.assertIn("consecutive_lost", tr.event_log[0])
        self.assertGreaterEqual(tr.event_log[0]["consecutive_lost"], 3)

    def test_event_has_angle_fields(self):
        tr = self._abort_tracker()
        evt = tr.event_log[0]
        self.assertIn("min_angle", evt)
        self.assertIn("max_angle", evt)

    def test_no_event_when_abort_not_triggered(self):
        """No abort → no lost_visibility event."""
        tr = _make_tracker(fsm_max_lost_frames=10)
        _hold_position(tr, 165.0)
        for _ in range(3):               # below threshold
            tr.update_quality("LOST")
        categories = [e["category"] for e in tr.event_log]
        self.assertNotIn("lost_visibility", categories)


# ── below_min_duration ────────────────────────────────────────────────────────

class TestBelowMinDurationEvent(unittest.TestCase):

    def _setup_fast_rep(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0, n=20)
        self.assertEqual(tr.stage, "start")
        rep_start = tr._rep_start
        p, v, d, s = _angle_to_lms(35.0)
        for _ in range(20):
            tr._last_upd_t = time.time() - _SIM_DT
            tr._rep_start  = rep_start    # keep duration short
            tr.update(p, v, d, s, 1, 1)
        return tr

    def test_event_logged_on_rejection(self):
        tr = self._setup_fast_rep()
        categories = [e["category"] for e in tr.event_log]
        self.assertIn("below_min_duration", categories)

    def test_event_logged_exactly_once_per_crossing(self):
        """Holding at end angle for many frames must not produce multiple events."""
        tr = self._setup_fast_rep()
        below_dur = [e for e in tr.event_log
                     if e["category"] == "below_min_duration"]
        self.assertEqual(len(below_dur), 1,
                         "One crossing → exactly one below_min_duration event")

    def test_event_has_duration_s(self):
        tr = self._setup_fast_rep()
        evt = next(e for e in tr.event_log if e["category"] == "below_min_duration")
        self.assertIn("duration_s", evt)
        self.assertLess(evt["duration_s"], BICEP_CURL.min_rep_time)

    def test_event_has_min_rep_time(self):
        tr = self._setup_fast_rep()
        evt = next(e for e in tr.event_log if e["category"] == "below_min_duration")
        self.assertIn("min_rep_time", evt)
        self.assertAlmostEqual(evt["min_rep_time"], BICEP_CURL.min_rep_time)

    def test_no_event_for_successful_rep(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0)
        _hold_until_done(tr, 35.0, backdate_start=2.0)
        categories = [e["category"] for e in tr.event_log]
        self.assertNotIn("below_min_duration", categories)


# ── recovery_interrupted ──────────────────────────────────────────────────────

class TestRecoveryInterruptedEvent(unittest.TestCase):

    def test_event_logged_when_in_rep(self):
        """Loss then recovery while rep is in-progress → recovery_interrupted."""
        tr = _make_tracker(fsm_max_lost_frames=10)
        _hold_position(tr, 165.0)           # _in_rep=True
        self.assertTrue(tr._in_rep)
        # Brief loss (does not reach max_lost_frames)
        for _ in range(3):
            tr.update_quality("LOST")
        self.assertTrue(tr._in_rep)        # rep still in progress
        tr.update_quality("GOOD")          # enters recovery
        self.assertTrue(tr._recovering)
        categories = [e["category"] for e in tr.event_log]
        self.assertIn("recovery_interrupted", categories)

    def test_event_not_logged_when_not_in_rep(self):
        """Loss then recovery while no rep in-progress → no event."""
        tr = _make_tracker()
        self.assertFalse(tr._in_rep)
        for _ in range(2):
            tr.update_quality("LOST")
        tr.update_quality("GOOD")
        categories = [e["category"] for e in tr.event_log]
        self.assertNotIn("recovery_interrupted", categories)

    def test_event_has_consecutive_lost(self):
        tr = _make_tracker(fsm_max_lost_frames=10)
        _hold_position(tr, 165.0)
        for _ in range(3):
            tr.update_quality("LOST")
        tr.update_quality("GOOD")
        evt = next(e for e in tr.event_log if e["category"] == "recovery_interrupted")
        self.assertIn("consecutive_lost", evt)
        self.assertEqual(evt["consecutive_lost"], 3)


# ── tracking_reset ────────────────────────────────────────────────────────────

class TestTrackingResetEvent(unittest.TestCase):

    def test_event_logged_when_in_rep(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0)
        self.assertTrue(tr._in_rep)
        tr.reset_tracking()
        categories = [e["category"] for e in tr.event_log]
        self.assertIn("tracking_reset", categories)

    def test_event_not_logged_when_not_in_rep(self):
        tr = _make_tracker()
        self.assertFalse(tr._in_rep)
        tr.reset_tracking()
        self.assertEqual(len(tr.event_log), 0)

    def test_event_has_angle_fields(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0)
        tr.reset_tracking()
        evt = next(e for e in tr.event_log if e["category"] == "tracking_reset")
        self.assertIn("min_angle", evt)
        self.assertIn("max_angle", evt)


# ── event_log lifecycle ───────────────────────────────────────────────────────

class TestEventLogLifecycle(unittest.TestCase):

    def _make_one_event(self):
        """Return a tracker that has exactly one event logged."""
        tr = _make_tracker(fsm_max_lost_frames=3)
        _hold_position(tr, 165.0)
        for _ in range(3):
            tr.update_quality("LOST")
        self.assertEqual(len(tr.event_log), 1)
        return tr

    def test_event_log_starts_empty(self):
        tr = _make_tracker()
        self.assertEqual(tr.event_log, [])

    def test_reset_set_clears_event_log(self):
        tr = self._make_one_event()
        tr.reset_set()
        self.assertEqual(tr.event_log, [])

    def test_reset_tracking_preserves_event_log(self):
        tr = self._make_one_event()
        # reset_tracking called when NOT in-rep (already aborted)
        tr.reset_tracking()
        self.assertEqual(len(tr.event_log), 1,
                         "event_log must survive reset_tracking()")

    def test_all_event_logs_accessor(self):
        tr = self._make_one_event()
        self.assertIs(tr.all_event_logs(), tr.event_log)

    def test_successful_rep_produces_no_events(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0)
        done, _ = _hold_until_done(tr, 35.0, backdate_start=2.0)
        self.assertTrue(done)
        self.assertEqual(tr.event_log, [],
                         "Clean rep must not produce any events")

    def test_event_side_matches_tracker_side(self):
        tr = _make_tracker(fsm_max_lost_frames=3)
        _hold_position(tr, 165.0)
        for _ in range(3):
            tr.update_quality("LOST")
        self.assertEqual(tr.event_log[0]["side"], "right")


if __name__ == "__main__":
    unittest.main()
