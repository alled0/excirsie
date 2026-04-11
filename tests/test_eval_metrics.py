"""
Unit tests for eval harness robustness metrics.

Covers:
  - RepTracker.aborted_reps counter increments on _abort_rep()
  - RepTracker.rejected_reps counter increments once per threshold crossing
    (not once per frame while the angle stays in the end zone)
  - rejected_reps does NOT increment when the rep completes legitimately
  - counters survive reset_tracking() but reset on reset_set()
  - compute_signal_quality() formula (boundary values + typical cases)
  - New eval metrics are present in replay output when run in no-video mode
    (tested via the accumulation helpers directly)

Run:  python -m unittest discover tests/
"""
import time
import unittest

from taharrak.eval import compute_signal_quality
from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.tracker import RepTracker

# Reuse dt-injection helpers from test_fsm
from tests.test_fsm import _angle_to_lms, _hold_position, _hold_until_done, _SIM_DT


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


def _advance_with_video_time(tr, angle_deg: float, frame_idx: int,
                             n: int = 20, w: int = 1, h: int = 1):
    """Feed n synthetic video frames using explicit timestamps."""
    p, v, d, s = _angle_to_lms(angle_deg)
    result = (angle_deg, False, False, None)
    for i in range(n):
        frame_time_s = (frame_idx + i) * _SIM_DT
        result = tr.update(p, v, d, s, w, h, now=frame_time_s)
    return frame_idx + n, result


def _advance_until_done_with_video_time(tr, angle_deg: float, frame_idx: int,
                                        max_frames: int = 40,
                                        w: int = 1, h: int = 1):
    """Feed synthetic video frames until a rep completes or frames run out."""
    p, v, d, s = _angle_to_lms(angle_deg)
    for i in range(max_frames):
        frame_time_s = (frame_idx + i) * _SIM_DT
        _, _, done, score = tr.update(p, v, d, s, w, h, now=frame_time_s)
        if done:
            return frame_idx + i + 1, True, score
    return frame_idx + max_frames, False, None


# ── aborted_reps tests ────────────────────────────────────────────────────────

class TestAbortedRepsCounter(unittest.TestCase):

    def test_starts_at_zero(self):
        tr = _make_tracker()
        self.assertEqual(tr.aborted_reps, 0)

    def test_abort_increments_counter(self):
        tr = _make_tracker(fsm_max_lost_frames=3)
        _hold_position(tr, 165.0)      # enter start → _in_rep=True
        self.assertTrue(tr._in_rep)
        for _ in range(3):
            tr.update_quality("LOST")
        self.assertEqual(tr.aborted_reps, 1)

    def test_multiple_aborts_accumulate(self):
        tr = _make_tracker(fsm_max_lost_frames=3)
        for _ in range(2):
            _hold_position(tr, 165.0)
            for _ in range(3):
                tr.update_quality("LOST")
        self.assertEqual(tr.aborted_reps, 2)

    def test_successful_rep_does_not_increment_aborted(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0)
        _hold_until_done(tr, 35.0)
        self.assertEqual(tr.aborted_reps, 0)

    def test_reset_set_clears_aborted_counter(self):
        tr = _make_tracker(fsm_max_lost_frames=3)
        _hold_position(tr, 165.0)
        for _ in range(3):
            tr.update_quality("LOST")
        self.assertEqual(tr.aborted_reps, 1)
        tr.reset_set()
        self.assertEqual(tr.aborted_reps, 0)

    def test_reset_tracking_preserves_aborted_counter(self):
        """reset_tracking() is a soft reset — running count must survive."""
        tr = _make_tracker(fsm_max_lost_frames=3)
        _hold_position(tr, 165.0)
        for _ in range(3):
            tr.update_quality("LOST")
        self.assertEqual(tr.aborted_reps, 1)
        tr.reset_tracking()
        self.assertEqual(tr.aborted_reps, 1)


# ── rejected_reps tests ───────────────────────────────────────────────────────

class TestRejectedRepsCounter(unittest.TestCase):

    def test_starts_at_zero(self):
        tr = _make_tracker()
        self.assertEqual(tr.rejected_reps, 0)

    def test_fast_rep_increments_rejected_once(self):
        """
        Angle held at end position immediately after starting — duration
        is below min_rep_time so the rep is rejected.  Holding for many frames
        must NOT produce multiple increments (one rejection per crossing).

        dt must be injected so the One Euro filter converges past angle_up,
        but _rep_start is NOT backdated so duration stays short.
        """
        from tests.test_fsm import _angle_to_lms

        tr = _make_tracker()
        W = H = 1
        # Enter start position with proper dt injection
        _hold_position(tr, 165.0, n=20)
        self.assertEqual(tr.stage, "start")

        # Hold at end angle with proper dt but recent _rep_start (short duration)
        p, v, d, s = _angle_to_lms(35.0)
        rep_start = tr._rep_start     # preserve the recent timestamp
        for _ in range(20):
            tr._last_upd_t = time.time() - _SIM_DT
            tr._rep_start  = rep_start   # keep duration short
            tr.update(p, v, d, s, W, H)

        self.assertEqual(tr.rejected_reps, 1,
                         "One crossing should produce exactly one rejection")
        self.assertEqual(tr.rep_count, 0)

    def test_slow_rep_does_not_increment_rejected(self):
        tr = _make_tracker()
        _hold_position(tr, 165.0)
        done, _ = _hold_until_done(tr, 35.0, backdate_start=2.0)
        self.assertTrue(done)
        self.assertEqual(tr.rejected_reps, 0)

    def test_second_crossing_after_completed_rep_counts_again(self):
        """
        _min_dur_blocked is cleared inside _begin_rep().  After a successful
        rep (stage → 'end') the user extends again → _begin_rep() fires →
        flag is clear → next fast crossing produces a new rejection.
        """
        from tests.test_fsm import _angle_to_lms

        tr = _make_tracker()

        # 1. Complete one legitimate rep so stage → "end"
        _hold_position(tr, 165.0, n=20)
        done, _ = _hold_until_done(tr, 35.0, backdate_start=2.0)
        self.assertTrue(done)
        self.assertEqual(tr.stage, "end")
        self.assertFalse(tr._min_dur_blocked)

        # 2. Enter start again (stage "end" → "start" via _begin_rep)
        _hold_position(tr, 165.0, n=20)
        self.assertEqual(tr.stage, "start")

        # 3. Fast crossing — should count as rejected_reps=1
        rep_start = tr._rep_start
        p, v, d, s = _angle_to_lms(35.0)
        for _ in range(20):
            tr._last_upd_t = time.time() - _SIM_DT
            tr._rep_start  = rep_start
            tr.update(p, v, d, s, 1, 1)
        self.assertEqual(tr.rejected_reps, 1)

    def _setup_one_rejection(self):
        """Return a tracker that has exactly one rejected rep recorded."""
        from tests.test_fsm import _angle_to_lms
        tr = _make_tracker()
        _hold_position(tr, 165.0, n=20)
        rep_start = tr._rep_start
        p, v, d, s = _angle_to_lms(35.0)
        for _ in range(20):
            tr._last_upd_t = time.time() - _SIM_DT
            tr._rep_start  = rep_start
            tr.update(p, v, d, s, 1, 1)
        self.assertEqual(tr.rejected_reps, 1)
        return tr

    def test_reset_set_clears_rejected_counter(self):
        tr = self._setup_one_rejection()
        tr.reset_set()
        self.assertEqual(tr.rejected_reps, 0)

    def test_reset_tracking_preserves_rejected_counter(self):
        tr = self._setup_one_rejection()
        tr.reset_tracking()
        self.assertEqual(tr.rejected_reps, 1)


# ── compute_signal_quality tests ──────────────────────────────────────────────

class TestComputeSignalQuality(unittest.TestCase):

    def test_perfect_signal_is_one(self):
        self.assertAlmostEqual(
            compute_signal_quality(0.0, 1.0, 0.0), 1.0, places=4)

    def test_zero_reliability_gives_zero(self):
        self.assertAlmostEqual(
            compute_signal_quality(0.0, 0.0, 0.0), 0.0, places=4)

    def test_full_dropout_gives_zero(self):
        self.assertAlmostEqual(
            compute_signal_quality(1.0, 1.0, 0.0), 0.0, places=4)

    def test_full_recovery_gives_zero(self):
        self.assertAlmostEqual(
            compute_signal_quality(0.0, 1.0, 1.0), 0.0, places=4)

    def test_typical_good_session(self):
        """0% dropout, 0.90 reliability, 5% recovery → ~0.855."""
        result = compute_signal_quality(0.0, 0.90, 0.05)
        self.assertAlmostEqual(result, 0.90 * 0.95, places=3)

    def test_multiplicative_penalty(self):
        """Each penalty factor is independent and multiplicative."""
        d, r, rec = 0.10, 0.80, 0.20
        expected = (1 - d) * r * (1 - rec)
        self.assertAlmostEqual(compute_signal_quality(d, r, rec), expected, places=4)

    def test_result_is_rounded_to_4dp(self):
        """Return value must be rounded to 4 decimal places."""
        result = compute_signal_quality(0.01, 0.99, 0.01)
        self.assertEqual(result, round(result, 4))

    def test_result_always_in_0_1(self):
        for d in (0.0, 0.5, 1.0):
            for r in (0.0, 0.5, 1.0):
                for rec in (0.0, 0.5, 1.0):
                    sq = compute_signal_quality(d, r, rec)
                    self.assertGreaterEqual(sq, 0.0)
                    self.assertLessEqual(sq, 1.0)


class TestOfflineReplayTimingRegression(unittest.TestCase):

    def test_explicit_video_time_preserves_valid_rep(self):
        tr = _make_tracker()

        frame_idx, _ = _advance_with_video_time(tr, 165.0, frame_idx=0, n=40)
        self.assertEqual(tr.stage, "start")

        frame_idx, done, _ = _advance_until_done_with_video_time(
            tr, 35.0, frame_idx=frame_idx, max_frames=40
        )
        self.assertTrue(done)
        self.assertEqual(tr.rep_count, 1)
        self.assertEqual(tr.rejected_reps, 0)

    def test_offline_timebase_is_independent_from_live_wall_clock(self):
        tr = _make_tracker()
        frame_idx = 0

        frame_idx, _ = _advance_with_video_time(tr, 165.0, frame_idx, n=40)
        frame_idx, done, _ = _advance_until_done_with_video_time(
            tr, 35.0, frame_idx, max_frames=40
        )

        self.assertTrue(done)
        self.assertGreaterEqual(frame_idx * _SIM_DT, BICEP_CURL.min_rep_time)
        self.assertEqual(tr.rep_count, 1)
        self.assertEqual(tr.rejected_reps, 0)


if __name__ == "__main__":
    unittest.main()
