"""
Correction Engine for Taharrak — Phase 3.

Converts raw fault detection signals into a single, prioritised correction
with severity and confidence scores.

Public API
──────────
  FAULT_PRIORITY          — global fault → priority-tier mapping (lower = higher priority)
  RepCorrection           — typed output of one correction assessment
  CorrectionEngine        — assesses live and per-rep corrections
  pick_one_correction     — select the single best correction from a list
"""
from dataclasses import dataclass

from taharrak.messages import t


# ── Priority tiers ────────────────────────────────────────────────────────────
# Tier 1 — safety / gross form (always surface first)
# Tier 2 — ROM / structural form
# Tier 3 — tempo / control  (already handled by slow_down path; included for completeness)
# Tier 4 — symmetry         (reserved for Phase 4)

FAULT_PRIORITY: dict[str, int] = {
    # Tier 1
    "trunk_swing":             1,
    "excessive_lean_back":     1,
    "upper_arm_drift":         1,
    "elbow_flare":             1,
    # Tier 2
    "incomplete_rom":          2,
    "incomplete_lockout":      2,
    "incomplete_extension":    2,
    "insufficient_depth":      2,
    "raising_too_high":        2,
    "wrist_elbow_misstacking": 2,
    "excessive_forward_lean":  2,
    # Tier 3
    "too_fast":                3,
    # Tier 4
    "asymmetry":               4,
}

# Fault key → message key used for HUD / TTS cue
_FAULT_CUE: dict[str, str] = {
    "upper_arm_drift":         "keep_upper_arm_still",
    "trunk_swing":             "dont_swing_body",
    "excessive_lean_back":     "dont_lean_back",
    "elbow_flare":             "keep_elbows_in",
    "incomplete_rom":          "curl_higher",
    "incomplete_lockout":      "finish_overhead",
    "incomplete_extension":    "finish_extension",
    "insufficient_depth":      "sit_deeper",
    "raising_too_high":        "raise_to_shoulder_height",
    "wrist_elbow_misstacking": "stack_wrists_over_elbows",
    "excessive_forward_lean":  "chest_up",
    "too_fast":                "slow_down",
}

# Quality string → confidence scalar
_QUALITY_CONFIDENCE: dict[str, float] = {"GOOD": 0.9, "WEAK": 0.5, "LOST": 0.1}

# Fault must persist this many frames before being reported (jitter suppression)
_MIN_LIVE_FRAMES = 5   # mid-rep live coaching
_MIN_REP_FRAMES  = 3   # post-rep assessment

# Fault appearing this many frames → severity = 1.0  (≈ 0.67 s at 30 fps)
_MAX_SEVERITY_FRAMES = 20


# ── RepCorrection ─────────────────────────────────────────────────────────────

@dataclass
class RepCorrection:
    """
    A single, prioritised correction output.

    main_error    : fault key (e.g. "upper_arm_drift"), or None for a clean rep
    severity      : 0.0–1.0 — how persistent / bad the fault was
    confidence    : 0.0–1.0 — tracking quality during detection
    cue_key       : message key for HUD / TTS, or None
    priority_tier : 1–4 (lower = more important; 99 = no fault)
    source        : "live" | "rep_end"
    side          : "left" | "right" | "center"
    """
    main_error:    str | None
    severity:      float
    confidence:    float
    cue_key:       str | None
    priority_tier: int
    source:        str
    side:          str = "center"


# ── CorrectionEngine ──────────────────────────────────────────────────────────

class CorrectionEngine:
    """
    Converts RepTracker fault signals into prioritised RepCorrection outputs.

    One instance per exercise session.  Keeps the last correction per side so
    post-rep summaries can compare consecutive reps.

    Typical usage
    ─────────────
    engine = CorrectionEngine()

    # Every frame while a rep is in progress:
    live = engine.assess_live(tracker, quality)

    # Immediately after tracker.update() returns rep_done=True:
    correction, summary = engine.assess_rep(tracker, quality, lang)
    # summary is (verdict_key, cue_text) or None
    """

    def __init__(self) -> None:
        # Most recent RepCorrection per tracker side ("left" / "right" / "center")
        self._last: dict[str, RepCorrection | None] = {}

    # ── Post-rep assessment ───────────────────────────────────────────

    def assess_rep(self, tracker, quality: str,
                   lang: str = "en") -> tuple[RepCorrection, "tuple | None"]:
        """
        Build a post-rep correction from a just-finished rep.

        tracker._fault_frames is still populated until the *next* _begin_rep,
        so this must be called before the tracker starts the following rep.

        Returns
        ───────
        (correction, summary) where summary is one of:
          None                                — clean rep
          ("correction_new",      cue_text)   — first faulty rep on this side
          ("correction_persists", cue_text)   — same fault as previous rep
          ("correction_fixed",    cue_text)   — previous fault gone, new one present
        """
        fault_frames: dict = dict(getattr(tracker, "_fault_frames", {}))
        confidence = _QUALITY_CONFIDENCE.get(quality, 0.5)
        side = getattr(tracker, "side", "center")

        best_fault = _pick_top_fault(fault_frames, _MIN_REP_FRAMES)

        if best_fault is None:
            correction = RepCorrection(
                main_error=None, severity=0.0, confidence=confidence,
                cue_key=None, priority_tier=99, source="rep_end", side=side,
            )
        else:
            frames   = fault_frames[best_fault]
            severity = min(frames / _MAX_SEVERITY_FRAMES, 1.0)
            correction = RepCorrection(
                main_error=best_fault,
                severity=round(severity, 3),
                confidence=confidence,
                cue_key=_FAULT_CUE.get(best_fault),
                priority_tier=FAULT_PRIORITY.get(best_fault, 3),
                source="rep_end",
                side=side,
            )

        prev = self._last.get(side)
        self._last[side] = correction
        summary = _build_summary(correction, prev, lang)
        return correction, summary

    # ── Live (mid-rep) assessment ─────────────────────────────────────

    def assess_live(self, tracker, quality: str) -> "RepCorrection | None":
        """
        Build a mid-rep correction for the current frame.

        Returns None when:
          - quality is LOST (no reliable signal)
          - no fault has persisted ≥ _MIN_LIVE_FRAMES (jitter suppression)

        The caller is responsible for enforcing one-cue policy across
        bilateral trackers via pick_one_correction().
        """
        if quality == "LOST":
            return None

        fault_frames: dict = dict(getattr(tracker, "_fault_frames", {}))
        confidence = _QUALITY_CONFIDENCE.get(quality, 0.5)
        side = getattr(tracker, "side", "center")

        best_fault = _pick_top_fault(fault_frames, _MIN_LIVE_FRAMES)
        if best_fault is None:
            return None

        frames   = fault_frames[best_fault]
        severity = min(frames / _MAX_SEVERITY_FRAMES, 1.0)

        return RepCorrection(
            main_error=best_fault,
            severity=round(severity, 3),
            confidence=confidence,
            cue_key=_FAULT_CUE.get(best_fault),
            priority_tier=FAULT_PRIORITY.get(best_fault, 3),
            source="live",
            side=side,
        )

    # ── Utilities ─────────────────────────────────────────────────────

    def last_correction(self, side: str) -> "RepCorrection | None":
        """Return the most recent RepCorrection for a given side, or None."""
        return self._last.get(side)

    def reset(self) -> None:
        """Clear per-side correction history.  Call on reset_set."""
        self._last.clear()


# ── Module-level helpers ──────────────────────────────────────────────────────

def _pick_top_fault(fault_frames: dict, min_frames: int) -> "str | None":
    """
    Select the highest-priority fault that has persisted ≥ min_frames.

    Tiebreak within the same tier: fault with more frames wins.
    Returns None if nothing qualifies.
    """
    candidates = [
        (FAULT_PRIORITY.get(f, 3), -count, f)
        for f, count in fault_frames.items()
        if count >= min_frames and f in FAULT_PRIORITY
    ]
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def _build_summary(correction: RepCorrection,
                   prev: "RepCorrection | None",
                   lang: str) -> "tuple[str, str] | None":
    """Compare this rep's correction against the previous rep on the same side."""
    if correction.main_error is None:
        return None

    cue_text = t(lang, correction.cue_key) if correction.cue_key else ""

    if prev is None or prev.main_error is None:
        return ("correction_new", cue_text)

    if prev.main_error == correction.main_error:
        return ("correction_persists", cue_text)

    # Previous fault is gone; a new one is present
    return ("correction_fixed", cue_text)


def pick_one_correction(corrections: list) -> "RepCorrection | None":
    """
    Given a list of RepCorrection objects (one per tracker side, may include
    None), return the single highest-priority non-None correction.

    Priority rule: lowest tier first; tiebreak by highest severity.
    Used by build_msgs to enforce the one-cue policy across bilateral trackers.
    """
    valid = [c for c in corrections if c is not None and c.main_error is not None]
    if not valid:
        return None
    return min(valid, key=lambda c: (c.priority_tier, -c.severity))
