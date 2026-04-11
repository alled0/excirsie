"""
Pose analysis helpers for Taharrak.

  joint_reliability     — combined visibility + presence score for one landmark
  det_quality_ex        — per-arm detection quality (GOOD / WEAK / LOST)
  analyze_camera_position — actionable camera setup feedback
  build_msgs            — real-time form feedback strings for the workout HUD
"""

from taharrak.exercises.base import Exercise
from taharrak.messages import t


_FAULT_RULES = {
    "1": {
        "upper_arm_drift": ("keep_upper_arm_still", "warning", "secondary_signals"),
        "trunk_swing": ("dont_swing_body", "error", "secondary_signals"),
        "incomplete_rom": ("curl_higher", "warning", "primary_signal"),
    },
    "2": {
        "excessive_lean_back": ("dont_lean_back", "error", "secondary_signals"),
        "incomplete_lockout": ("finish_overhead", "warning", "primary_signal"),
        "wrist_elbow_misstacking": ("stack_wrists_over_elbows", "warning", "secondary_signals"),
    },
    "3": {
        "raising_too_high": ("raise_to_shoulder_height", "warning", "primary_signal"),
    },
    "4": {
        "elbow_flare": ("keep_elbows_in", "warning", "secondary_signals"),
        "incomplete_extension": ("finish_extension", "warning", "primary_signal"),
    },
    "5": {
        "insufficient_depth": ("sit_deeper", "warning", "primary_signal"),
        "excessive_forward_lean": ("chest_up", "warning", "secondary_signals"),
    },
}

_POSITIVE_HINTS = {
    "1": {"end": "lower_with_control"},
    "2": {"start": "finish_overhead"},
    "3": {"start": "raise_to_shoulder_height"},
    "4": {"start": "finish_extension"},
    "5": {"end": "stand_tall"},
}


# ── Joint reliability ─────────────────────────────────────────────────────────

def joint_reliability(lm) -> float:
    """
    Combined reliability score in [0, 1] for a single landmark.

    When MediaPipe exposes both ``visibility`` (occlusion likelihood) and
    ``presence`` (likelihood the landmark is inside the frame), we take the
    minimum: both must be high for the joint to be considered reliable.

    Falls back to ``visibility`` alone when ``presence`` is absent (e.g. when
    landmarks come from an older pose model or a hand-crafted test fixture).
    This ensures backward compatibility with any code that only sets
    ``visibility``.
    """
    vis  = getattr(lm, 'visibility', 1.0)
    pres = getattr(lm, 'presence',   None)
    return vis if pres is None else min(vis, pres)


# ── Detection quality ─────────────────────────────────────────────────────────

def det_quality_ex(lm, exercise: Exercise, cfg: dict) -> tuple:
    """Returns (left_quality, right_quality) — each is 'GOOD', 'WEAK', or 'LOST'."""
    VG, VW = cfg.get("vis_good", 0.68), cfg.get("vis_weak", 0.38)

    def _q(indices):
        rel = [joint_reliability(lm[i]) for i in indices]
        if all(r > VG for r in rel): return "GOOD"
        if all(r > VW for r in rel): return "WEAK"
        return "LOST"

    return _q(exercise.joints_left), _q(exercise.joints_right)


# ── Camera position analysis ──────────────────────────────────────────────────

def analyze_camera_position(lm) -> list:
    """
    Analyses smoothed pose landmarks and returns a list of message-key strings
    that describe camera position issues.  An empty list means the position is good.

    Checks (in priority order):
      1. Landmark visibility  → cam_poor_vis
      2. Distance             → cam_too_close / cam_too_far
      3. Horizontal centering → cam_move_right / cam_move_left
      4. Camera height        → cam_too_low / cam_too_high
      5. Body rotation        → cam_turn_right / cam_turn_left
    """
    issues = []

    l_sh = lm[11]   # left  shoulder (MediaPipe landmark 11)
    r_sh = lm[12]   # right shoulder (MediaPipe landmark 12)

    # -- Reliability: if key landmarks are mostly invisible/absent, lighting is bad
    key_vis = [joint_reliability(lm[i]) for i in (0, 11, 12, 23, 24)]
    if sum(key_vis) / len(key_vis) < 0.35:
        issues.append("cam_poor_vis")
        return issues   # can't judge geometry — stop here

    # -- Distance via shoulder span (normalised 0-1 width)
    sh_width = abs(l_sh.x - r_sh.x)
    if sh_width > 0.48:
        issues.append("cam_too_close")
    elif sh_width < 0.15:
        issues.append("cam_too_far")

    # -- Horizontal centering: shoulder midpoint should be near x = 0.5
    mid_x = (l_sh.x + r_sh.x) / 2.0
    if mid_x < 0.35:
        issues.append("cam_move_right")
    elif mid_x > 0.65:
        issues.append("cam_move_left")

    # -- Camera height: shoulder midpoint should sit in the upper-middle of frame
    mid_y = (l_sh.y + r_sh.y) / 2.0
    if mid_y > 0.70:
        issues.append("cam_too_low")    # shoulders near bottom → camera is low
    elif mid_y < 0.15:
        issues.append("cam_too_high")   # shoulders near top    → camera is high

    # -- Body rotation: large vertical shoulder asymmetry → person is turned
    sh_y_diff = abs(l_sh.y - r_sh.y)
    if sh_y_diff > 0.06:
        issues.append("cam_turn_right" if l_sh.y < r_sh.y else "cam_turn_left")

    return issues


# ── Exercise-specific framing gate ────────────────────────────────────────────

def check_exercise_framing(lm, exercise: Exercise, cfg: dict) -> list:
    """
    Checks that the joints critical to *this* exercise are visible at GOOD
    confidence.  Returns a list of message keys; empty means all clear.

    Unlike det_quality_ex (which checks all joints and returns GOOD/WEAK/LOST),
    this function returns actionable message keys for the calibration HUD so
    the user knows *which* joints are hidden.

    The checked joints come from exercise.key_joints_left /
    exercise.key_joints_right.  If an exercise has no key joints set, this
    function returns an empty list (no-op, safe for legacy exercises).
    """
    VG     = cfg.get("vis_good", 0.68)
    issues = []

    if exercise.bilateral and exercise.key_joints_left:
        hidden_l = [i for i in exercise.key_joints_left
                    if joint_reliability(lm[i]) < VG]
        if hidden_l:
            issues.append("joint_hidden")

    if exercise.key_joints_right:
        hidden_r = [i for i in exercise.key_joints_right
                    if joint_reliability(lm[i]) < VG]
        if hidden_r and "joint_hidden" not in issues:
            issues.append("joint_hidden")

    return issues


def build_setup_msgs(qualities: list[str], cam_feedback: list[str],
                     trust, lang: str) -> list:
    """Trust-building guidance shown when coaching is intentionally suppressed."""
    msgs = []
    if cam_feedback:
        for key in cam_feedback[:2]:
            msgs.append((f"  {t(lang, key)}", "warning"))
        return msgs

    if any(q == "LOST" for q in qualities):
        return [(f"  {t(lang, 'joint_hidden')}", "warning")]
    if any(q == "WEAK" for q in qualities):
        return [(f"  {t(lang, 'cam_poor_vis')}", "warning")]
    if trust and trust.render_allowed and not trust.coaching_allowed:
        return [(f"  {t(lang, 'hold_still_tracking')}", "ok")]
    return msgs


def _quality_meets(quality: str | None, requirement: str | None) -> bool:
    if quality is None or requirement is None:
        return True
    if requirement == "GOOD":
        return quality == "GOOD"
    if requirement == "WEAK_OR_BETTER":
        return quality in {"GOOD", "WEAK"}
    return quality != "LOST"


def _format_profile_cue(lang: str, cue_key: str, side_ln: str, bilateral: bool) -> str:
    cue = t(lang, cue_key)
    if bilateral and side_ln:
        return f"  [{side_ln}] {cue}"
    return f"  {cue}"


def _profile_feedback(tracker, angle: float | None, exercise: Exercise,
                      quality: str | None, lang: str) -> tuple[str, str] | None:
    profile = exercise.technique_profile
    if profile is None:
        return None

    fault_rules = _FAULT_RULES.get(exercise.key, {})
    tech_state = getattr(tracker, "technique_state", {}) or {}
    side_ln = t(lang, getattr(tracker, "side", "")) if exercise.bilateral else ""

    for fault in profile.top_faults:
        meta = fault_rules.get(fault)
        if meta is None or fault not in tech_state.get("faults", ()):
            continue
        cue_key, severity, signal_kind = meta
        requirement = profile.confidence_requirements.get(signal_kind)
        if _quality_meets(quality, requirement):
            return _format_profile_cue(lang, cue_key, side_ln, exercise.bilateral), severity

    if angle is None or not _quality_meets(
        quality, profile.confidence_requirements.get("primary_signal")
    ):
        return None

    end_range = (tech_state.get("signals", {}) or {}).get("end_range", ())
    if not isinstance(end_range, tuple) or len(end_range) != 2:
        return None

    cue_key = None
    if exercise.key == "1" and tracker.stage == "start" and tracker.rep_elapsed > 0.35 and angle > end_range[1]:
        cue_key = "curl_higher"
    elif exercise.key == "2" and tracker.stage == "start" and tracker.rep_elapsed > 0.35 and angle < end_range[0]:
        cue_key = "finish_overhead"
    elif exercise.key == "3" and tracker.stage == "start" and tracker.rep_elapsed > 0.35 and angle > end_range[1] + 5.0:
        cue_key = "raise_to_shoulder_height"
    elif exercise.key == "4" and tracker.stage == "start" and tracker.rep_elapsed > 0.35 and angle < end_range[0]:
        cue_key = "finish_extension"
    elif exercise.key == "5" and tracker.stage == "start" and tracker.rep_elapsed > 0.45 and angle > end_range[1]:
        cue_key = "sit_deeper"

    if cue_key is None:
        return None
    return _format_profile_cue(lang, cue_key, side_ln, exercise.bilateral), "warning"


def _profile_hint(tracker, exercise: Exercise, lang: str) -> str | None:
    cue_key = _POSITIVE_HINTS.get(exercise.key, {}).get(tracker.stage)
    if cue_key is None:
        return None
    side_ln = t(lang, getattr(tracker, "side", "")) if exercise.bilateral else ""
    return _format_profile_cue(lang, cue_key, side_ln, exercise.bilateral).strip()


# ── Form feedback messages ────────────────────────────────────────────────────

_SIDES_EN = ["LEFT", "RIGHT"]


def build_msgs(trackers: list, angles: list, swings: list,
               exercise: Exercise, voice, cfg: dict, lang: str,
               qualities: list[str] | None = None,
               trust = None,
               cam_feedback: list[str] | None = None) -> list:
    """
    Build real-time form feedback message list for the workout HUD.
    Returns list of (text, severity) tuples where severity is one of:
      "error"   — must-fix issue (swinging, too fast)
      "warning" — ROM / form nudge
      "ok"      — positive cue / no issue

    The UI layer maps severity → colour via ui.severity_color().
    """
    if trust is not None and not trust.coaching_allowed:
        return build_setup_msgs(qualities or [], cam_feedback or [], trust, lang)

    msgs      = []
    sides_ln  = [t(lang, "left"), t(lang, "right")]

    for i, (tracker, angle, swinging) in enumerate(zip(trackers, angles, swings)):
        side_en = _SIDES_EN[i] if i < 2 else "CENTER"
        side_ln = sides_ln[i]  if i < 2 else ""
        quality = qualities[i] if qualities is not None and i < len(qualities) else None

        profile_msg = _profile_feedback(tracker, angle, exercise, quality, lang)
        if profile_msg is not None:
            msgs.append(profile_msg)

        if profile_msg is None and swinging and (qualities is None or qualities[i] == "GOOD"):
            msgs.append((f"  {t(lang, 'swing_warn', side=side_ln)}", "error"))
            voice.say(f"Stop swinging your {side_en.lower()} side", 4.0)

        if angle is None:
            continue

        if profile_msg is None and not exercise.invert:
            if tracker.stage == "start" and angle > exercise.angle_down - 12:
                msgs.append((f"  {t(lang, 'extend_fully', side=side_ln)}", "warning"))
            elif tracker.stage == "end" and angle > exercise.angle_up + 15:
                msgs.append((f"  {t(lang, 'curl_fully', side=side_ln)}", "warning"))
        elif profile_msg is None:
            if tracker.stage == "start" and angle > exercise.angle_down + 15:
                msgs.append((f"  {t(lang, 'extend_fully', side=side_ln)}", "warning"))
            elif tracker.stage == "end" and angle < exercise.angle_up - 15:
                msgs.append((f"  {t(lang, 'press_up', side=side_ln)}", "warning"))

        if 0 < tracker.rep_elapsed < cfg.get("min_rep_time", 1.2):
            msgs.append((f"  {t(lang, 'slow_down', side=side_ln)}", "error"))
            voice.say("Slow down", 5.0)

    if not msgs:
        hints = []
        for i, tracker in enumerate(trackers):
            side_ln = sides_ln[i] if i < len(sides_ln) else ""
            profile_hint = _profile_hint(tracker, exercise, lang)
            if profile_hint:
                hints.append(profile_hint)
            elif tracker.stage == "end":
                hints.append(t(lang, "lower_slowly", side=side_ln))
            elif tracker.stage == "start":
                hints.append(t(lang, "curl_up", side=side_ln))
        if hints:
            msgs.append(("  " + "   ·   ".join(hints), "ok"))

    return msgs
