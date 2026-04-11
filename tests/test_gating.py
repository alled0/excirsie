"""
Unit tests for confidence-aware gating logic inside RepTracker.

Covers:
  - joint_reliability() GOOD / WEAK / LOST classification
  - Backward compatibility when only visibility is present
  - det_quality_ex() uses combined reliability
  - update_quality() transitions: GOOD → LOST → GOOD triggers recovery mode
  - Recovery counter increments and exits correctly
  - backward-compat: smooth_quality() is an alias for update_quality()

Run:  python -m pytest tests/ -v
      python -m unittest discover tests/
"""
import unittest

from taharrak.analysis import det_quality_ex, joint_reliability
from taharrak.exercises.bicep_curl import BICEP_CURL
from taharrak.tracker import RepTracker


# ── Mock landmarks ─────────────────────────────────────────────────────────────

class _LM:
    """Landmark with visibility only (backward-compat fixture)."""
    def __init__(self, visibility: float = 1.0):
        self.visibility = visibility


class _LMFull:
    """Landmark with both visibility and presence."""
    def __init__(self, visibility: float = 1.0, presence: float = 1.0):
        self.visibility = visibility
        self.presence   = presence


# ── joint_reliability tests ────────────────────────────────────────────────────

class TestJointReliability(unittest.TestCase):
    """joint_reliability() combines visibility + presence via min()."""

    # -- visibility-only (backward-compat) ------------------------------------

    def test_vis_only_high_returns_visibility(self):
        self.assertAlmostEqual(joint_reliability(_LM(0.9)), 0.9)

    def test_vis_only_low_returns_visibility(self):
        self.assertAlmostEqual(joint_reliability(_LM(0.2)), 0.2)

    def test_no_attrs_defaults_to_one(self):
        """Object with neither visibility nor presence → 1.0 (safe default)."""
        self.assertAlmostEqual(joint_reliability(object()), 1.0)

    # -- visibility + presence (combined) -------------------------------------

    def test_both_high_returns_min(self):
        lm = _LMFull(visibility=0.95, presence=0.90)
        self.assertAlmostEqual(joint_reliability(lm), 0.90)

    def test_low_presence_downgrades_high_visibility(self):
        """Low presence should drop reliability below LOST threshold."""
        lm = _LMFull(visibility=0.90, presence=0.20)
        self.assertLess(joint_reliability(lm), 0.38)

    def test_low_visibility_downgrades_high_presence(self):
        lm = _LMFull(visibility=0.20, presence=0.90)
        self.assertLess(joint_reliability(lm), 0.38)

    def test_both_equal_returns_that_value(self):
        lm = _LMFull(visibility=0.75, presence=0.75)
        self.assertAlmostEqual(joint_reliability(lm), 0.75)


# ── det_quality_ex with presence tests ────────────────────────────────────────

_VIS_GOOD = 0.68
_VIS_WEAK = 0.38
_CFG = {"vis_good": _VIS_GOOD, "vis_weak": _VIS_WEAK}


def _lm_list(overrides: dict, default_vis: float = 0.95,
             default_pres: float | None = None) -> list:
    """
    Build a 33-element landmark list.  overrides maps index → (vis, pres) or
    index → vis (float).  default_pres=None → visibility-only landmarks.
    """
    if default_pres is None:
        lms = [_LM(default_vis) for _ in range(33)]
    else:
        lms = [_LMFull(default_vis, default_pres) for _ in range(33)]
    for idx, val in overrides.items():
        if isinstance(val, tuple):
            lms[idx] = _LMFull(*val)
        else:
            lms[idx] = _LM(val)
    return lms


class TestDetQualityExWithPresence(unittest.TestCase):
    """det_quality_ex respects the combined reliability signal."""

    def test_all_good_vis_only(self):
        """Baseline: high visibility, no presence → GOOD."""
        lm = _lm_list({})
        l_q, r_q = det_quality_ex(lm, BICEP_CURL, _CFG)
        self.assertEqual(l_q, "GOOD")
        self.assertEqual(r_q, "GOOD")

    def test_all_good_vis_and_presence(self):
        lm = _lm_list({}, default_pres=0.95)
        l_q, r_q = det_quality_ex(lm, BICEP_CURL, _CFG)
        self.assertEqual(l_q, "GOOD")
        self.assertEqual(r_q, "GOOD")

    def test_low_presence_on_key_joint_makes_lost(self):
        """
        BICEP_CURL joints_right = (RS=12, RE=14, RW=16).
        Setting presence=0.1 on RE makes reliability < vis_weak → LOST.
        """
        lm = _lm_list({14: (0.90, 0.10)}, default_pres=0.95)
        _, r_q = det_quality_ex(lm, BICEP_CURL, _CFG)
        self.assertEqual(r_q, "LOST")

    def test_low_presence_on_key_joint_does_not_affect_other_side(self):
        """Presence drop on right elbow should not degrade left quality."""
        lm = _lm_list({14: (0.90, 0.10)}, default_pres=0.95)
        l_q, _ = det_quality_ex(lm, BICEP_CURL, _CFG)
        self.assertEqual(l_q, "GOOD")

    def test_weak_presence_gives_weak(self):
        """Presence in (vis_weak, vis_good) range → WEAK not GOOD."""
        # reliability = min(0.90, 0.55) = 0.55  ∈ (0.38, 0.68)
        lm = _lm_list({12: (0.90, 0.55), 14: (0.90, 0.55), 16: (0.90, 0.55)},
                      default_pres=0.95)
        _, r_q = det_quality_ex(lm, BICEP_CURL, _CFG)
        self.assertEqual(r_q, "WEAK")

    def test_backward_compat_vis_only_weak(self):
        """Joints with only visibility in weak range → WEAK (no presence needed)."""
        lm = _lm_list({12: 0.55, 14: 0.55, 16: 0.55})
        _, r_q = det_quality_ex(lm, BICEP_CURL, _CFG)
        self.assertEqual(r_q, "WEAK")


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


# ── TrackingGuard tests ───────────────────────────────────────────────────────

from taharrak.tracker import TrackingGuard


def _guard_cfg(**overrides):
    cfg = {
        "vis_weak": 0.38,
        "guard_max_low_rel_frames": 5,
        "guard_bbox_jump": 0.25,
        "guard_scale_jump": 0.30,
        "guard_recovery_window": 5.0,
        "guard_max_recoveries": 3,
    }
    cfg.update(overrides)
    return cfg


def _lms_uniform(vis=0.95, pres=None, cx=0.5, cy=0.5,
                 l_sh=(0.40, 0.30), r_sh=(0.60, 0.30)):
    """33-landmark list with consistent shoulder positions and uniform reliability."""
    lms = [_LMFull(vis, pres if pres is not None else vis) for _ in range(33)]
    lms[11] = _LMFull(l_sh[0], l_sh[1]) if False else type('L', (), {
        'x': l_sh[0], 'y': l_sh[1], 'visibility': vis,
        'presence': pres if pres is not None else vis
    })()
    lms[12] = type('L', (), {
        'x': r_sh[0], 'y': r_sh[1], 'visibility': vis,
        'presence': pres if pres is not None else vis
    })()
    # All other landmarks at (cx, cy)
    for i in range(33):
        if i not in (11, 12):
            lms[i] = type('L', (), {
                'x': cx, 'y': cy, 'visibility': vis,
                'presence': pres if pres is not None else vis
            })()
    return lms


class _FakeTracker:
    """Minimal tracker stub that exposes _recovering."""
    def __init__(self, recovering=False):
        self._recovering = recovering


class TestTrackingGuard(unittest.TestCase):

    # -- no trigger on good signal ----------------------------------------

    def test_no_trigger_on_good_signal(self):
        guard = TrackingGuard(_guard_cfg())
        lms   = _lms_uniform(vis=0.95)
        for _ in range(10):
            fired = guard.update(lms, [_FakeTracker()], BICEP_CURL)
        self.assertFalse(fired)

    # -- low reliability trigger ------------------------------------------

    def test_low_reliability_fires_after_n_frames(self):
        """Consecutive frames with reliability below vis_weak → trigger."""
        guard = TrackingGuard(_guard_cfg(guard_max_low_rel_frames=3))
        lms   = _lms_uniform(vis=0.20)   # very low → below vis_weak=0.38
        fired = False
        for _ in range(3):
            fired = guard.update(lms, [_FakeTracker()], BICEP_CURL)
        self.assertTrue(fired)

    def test_low_reliability_does_not_fire_before_n_frames(self):
        guard = TrackingGuard(_guard_cfg(guard_max_low_rel_frames=5))
        lms   = _lms_uniform(vis=0.20)
        fired = False
        for _ in range(4):
            fired = guard.update(lms, [_FakeTracker()], BICEP_CURL)
        self.assertFalse(fired)

    def test_good_frame_resets_low_rel_counter(self):
        """One good frame in between must reset the consecutive counter."""
        guard = TrackingGuard(_guard_cfg(guard_max_low_rel_frames=3))
        low   = _lms_uniform(vis=0.20)
        good  = _lms_uniform(vis=0.95)
        guard.update(low,  [_FakeTracker()], BICEP_CURL)
        guard.update(low,  [_FakeTracker()], BICEP_CURL)
        guard.update(good, [_FakeTracker()], BICEP_CURL)  # resets counter
        fired = guard.update(low, [_FakeTracker()], BICEP_CURL)  # only 1 bad frame
        self.assertFalse(fired)

    # -- bbox jump trigger ------------------------------------------------

    def test_bbox_jump_fires_on_large_move(self):
        """Centroid jumping > guard_bbox_jump in one frame → trigger."""
        guard  = TrackingGuard(_guard_cfg(guard_bbox_jump=0.10))
        lms_a  = _lms_uniform(cx=0.5, cy=0.5)
        lms_b  = _lms_uniform(cx=0.8, cy=0.8)  # large jump
        guard.update(lms_a, [_FakeTracker()], BICEP_CURL)
        fired = guard.update(lms_b, [_FakeTracker()], BICEP_CURL)
        self.assertTrue(fired)

    def test_bbox_small_move_no_fire(self):
        guard  = TrackingGuard(_guard_cfg(guard_bbox_jump=0.25))
        lms_a  = _lms_uniform(cx=0.50, cy=0.50)
        lms_b  = _lms_uniform(cx=0.52, cy=0.51)  # tiny move
        guard.update(lms_a, [_FakeTracker()], BICEP_CURL)
        fired = guard.update(lms_b, [_FakeTracker()], BICEP_CURL)
        self.assertFalse(fired)

    # -- scale jump trigger -----------------------------------------------

    def test_scale_jump_fires_on_abrupt_zoom(self):
        """Shoulder span doubling in one frame → trigger."""
        guard  = TrackingGuard(_guard_cfg(guard_scale_jump=0.30))
        # span = 0.20 → span = 0.50 (150% increase)
        lms_a  = _lms_uniform(l_sh=(0.40, 0.30), r_sh=(0.60, 0.30))
        lms_b  = _lms_uniform(l_sh=(0.25, 0.30), r_sh=(0.75, 0.30))
        guard.update(lms_a, [_FakeTracker()], BICEP_CURL)
        fired = guard.update(lms_b, [_FakeTracker()], BICEP_CURL)
        self.assertTrue(fired)

    def test_scale_small_change_no_fire(self):
        guard  = TrackingGuard(_guard_cfg(guard_scale_jump=0.30))
        lms_a  = _lms_uniform(l_sh=(0.40, 0.30), r_sh=(0.60, 0.30))  # span 0.20
        lms_b  = _lms_uniform(l_sh=(0.41, 0.30), r_sh=(0.59, 0.30))  # span 0.18 (10%)
        guard.update(lms_a, [_FakeTracker()], BICEP_CURL)
        fired = guard.update(lms_b, [_FakeTracker()], BICEP_CURL)
        self.assertFalse(fired)

    # -- recovery frequency trigger ---------------------------------------

    def test_recovery_frequency_fires_after_max_entries(self):
        """Entering recovery ≥ max_recoveries times within window → trigger."""
        # The guard fires on the Nth recovering=True call (edge detection), not
        # on the subsequent recovering=False call, so we collect all results.
        guard   = TrackingGuard(_guard_cfg(guard_max_recoveries=3,
                                            guard_recovery_window=10.0))
        lms     = _lms_uniform()
        results = []
        for _ in range(3):
            results.append(guard.update(lms, [_FakeTracker(recovering=True)],  BICEP_CURL))
            results.append(guard.update(lms, [_FakeTracker(recovering=False)], BICEP_CURL))
        self.assertTrue(any(results), "Guard must fire within 3 recovery entries")

    def test_recovery_frequency_no_fire_below_max(self):
        guard = TrackingGuard(_guard_cfg(guard_max_recoveries=4,
                                         guard_recovery_window=10.0))
        lms   = _lms_uniform()
        fired = False
        for _ in range(3):
            guard.update(lms, [_FakeTracker(recovering=True)],  BICEP_CURL)
            fired = guard.update(lms, [_FakeTracker(recovering=False)], BICEP_CURL)
        self.assertFalse(fired)

    # -- reset() clears state ---------------------------------------------

    def test_reset_clears_low_rel_counter(self):
        guard = TrackingGuard(_guard_cfg(guard_max_low_rel_frames=3))
        lms   = _lms_uniform(vis=0.20)
        guard.update(lms, [_FakeTracker()], BICEP_CURL)
        guard.update(lms, [_FakeTracker()], BICEP_CURL)
        guard.reset()
        fired = guard.update(lms, [_FakeTracker()], BICEP_CURL)
        self.assertFalse(fired, "After reset, counter restarts from 0")

    def test_reset_clears_bbox_history(self):
        """After reset(), a position jump from old position must not re-fire."""
        guard  = TrackingGuard(_guard_cfg(guard_bbox_jump=0.10))
        lms_a  = _lms_uniform(cx=0.5, cy=0.5)
        lms_b  = _lms_uniform(cx=0.8, cy=0.8)
        guard.update(lms_a, [_FakeTracker()], BICEP_CURL)
        guard.reset()
        # First frame after reset has no previous centroid → no jump check
        fired = guard.update(lms_b, [_FakeTracker()], BICEP_CURL)
        self.assertFalse(fired)

    # -- reset_tracking preserves rep count -------------------------------

    def test_reset_tracking_preserves_rep_count(self):
        tr = _make_tracker()
        tr.rep_count = 5
        tr.stage     = "start"
        tr._in_rep   = True
        tr.reset_tracking()
        self.assertEqual(tr.rep_count, 5,   "rep_count must survive reset_tracking()")
        self.assertIsNone(tr.stage,         "stage must be cleared")
        self.assertFalse(tr._in_rep,        "_in_rep must be cleared")
        self.assertFalse(tr._recovering,    "_recovering must be cleared")


if __name__ == "__main__":
    unittest.main()
