"""
Unit tests for taharrak/correction.py — Phase 3 Correction Engine.

Covers:
  - FAULT_PRIORITY ordering (tier 1 beats tier 2)
  - _pick_top_fault selection and min-frames gate
  - RepCorrection fields and defaults
  - CorrectionEngine.assess_rep:
      severity calculation from fault_frames
      confidence from quality string
      clean rep produces priority_tier=99, main_error=None
  - CorrectionEngine.assess_live:
      returns None on LOST quality
      returns None when no fault meets min-frames threshold
      returns correct RepCorrection when fault persists
  - Priority beats frame-count: tier-1 fault with fewer frames beats tier-2 with more
  - Post-rep summaries (correction_new / correction_persists / correction_fixed)
  - One-cue policy: pick_one_correction across bilateral trackers
  - CorrectionEngine.reset clears history
  - build_post_rep_summary integration with messages

Run:  python -m unittest discover tests/
"""
import unittest
from collections import Counter
from unittest.mock import MagicMock

from taharrak.correction import (
    FAULT_PRIORITY,
    RepCorrection,
    CorrectionEngine,
    pick_one_correction,
    _pick_top_fault,
    _MIN_LIVE_FRAMES,
    _MIN_REP_FRAMES,
    _MAX_SEVERITY_FRAMES,
)
from taharrak.analysis import build_post_rep_summary


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tracker(side: str = "left", fault_frames: dict | None = None) -> MagicMock:
    """Return a minimal tracker mock with _fault_frames and side set."""
    tr = MagicMock()
    tr.side = side
    tr._fault_frames = Counter(fault_frames or {})
    return tr


# ── FAULT_PRIORITY ────────────────────────────────────────────────────────────

class TestFaultPriority(unittest.TestCase):

    def test_tier1_faults_present(self):
        for fault in ("trunk_swing", "excessive_lean_back", "upper_arm_drift", "elbow_flare"):
            self.assertEqual(FAULT_PRIORITY[fault], 1, fault)

    def test_tier2_faults_present(self):
        for fault in ("incomplete_rom", "incomplete_lockout", "incomplete_extension",
                      "insufficient_depth", "raising_too_high", "wrist_elbow_misstacking"):
            self.assertEqual(FAULT_PRIORITY[fault], 2, fault)

    def test_tier1_lower_than_tier2(self):
        self.assertLess(FAULT_PRIORITY["trunk_swing"], FAULT_PRIORITY["incomplete_rom"])

    def test_tier3_reserved(self):
        self.assertEqual(FAULT_PRIORITY["too_fast"], 3)


# ── _pick_top_fault ───────────────────────────────────────────────────────────

class TestPickTopFault(unittest.TestCase):

    def test_returns_none_when_empty(self):
        self.assertIsNone(_pick_top_fault({}, _MIN_REP_FRAMES))

    def test_returns_none_below_min_frames(self):
        faults = {"upper_arm_drift": _MIN_REP_FRAMES - 1}
        self.assertIsNone(_pick_top_fault(faults, _MIN_REP_FRAMES))

    def test_returns_fault_at_exact_min_frames(self):
        faults = {"upper_arm_drift": _MIN_REP_FRAMES}
        self.assertEqual(_pick_top_fault(faults, _MIN_REP_FRAMES), "upper_arm_drift")

    def test_tier1_beats_tier2_regardless_of_frame_count(self):
        # trunk_swing (tier 1) with fewer frames beats incomplete_rom (tier 2) with more
        faults = {"trunk_swing": _MIN_REP_FRAMES, "incomplete_rom": _MAX_SEVERITY_FRAMES}
        self.assertEqual(_pick_top_fault(faults, _MIN_REP_FRAMES), "trunk_swing")

    def test_tiebreak_within_tier_by_frame_count(self):
        # Both tier 2 — the one with more frames should win
        faults = {"incomplete_rom": 5, "insufficient_depth": 10}
        result = _pick_top_fault(faults, _MIN_REP_FRAMES)
        self.assertEqual(result, "insufficient_depth")

    def test_unknown_fault_ignored(self):
        faults = {"made_up_fault": 100}
        self.assertIsNone(_pick_top_fault(faults, _MIN_REP_FRAMES))


# ── CorrectionEngine.assess_rep ───────────────────────────────────────────────

class TestAssessRep(unittest.TestCase):

    def setUp(self):
        self.engine = CorrectionEngine()

    def test_clean_rep_main_error_is_none(self):
        tr = _make_tracker("left", {})
        correction, summary = self.engine.assess_rep(tr, "GOOD")
        self.assertIsNone(correction.main_error)
        self.assertEqual(correction.priority_tier, 99)

    def test_clean_rep_summary_is_none(self):
        tr = _make_tracker("left", {})
        _, summary = self.engine.assess_rep(tr, "GOOD")
        self.assertIsNone(summary)

    def test_severity_scales_with_frame_count(self):
        tr = _make_tracker("left", {"upper_arm_drift": 10})
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        expected = round(10 / _MAX_SEVERITY_FRAMES, 3)
        self.assertAlmostEqual(correction.severity, expected, places=3)

    def test_severity_capped_at_1(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MAX_SEVERITY_FRAMES * 5})
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        self.assertEqual(correction.severity, 1.0)

    def test_confidence_from_good_quality(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_REP_FRAMES})
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        self.assertAlmostEqual(correction.confidence, 0.9)

    def test_confidence_from_weak_quality(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_REP_FRAMES})
        correction, _ = self.engine.assess_rep(tr, "WEAK")
        self.assertAlmostEqual(correction.confidence, 0.5)

    def test_confidence_from_lost_quality(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_REP_FRAMES})
        correction, _ = self.engine.assess_rep(tr, "LOST")
        self.assertAlmostEqual(correction.confidence, 0.1)

    def test_cue_key_populated(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_REP_FRAMES})
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        self.assertEqual(correction.cue_key, "keep_upper_arm_still")

    def test_priority_tier_set_correctly(self):
        tr = _make_tracker("left", {"trunk_swing": _MIN_REP_FRAMES})
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        self.assertEqual(correction.priority_tier, 1)

    def test_tier1_picked_over_tier2(self):
        # trunk_swing (tier 1) with min frames beats incomplete_rom (tier 2) with many
        faults = {"trunk_swing": _MIN_REP_FRAMES, "incomplete_rom": _MAX_SEVERITY_FRAMES}
        tr = _make_tracker("left", faults)
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        self.assertEqual(correction.main_error, "trunk_swing")

    def test_side_stored_on_correction(self):
        tr = _make_tracker("right", {"upper_arm_drift": _MIN_REP_FRAMES})
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        self.assertEqual(correction.side, "right")

    def test_source_is_rep_end(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_REP_FRAMES})
        correction, _ = self.engine.assess_rep(tr, "GOOD")
        self.assertEqual(correction.source, "rep_end")


# ── CorrectionEngine.assess_live ─────────────────────────────────────────────

class TestAssessLive(unittest.TestCase):

    def setUp(self):
        self.engine = CorrectionEngine()

    def test_returns_none_on_lost(self):
        tr = _make_tracker("left", {"upper_arm_drift": 100})
        self.assertIsNone(self.engine.assess_live(tr, "LOST"))

    def test_returns_none_below_min_live_frames(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_LIVE_FRAMES - 1})
        self.assertIsNone(self.engine.assess_live(tr, "GOOD"))

    def test_returns_correction_at_min_live_frames(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_LIVE_FRAMES})
        result = self.engine.assess_live(tr, "GOOD")
        self.assertIsNotNone(result)
        self.assertEqual(result.main_error, "upper_arm_drift")

    def test_source_is_live(self):
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_LIVE_FRAMES})
        result = self.engine.assess_live(tr, "GOOD")
        self.assertEqual(result.source, "live")

    def test_tier1_beats_tier2_live(self):
        faults = {"trunk_swing": _MIN_LIVE_FRAMES, "incomplete_rom": _MAX_SEVERITY_FRAMES}
        tr = _make_tracker("left", faults)
        result = self.engine.assess_live(tr, "GOOD")
        self.assertEqual(result.main_error, "trunk_swing")

    def test_returns_none_no_faults(self):
        tr = _make_tracker("left", {})
        self.assertIsNone(self.engine.assess_live(tr, "GOOD"))


# ── Post-rep summaries ────────────────────────────────────────────────────────

class TestPostRepSummary(unittest.TestCase):

    def setUp(self):
        self.engine = CorrectionEngine()

    def _rep(self, side: str, fault: str | None, frames: int = _MIN_REP_FRAMES):
        """Run assess_rep once and return (correction, summary)."""
        faults = {fault: frames} if fault else {}
        tr = _make_tracker(side, faults)
        return self.engine.assess_rep(tr, "GOOD", lang="en")

    def test_first_faulty_rep_is_correction_new(self):
        _, summary = self._rep("left", "upper_arm_drift")
        self.assertIsNotNone(summary)
        verdict, _ = summary
        self.assertEqual(verdict, "correction_new")

    def test_same_fault_two_reps_is_correction_persists(self):
        self._rep("left", "upper_arm_drift")      # rep 1
        _, summary = self._rep("left", "upper_arm_drift")  # rep 2
        verdict, _ = summary
        self.assertEqual(verdict, "correction_persists")

    def test_different_fault_is_correction_fixed(self):
        self._rep("left", "upper_arm_drift")          # rep 1: drift
        _, summary = self._rep("left", "trunk_swing") # rep 2: swing
        verdict, _ = summary
        self.assertEqual(verdict, "correction_fixed")

    def test_clean_rep_after_fault_summary_is_none(self):
        self._rep("left", "upper_arm_drift")
        _, summary = self._rep("left", None)
        self.assertIsNone(summary)

    def test_sides_tracked_independently(self):
        # Left has a fault; right is clean — they shouldn't interfere
        self._rep("left", "upper_arm_drift")
        _, summary_right = self._rep("right", "trunk_swing")
        # Right has no prior history — should be correction_new, not persists
        verdict, _ = summary_right
        self.assertEqual(verdict, "correction_new")

    def test_cue_text_in_summary(self):
        _, summary = self._rep("left", "upper_arm_drift")
        _, cue_text = summary
        self.assertIn("upper arm", cue_text.lower())

    def test_persists_cue_text_unchanged(self):
        self._rep("left", "upper_arm_drift")
        _, summary = self._rep("left", "upper_arm_drift")
        _, cue_text = summary
        self.assertIn("upper arm", cue_text.lower())


# ── pick_one_correction ───────────────────────────────────────────────────────

class TestPickOneCorrection(unittest.TestCase):

    def _correction(self, fault: str | None, tier: int, severity: float,
                    side: str = "left") -> RepCorrection:
        return RepCorrection(
            main_error=fault, severity=severity, confidence=0.9,
            cue_key=None, priority_tier=tier, source="live", side=side,
        )

    def test_returns_none_for_empty_list(self):
        self.assertIsNone(pick_one_correction([]))

    def test_returns_none_for_all_none(self):
        self.assertIsNone(pick_one_correction([None, None]))

    def test_returns_none_for_clean_corrections(self):
        a = self._correction(None, 99, 0.0, "left")
        b = self._correction(None, 99, 0.0, "right")
        self.assertIsNone(pick_one_correction([a, b]))

    def test_picks_lower_tier(self):
        tier1 = self._correction("trunk_swing", 1, 0.3, "left")
        tier2 = self._correction("incomplete_rom", 2, 0.9, "right")
        result = pick_one_correction([tier1, tier2])
        self.assertEqual(result.main_error, "trunk_swing")

    def test_tiebreak_by_severity(self):
        a = self._correction("trunk_swing", 1, 0.4, "left")
        b = self._correction("upper_arm_drift", 1, 0.8, "right")
        result = pick_one_correction([a, b])
        self.assertEqual(result.main_error, "upper_arm_drift")

    def test_skips_none_entries(self):
        valid = self._correction("trunk_swing", 1, 0.5, "left")
        result = pick_one_correction([None, valid, None])
        self.assertEqual(result.main_error, "trunk_swing")

    def test_bilateral_one_clean_one_faulty(self):
        clean = self._correction(None, 99, 0.0, "left")
        fault = self._correction("incomplete_rom", 2, 0.6, "right")
        result = pick_one_correction([clean, fault])
        self.assertEqual(result.main_error, "incomplete_rom")


# ── CorrectionEngine.reset ────────────────────────────────────────────────────

class TestCorrectionEngineReset(unittest.TestCase):

    def test_reset_clears_history(self):
        engine = CorrectionEngine()
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_REP_FRAMES})
        engine.assess_rep(tr, "GOOD", lang="en")
        self.assertIsNotNone(engine.last_correction("left"))

        engine.reset()
        self.assertIsNone(engine.last_correction("left"))

    def test_after_reset_next_rep_is_correction_new(self):
        engine = CorrectionEngine()
        tr = _make_tracker("left", {"upper_arm_drift": _MIN_REP_FRAMES})
        engine.assess_rep(tr, "GOOD", lang="en")   # rep 1
        engine.reset()
        _, summary = engine.assess_rep(tr, "GOOD", lang="en")  # rep 2 after reset
        # History was cleared — should be treated as first faulty rep
        verdict, _ = summary
        self.assertEqual(verdict, "correction_new")


# ── build_post_rep_summary ────────────────────────────────────────────────────

class TestBuildPostRepSummary(unittest.TestCase):

    def test_none_summary_returns_empty(self):
        self.assertEqual(build_post_rep_summary(None, "en"), [])

    def test_correction_new_returns_cue_text(self):
        msgs = build_post_rep_summary(("correction_new", "Keep your upper arm still"), "en")
        self.assertEqual(len(msgs), 1)
        text, severity = msgs[0]
        self.assertIn("Keep your upper arm still", text)
        self.assertEqual(severity, "warning")

    def test_correction_persists_prefixed(self):
        msgs = build_post_rep_summary(("correction_persists", "Keep your upper arm still"), "en")
        self.assertEqual(len(msgs), 1)
        text, severity = msgs[0]
        self.assertIn("Still:", text)
        self.assertIn("Keep your upper arm still", text)
        self.assertEqual(severity, "warning")

    def test_correction_fixed_says_fixed(self):
        msgs = build_post_rep_summary(("correction_fixed", "Don't lean back"), "en")
        self.assertEqual(len(msgs), 1)
        text, severity = msgs[0]
        self.assertIn("Fixed", text)
        self.assertEqual(severity, "ok")

    def test_arabic_correction_persists(self):
        msgs = build_post_rep_summary(("correction_persists", "ثبّت أعلى الذراع"), "ar")
        self.assertEqual(len(msgs), 1)
        text, _ = msgs[0]
        self.assertIn("لا يزال", text)

    def test_arabic_correction_fixed(self):
        msgs = build_post_rep_summary(("correction_fixed", ""), "ar")
        text, _ = msgs[0]
        self.assertIn("أحسنت", text)


if __name__ == "__main__":
    unittest.main()
