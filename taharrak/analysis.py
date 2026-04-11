"""
Pose analysis helpers for Taharrak.

  det_quality_ex        — per-arm detection quality (GOOD / WEAK / LOST)
  analyze_camera_position — actionable camera setup feedback
  build_msgs            — real-time form feedback strings for the workout HUD
"""

from taharrak.exercises.base import Exercise
from taharrak.messages import t


# ── Detection quality ─────────────────────────────────────────────────────────

def det_quality_ex(lm, exercise: Exercise, cfg: dict) -> tuple:
    """Returns (left_quality, right_quality) — each is 'GOOD', 'WEAK', or 'LOST'."""
    VG, VW = cfg.get("vis_good", 0.68), cfg.get("vis_weak", 0.38)

    def _q(indices):
        vis = [lm[i].visibility for i in indices]
        if all(v > VG for v in vis): return "GOOD"
        if all(v > VW for v in vis): return "WEAK"
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

    # -- Visibility: if key landmarks are mostly invisible, lighting is bad
    key_vis = [lm[i].visibility for i in (0, 11, 12, 23, 24)]
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
        hidden_l = [i for i in exercise.key_joints_left if lm[i].visibility < VG]
        if hidden_l:
            issues.append("joint_hidden")

    if exercise.key_joints_right:
        hidden_r = [i for i in exercise.key_joints_right if lm[i].visibility < VG]
        if hidden_r and "joint_hidden" not in issues:
            issues.append("joint_hidden")

    return issues


# ── Form feedback messages ────────────────────────────────────────────────────

_SIDES_EN = ["LEFT", "RIGHT"]


def build_msgs(trackers: list, angles: list, swings: list,
               exercise: Exercise, voice, cfg: dict, lang: str) -> list:
    """
    Build real-time form feedback message list for the workout HUD.
    Returns list of (text, colour) tuples.
    Late-import of ui colours to avoid circular imports.
    """
    from taharrak.ui import RED, ORANGE, GREEN  # noqa: PLC0415

    msgs      = []
    sides_ln  = [t(lang, "left"), t(lang, "right")]

    for i, (tracker, angle, swinging) in enumerate(zip(trackers, angles, swings)):
        side_en = _SIDES_EN[i] if i < 2 else "CENTER"
        side_ln = sides_ln[i]  if i < 2 else ""

        if swinging:
            msgs.append((f"  {t(lang, 'swing_warn', side=side_ln)}", RED))
            voice.say(f"Stop swinging your {side_en.lower()} side", 4.0)

        if angle is None:
            continue

        if not exercise.invert:
            if tracker.stage == "start" and angle > exercise.angle_down - 12:
                msgs.append((f"  {t(lang, 'extend_fully', side=side_ln)}", ORANGE))
            elif tracker.stage == "end" and angle > exercise.angle_up + 15:
                msgs.append((f"  {t(lang, 'curl_fully', side=side_ln)}", ORANGE))
        else:
            if tracker.stage == "start" and angle > exercise.angle_down + 15:
                msgs.append((f"  {t(lang, 'extend_fully', side=side_ln)}", ORANGE))
            elif tracker.stage == "end" and angle < exercise.angle_up - 15:
                msgs.append((f"  {t(lang, 'press_up', side=side_ln)}", ORANGE))

        if 0 < tracker.rep_elapsed < cfg.get("min_rep_time", 1.2):
            msgs.append((f"  {t(lang, 'slow_down', side=side_ln)}", RED))
            voice.say("Slow down", 5.0)

    if not msgs:
        hints = []
        for i, tracker in enumerate(trackers):
            side_ln = sides_ln[i] if i < len(sides_ln) else ""
            if tracker.stage == "end":
                hints.append(t(lang, "lower_slowly", side=side_ln))
            elif tracker.stage == "start":
                hints.append(t(lang, "curl_up", side=side_ln))
        if hints:
            msgs.append(("  " + "   ·   ".join(hints), GREEN))

    return msgs
