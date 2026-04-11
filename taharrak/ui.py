"""
All screen renderers for Taharrak.
Every function draws onto an OpenCV BGR frame in-place and returns nothing.
"""

import time
import numpy as np
import cv2

from taharrak.exercises import Exercise, EXERCISES
from taharrak.messages import t, put_text

# ── Colours (BGR) ─────────────────────────────────────────────────────────────
WHITE  = (255, 255, 255)
YELLOW = (  0, 255, 255)
GREEN  = (  0, 220,  70)
ORANGE = (  0, 155, 255)
RED    = ( 40,  40, 220)
CYAN   = (255, 220,   0)
DARK   = ( 16,  16,  16)
GRAY   = (115, 115, 115)
L_COL  = (  0, 200, 200)
R_COL  = (255, 200,   0)

# Skeleton connections drawn on every screen that shows the body
SKELETON = [(11,12),(11,13),(13,15),(12,14),(14,16)]


# ── Primitives ────────────────────────────────────────────────────────────────

def trect(img, x1, y1, x2, y2, color=DARK, alpha=0.72, border=True):
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
    if x1 >= x2 or y1 >= y2:
        return
    roi = img[y1:y2, x1:x2]
    bg  = np.full_like(roi, color, dtype=np.uint8)
    cv2.addWeighted(bg, alpha, roi, 1 - alpha, 0, roi)
    img[y1:y2, x1:x2] = roi
    if border:
        cv2.rectangle(img, (x1, y1), (x2, y2), (75, 75, 75), 1)


def put(img, text, pos, scale=0.8, color=WHITE, thickness=2):
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_DUPLEX,
                scale, color, thickness, cv2.LINE_AA)


def center_put(img, text, y, scale=1.0, color=WHITE, thickness=2):
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, thickness)
    put(img, text, ((img.shape[1] - tw) // 2, y), scale, color, thickness)


def hline(img, y, width=620):
    w = img.shape[1]
    cv2.line(img, (w//2 - width//2, y), (w//2 + width//2, y), (55, 55, 55), 1)


def vis_bar(img, x, y, width, quality):
    fill = {"GOOD": width, "WEAK": width * 2 // 3, "LOST": width // 6}[quality]
    col  = q_color(quality)
    cv2.rectangle(img, (x, y), (x + width, y + 6), (50, 50, 50), -1)
    if fill > 0:
        cv2.rectangle(img, (x, y), (x + fill, y + 6), col, -1)


def tempo_bar(img, x, y, width, elapsed: float, cfg: dict):
    ideal = cfg.get("ideal_rep_time", 2.5)
    min_t = cfg.get("min_rep_time",   1.2)
    frac  = min(elapsed / ideal, 1.0)
    fill  = int(width * frac)
    col   = RED if elapsed < min_t else (ORANGE if elapsed < ideal * 0.75 else GREEN)
    cv2.rectangle(img, (x, y), (x + width, y + 8), (45, 45, 45), -1)
    if fill > 0:
        cv2.rectangle(img, (x, y), (x + fill, y + 8), col, -1)
    cv2.rectangle(img, (x, y), (x + width, y + 8), (80, 80, 80), 1)


def arc_gauge(img, pt, angle: float):
    cx, cy = int(pt[0]), int(pt[1])
    r = 36
    cv2.ellipse(img, (cx, cy), (r, r), -90, 0, 180, (60, 60, 60), 3, cv2.LINE_AA)
    frac = 1.0 - np.clip(angle / 180.0, 0, 1)
    end  = int(180 * frac)
    hue  = int(60 * frac)
    col  = tuple(int(c) for c in cv2.cvtColor(
        np.uint8([[[hue, 255, 215]]]), cv2.COLOR_HSV2BGR)[0, 0])
    if end > 0:
        cv2.ellipse(img, (cx, cy), (r, r), -90, 0, end, col, 3, cv2.LINE_AA)
    put(img, f"{int(angle)}", (cx + r + 6, cy + 7), 0.60, YELLOW, 2)


def q_color(q: str):
    return {"GOOD": GREEN, "WEAK": ORANGE, "LOST": RED}.get(q, GRAY)


def severity_color(severity: str) -> tuple:
    """Map a semantic severity key from build_msgs to a BGR colour.

    "error"   → RED    (must-fix issue)
    "warning" → ORANGE (form / ROM nudge)
    "ok"      → GREEN  (positive cue)
    """
    return {"error": RED, "warning": ORANGE, "ok": GREEN}.get(severity, WHITE)


def rating_color(r: str):
    return {"S": YELLOW, "A": GREEN, "B": ORANGE, "C": RED}.get(r, WHITE)


def rating(score: float) -> str:
    if score >= 90: return "S"
    if score >= 75: return "A"
    if score >= 60: return "B"
    return "C"


def draw_skeleton(img, lm_px):
    for i, j in SKELETON:
        if i < len(lm_px) and j < len(lm_px):
            cv2.line(img, lm_px[i], lm_px[j], (105, 105, 105), 1, cv2.LINE_AA)


def draw_arm(img, lm_px, idx_a, idx_b, idx_c, color):
    a, b, c = lm_px[idx_a], lm_px[idx_b], lm_px[idx_c]
    cv2.line(img, a, b, color, 3, cv2.LINE_AA)
    cv2.line(img, b, c, color, 3, cv2.LINE_AA)
    for pt, jcol in zip([a, b, c], [(255,100,20),(20,215,255),(60,255,80)]):
        cv2.circle(img, pt, 10, jcol,  -1, cv2.LINE_AA)
        cv2.circle(img, pt, 12, WHITE,  2, cv2.LINE_AA)


def lm_to_px(lm, w: int, h: int, mirror: bool) -> list:
    if mirror:
        return [(w - int(p.x * w), int(p.y * h)) for p in lm]
    return [(int(p.x * w), int(p.y * h)) for p in lm]


# ── Screen: EXERCISE SELECT ───────────────────────────────────────────────────

def screen_exercise_select(frame, lang: str, font_path: str):
    h, w = frame.shape[:2]
    frame[:] = (10, 10, 25)

    # Header
    center_put(frame, t(lang, "app_title"), 58, 1.1, WHITE, 2)
    hline(frame, 75)

    center_put(frame, t(lang, "select_exercise"), 115, 0.95, GRAY, 1)

    # Exercise cards
    ex_list = list(EXERCISES.values())
    card_h  = 72
    start_y = 140
    card_w  = min(w - 80, 600)
    cx      = w // 2

    for i, ex in enumerate(ex_list):
        y1 = start_y + i * (card_h + 12)
        y2 = y1 + card_h
        trect(frame, cx - card_w//2, y1, cx + card_w//2, y2, (18, 18, 38))
        # Key badge
        cv2.rectangle(frame, (cx - card_w//2 + 10, y1 + 14),
                      (cx - card_w//2 + 46, y2 - 14), (50, 50, 80), -1)
        put(frame, ex.key, (cx - card_w//2 + 18, y2 - 18), 1.0, YELLOW, 2)
        # Name
        name = ex.name_ar if lang == "ar" else ex.name
        put(frame, name, (cx - card_w//2 + 60, y1 + card_h//2 + 10), 0.88, WHITE, 2)

    # Bottom hints
    hline(frame, h - 52)
    put(frame, t(lang, "controls_select"), (20, h - 18), 0.52, GRAY, 1)
    put(frame, t(lang, "lang_toggle"),     (w - 180, h - 18), 0.52, CYAN, 1)


# ── Screen: WEIGHT INPUT ──────────────────────────────────────────────────────

def screen_weight_input(frame, exercise: Exercise, weight_kg: float,
                        lang: str, suggest: bool, cfg: dict):
    h, w = frame.shape[:2]
    frame[:] = (10, 10, 25)

    ex_name = exercise.name_ar if lang == "ar" else exercise.name
    center_put(frame, ex_name,                   70,  1.0, YELLOW, 2)
    center_put(frame, t(lang, "weight_input"),   115, 0.88, GRAY,  1)
    hline(frame, 130)

    # Big weight display
    label = f"{weight_kg:.1f} kg"
    (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 3.5, 6)
    put(frame, label, (w//2 - tw//2, h//2 + 30), 3.5, WHITE, 6)

    # Arrows
    put(frame, "▲", (w//2 - 30, h//2 - 65),  1.5, GREEN,  2)
    put(frame, "▼", (w//2 - 30, h//2 + 95),  1.5, ORANGE, 2)

    # Suggest increase badge
    if suggest:
        step  = cfg.get("overload_step_kg", 2.5)
        badge = t(lang, "suggest_increase", n=step)
        trect(frame, w//2 - 220, h//2 + 110, w//2 + 220, h//2 + 155, (0, 55, 0))
        center_put(frame, badge, h//2 + 142, 0.82, GREEN, 1)

    hline(frame, h - 60)
    center_put(frame, t(lang, "weight_hint"), h - 32, 0.58, GRAY, 1)


# ── Screen: CALIBRATION ───────────────────────────────────────────────────────

def screen_calibration(frame, result, exercise: Exercise,
                       can_start: bool, cam_feedback: list,
                       lang: str, cfg: dict):
    h, w = frame.shape[:2]

    trect(frame, 0, 0, w, 105, (10, 10, 30), 0.82, False)
    center_put(frame, t(lang, "app_title"), 44, 0.95, WHITE, 2)
    center_put(frame, t(lang, "calibration_hint"), 88, 0.56, GRAY, 1)

    l_q = r_q = "LOST"
    if result and result.pose_landmarks:
        lm    = result.pose_landmarks[0]
        lm_px = lm_to_px(lm, w, h, cfg.get("mirror_mode", True))
        draw_skeleton(frame, lm_px)

        l_vis = [lm[i].visibility for i in exercise.joints_left]
        r_vis = [lm[i].visibility for i in exercise.joints_right]
        VG, VW = cfg.get("vis_good", 0.68), cfg.get("vis_weak", 0.38)
        l_q   = "GOOD" if all(v > VG for v in l_vis) else ("WEAK" if all(v > VW for v in l_vis) else "LOST")
        r_q   = "GOOD" if all(v > VG for v in r_vis) else ("WEAK" if all(v > VW for v in r_vis) else "LOST")

        if l_q != "LOST":
            a, b, c = exercise.joints_left
            draw_arm(frame, lm_px, a, b, c, L_COL)
        if r_q != "LOST":
            a, b, c = exercise.joints_right
            draw_arm(frame, lm_px, a, b, c, R_COL)

        # ── Camera position feedback panel ──────────────────────────────
        fb_y = h // 2 - 20
        if cam_feedback:
            panel_h = 42 + len(cam_feedback) * 32
            trect(frame, w//2 - 295, fb_y, w//2 + 295, fb_y + panel_h, (28, 12, 5), 0.88)
            put(frame, t(lang, "cam_feedback_title"),
                (w//2 - 278, fb_y + 27), 0.68, ORANGE, 1)
            for i, key in enumerate(cam_feedback):
                put(frame, f"  \u25cf  {t(lang, key)}",
                    (w//2 - 270, fb_y + 52 + i * 32), 0.70, YELLOW, 1)
        elif l_q == "LOST" or r_q == "LOST":
            trect(frame, w//2 - 270, fb_y, w//2 + 270, fb_y + 48, (0, 0, 55))
            center_put(frame, t(lang, "improve_hint"), fb_y + 34, 0.65, ORANGE, 1)
        else:
            trect(frame, w//2 - 185, fb_y, w//2 + 185, fb_y + 44, (0, 42, 0), 0.85)
            center_put(frame, t(lang, "cam_good"), fb_y + 30, 0.80, GREEN, 2)

    else:
        trect(frame, w//2 - 240, h//2 - 35, w//2 + 240, h//2 + 42, (0, 0, 70))
        center_put(frame, t(lang, "no_person"), h//2 + 12, 0.85, RED, 2)

    PW = 215
    # Left panel
    trect(frame, 18, 115, 18 + PW, 215)
    put(frame, t(lang, "left"),  (30, 148), 0.72, GRAY, 1)
    put(frame, l_q,              (30, 190), 0.92, q_color(l_q), 2)
    vis_bar(frame, 30, 200, PW - 24, l_q)
    # Right panel
    trect(frame, w - 18 - PW, 115, w - 18, 215)
    put(frame, t(lang, "right"), (w - 18 - PW + 12, 148), 0.72, GRAY, 1)
    put(frame, r_q,              (w - 18 - PW + 12, 190), 0.92, q_color(r_q), 2)
    vis_bar(frame, w - 18 - PW + 12, 200, PW - 24, r_q)

    if can_start:
        trect(frame, w//2 - 185, h - 88, w//2 + 185, h - 18, (0, 50, 0))
        center_put(frame, t(lang, "space_start"), h - 44, 0.92, GREEN, 2)
    else:
        trect(frame, w//2 - 255, h - 88, w//2 + 255, h - 18, (22, 22, 22))
        center_put(frame, t(lang, "need_good"), h - 44, 0.70, GRAY, 1)


# ── Screen: COUNTDOWN ─────────────────────────────────────────────────────────

def screen_countdown(frame, remaining: int, lang: str):
    overlay = np.zeros_like(frame)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    center_put(frame, t(lang, "get_ready"), frame.shape[0]//2 - 85, 1.5, WHITE, 3)
    center_put(frame, str(remaining),       frame.shape[0]//2 + 60, 4.5, YELLOW, 9)


# ── Screen: WORKOUT (bilateral) ───────────────────────────────────────────────

def screen_workout_bilateral(frame, left, right,
                              l_angle, r_angle, l_swing, r_swing,
                              l_quality, r_quality, set_num: int,
                              score_flash: dict, msgs: list,
                              exercise: Exercise, cfg: dict, lang: str,
                              angle_visible: tuple[bool, bool] = (True, True),
                              tempo_visible: tuple[bool, bool] = (True, True),
                              comparison_allowed: bool = True):
    h, w   = frame.shape[:2]
    now    = time.time()
    target = cfg.get("target_reps", 12)
    PW     = 188

    def _arm_panel(tracker, angle, quality, px, is_warmup, arm_col,
                   show_angle: bool, show_tempo: bool):
        trect(frame, px, 10, px + PW, 335)
        side_label = t(lang, "left") if tracker.side == "left" else t(lang, "right")
        put(frame, side_label, (px + 12, 42), 0.70, GRAY, 1)
        if is_warmup:
            put(frame, t(lang, "warmup_badge"), (px + 12, 65), 0.55, YELLOW, 1)

        rep_col = GREEN if tracker.rep_count >= target else (arm_col if tracker.rep_count > 0 else WHITE)
        put(frame, str(tracker.rep_count), (px + 12, 132), 3.1, rep_col, 4)
        put(frame, t(lang, "target_label", n=target), (px + 82, 132), 1.0, GRAY, 2)

        stage_txt = (exercise.stage_labels[1] if tracker.stage == "end"
                     else exercise.stage_labels[0] if tracker.stage == "start"
                     else "READY")
        stage_col = GREEN if tracker.stage == "end" else (ORANGE if tracker.stage == "start" else WHITE)
        put(frame, stage_txt, (px + 12, 162), 0.80, stage_col, 2)

        put(frame, f"{t(lang, 'det_label')} {quality}",
            (px + 12, 192), 0.56, q_color(quality), 1)
        vis_bar(frame, px + 12, 200, PW - 24, quality)

        if tracker.form_scores:
            sc = tracker.avg_score
            sc_col = GREEN if sc >= 80 else (ORANGE if sc >= 60 else RED)
            put(frame, f"{t(lang, 'avg_label')} {sc:.0f}%", (px + 12, 225), 0.65, sc_col, 1)

        if show_angle and angle is not None:
            put(frame, f"{int(angle):>3}\u00b0", (px + 12, 258), 0.80, YELLOW, 2)
        if show_tempo and 0 < tracker.rep_elapsed:
            put(frame, t(lang, "tempo_label"),   (px + 12, 282), 0.50, GRAY, 1)
            tempo_bar(frame, px + 12, 288, PW - 24, tracker.rep_elapsed, cfg)
            if tracker.rep_elapsed < cfg.get("min_rep_time", 1.2):
                put(frame, t(lang, "too_fast"), (px + 12, 315), 0.58, RED, 1)

        if tracker.is_fatigued():
            put(frame, t(lang, "fatigue_warning")[:28], (px + 12, 335), 0.48, ORANGE, 1)

    warmup = (set_num == 1)
    _arm_panel(left,  l_angle, l_quality, 10,          warmup, L_COL,
               angle_visible[0], tempo_visible[0])
    _arm_panel(right, r_angle, r_quality, w - 10 - PW, warmup, R_COL,
               angle_visible[1], tempo_visible[1])

    # Top centre: set badge
    trect(frame, w//2 - 82, 10, w//2 + 82, 52)
    center_put(frame, t(lang, "set_label", n=set_num), 42, 0.90, WHITE, 2)

    # Symmetry scores
    if comparison_allowed and left.form_scores and right.form_scores:
        trect(frame, w//2 - 165, 60, w//2 + 165, 100)
        put(frame, f"L {left.avg_score:.0f}%",  (w//2 - 152, 90), 0.72, L_COL, 1)
        put(frame, "|",                          (w//2 -  8,  90), 0.72, GRAY,  1)
        put(frame, f"R {right.avg_score:.0f}%", (w//2 + 16,  90), 0.72, R_COL, 1)

    # Swing border flash
    if l_swing:
        cv2.rectangle(frame, (3, 3), (w//2, h - 3), (40, 40, 220), 4)
    if r_swing:
        cv2.rectangle(frame, (w//2, 3), (w - 3, h - 3), (40, 40, 220), 4)

    # Target reached banner
    if left.rep_count >= target and right.rep_count >= target:
        trect(frame, w//2 - 225, h//2 - 32, w//2 + 225, h//2 + 34, (0, 60, 0), 0.88)
        center_put(frame, t(lang, "set_done_banner", n=set_num), h//2 + 12, 0.80, GREEN, 2)

    # Symmetry rep-count warning
    mr = max(left.rep_count, right.rep_count, 1)
    if comparison_allowed and abs(left.rep_count - right.rep_count) / mr > cfg.get("symmetry_warn_ratio", 0.15) and mr > 2:
        lag = t(lang, "left") if left.rep_count < right.rep_count else t(lang, "right")
        trect(frame, w//2 - 265, h - 108, w//2 + 265, h - 70, (0, 0, 60))
        center_put(frame, t(lang, "sym_lag", side=lag), h - 76, 0.72, ORANGE, 1)

    _score_flashes(frame, score_flash, now, h, w)
    _feedback_strip(frame, msgs, h)
    put(frame, t(lang, "controls_workout"), (12, h - 8), 0.46, (80, 80, 80), 1)


# ── Screen: WORKOUT (non-bilateral / squat) ───────────────────────────────────

def screen_workout_single(frame, tracker, angle, swinging,
                          quality, set_num: int, score_flash: dict,
                          msgs: list, exercise: Exercise, cfg: dict, lang: str,
                          angle_visible: bool = True,
                          tempo_visible: bool = True):
    h, w   = frame.shape[:2]
    now    = time.time()
    target = cfg.get("target_reps", 12)
    warmup = (set_num == 1)
    PW     = 480
    px     = w//2 - PW//2

    trect(frame, px, 115, px + PW, 375)

    put(frame, exercise.name if lang == "en" else exercise.name_ar,
        (px + 14, 148), 0.78, GRAY, 1)
    if warmup:
        put(frame, t(lang, "warmup_badge"), (px + PW - 120, 148), 0.58, YELLOW, 1)

    rep_col = GREEN if tracker.rep_count >= target else (CYAN if tracker.rep_count > 0 else WHITE)
    put(frame, str(tracker.rep_count), (px + 14, 240), 3.2, rep_col, 4)
    put(frame, t(lang, "target_label", n=target), (px + 100, 240), 1.1, GRAY, 2)

    stage_txt = (exercise.stage_labels[1] if tracker.stage == "end"
                 else exercise.stage_labels[0] if tracker.stage == "start"
                 else "READY")
    stage_col = GREEN if tracker.stage == "end" else (ORANGE if tracker.stage == "start" else WHITE)
    put(frame, stage_txt, (px + 14, 270), 0.85, stage_col, 2)

    put(frame, f"{t(lang, 'det_label')} {quality}", (px + 14, 300), 0.60, q_color(quality), 1)
    vis_bar(frame, px + 14, 308, PW - 28, quality)

    if tracker.form_scores:
        sc = tracker.avg_score
        sc_col = GREEN if sc >= 80 else (ORANGE if sc >= 60 else RED)
        put(frame, f"{t(lang, 'avg_label')} {sc:.0f}%", (px + 14, 335), 0.68, sc_col, 1)

    if angle_visible and angle is not None:
        put(frame, f"{int(angle):>3}\u00b0", (px + 14, 362), 0.82, YELLOW, 2)
    if tempo_visible and angle is not None and 0 < tracker.rep_elapsed:
        put(frame, t(lang, "tempo_label"),   (px + 120, 335), 0.52, GRAY, 1)
        tempo_bar(frame, px + 120, 342, PW - 140, tracker.rep_elapsed, cfg)
        if tracker.rep_elapsed < cfg.get("min_rep_time", 1.2):
            put(frame, t(lang, "too_fast"), (px + 120, 365), 0.60, RED, 1)

    if tracker.is_fatigued():
        trect(frame, w//2 - 255, h//2 - 28, w//2 + 255, h//2 + 26, (0, 0, 55))
        center_put(frame, t(lang, "fatigue_warning"), h//2 + 10, 0.78, ORANGE, 2)

    trect(frame, w//2 - 82, 10, w//2 + 82, 52)
    center_put(frame, t(lang, "set_label", n=set_num), 42, 0.90, WHITE, 2)

    if tracker.rep_count >= target:
        trect(frame, w//2 - 225, h//2 + 50, w//2 + 225, h//2 + 105, (0, 60, 0), 0.88)
        center_put(frame, t(lang, "set_done_banner", n=set_num), h//2 + 90, 0.80, GREEN, 2)

    if swinging:
        cv2.rectangle(frame, (3, 3), (w - 3, h - 3), (40, 40, 220), 4)

    _score_flashes(frame, score_flash, now, h, w, bilateral=False)
    _feedback_strip(frame, msgs, h)
    put(frame, t(lang, "controls_workout"), (12, h - 8), 0.46, (80, 80, 80), 1)


# ── Screen: REST ──────────────────────────────────────────────────────────────

def screen_rest(frame, remaining: int, total_secs: int, set_num: int,
                l_reps: int, r_reps: int, l_score: float, r_score: float,
                lang: str, bilateral: bool):
    h, w = frame.shape[:2]
    overlay = np.full_like(frame, (8, 8, 24))
    cv2.addWeighted(overlay, 0.84, frame, 0.16, 0, frame)

    center_put(frame, t(lang, "set_rest_title", n=set_num), h//2 - 150, 1.3, GREEN, 3)

    if bilateral:
        info = f"L: {l_reps} reps  {l_score:.0f}%     R: {r_reps} reps  {r_score:.0f}%"
    else:
        info = f"{l_reps} reps  {l_score:.0f}% avg"
    center_put(frame, info, h//2 - 88, 0.80, WHITE, 1)

    center_put(frame, t(lang, "rest_title"), h//2 - 12, 0.95, GRAY, 2)
    center_put(frame, str(remaining), h//2 + 90, 3.8, YELLOW, 7)

    # Progress bar
    elapsed = total_secs - remaining
    bw = int(w * (elapsed / total_secs)) if total_secs > 0 else 0
    cv2.rectangle(frame, (0, h - 18), (bw, h - 4), (0, 80, 40), -1)
    cv2.rectangle(frame, (0, h - 18), (w,  h - 4), (40, 40, 40), 1)
    center_put(frame, t(lang, "space_skip"), h - 26, 0.62, GRAY, 1)


# ── Screen: SUMMARY ───────────────────────────────────────────────────────────

def screen_summary(frame, trackers: list, set_count: int,
                   elapsed_session: float, elapsed_display: float,
                   exercise: Exercise, weight_kg: float,
                   pb: dict, cfg: dict, lang: str):
    h, w = frame.shape[:2]
    frame[:] = (8, 8, 22)

    center_put(frame, t(lang, "summary_title"), 52, 1.0, WHITE, 2)
    hline(frame, 70)

    all_logs   = []
    total_reps = 0
    for tr in trackers:
        all_logs   += tr.rep_log
        total_reps += tr.total_reps

    all_scores = []
    for tr in trackers:
        all_scores += tr.form_scores

    avg  = sum(all_scores) / len(all_scores) if all_scores else 0.0
    best = max(all_scores)                   if all_scores else 0
    r    = rating(avg)
    rc   = rating_color(r)

    # Rep summary
    if len(trackers) == 2:
        center_put(frame,
            f"Left: {trackers[0].total_reps} reps     Right: {trackers[1].total_reps} reps",
            110, 0.88, WHITE, 2)
    else:
        center_put(frame, f"{total_reps} total reps", 110, 0.88, WHITE, 2)

    center_put(frame, t(lang, "sets_label", n=set_count), 148, 0.72, GRAY, 1)
    mins = int(elapsed_session // 60)
    secs = int(elapsed_session % 60)
    center_put(frame, f"Duration: {mins}m {secs}s     Weight: {weight_kg:.1f} kg",
               182, 0.68, GRAY, 1)
    hline(frame, 200)

    center_put(frame, t(lang, "form_section"), 232, 0.78, GRAY, 1)
    if len(trackers) == 2:
        center_put(frame,
            f"L avg {trackers[0].avg_score:.0f}%   |   R avg {trackers[1].avg_score:.0f}%",
            268, 0.85, WHITE, 2)
    center_put(frame, t(lang, "session_avg", avg=f"{avg:.0f}", best=best), 302, 0.75, YELLOW, 1)

    # Personal best badge
    if avg > pb.get("best_avg_score", 0):
        trect(frame, w//2 - 200, 310, w//2 + 200, 342, (0, 55, 0))
        center_put(frame, f"New {t(lang, 'pb_label')}! {avg:.0f}% avg", 333, 0.68, GREEN, 1)
    hline(frame, 350)

    if len(trackers) == 2:
        center_put(frame, t(lang, "sym_section"), 382, 0.78, GRAY, 1)
        l_s, r_s = trackers[0].avg_score, trackers[1].avg_score
        diff = abs(l_s - r_s)
        sym_thr = cfg.get("symmetry_warn_ratio", 0.15) * 100
        if l_s > 0 and r_s > 0:
            if diff > sym_thr:
                weaker = t(lang, "left") if l_s < r_s else t(lang, "right")
                center_put(frame, t(lang, "sym_weak", side=weaker, diff=f"{diff:.0f}"),
                           418, 0.78, ORANGE, 2)
            else:
                center_put(frame, t(lang, "sym_good"), 418, 0.78, GREEN, 1)
        hline(frame, 438)

    center_put(frame, t(lang, "rating_section"), 472, 0.85, GRAY, 1)
    center_put(frame, r, 556, 2.8, rc, 6)
    center_put(frame, t(lang, f"rating_{r}"), h - 62, 0.72, rc, 1)

    # Auto-close progress bar
    close_secs = cfg.get("summary_auto_close", 12)
    progress   = min(elapsed_display / close_secs, 1.0)
    bw         = int(w * progress)
    cv2.rectangle(frame, (0, h - 14), (bw, h), (45, 45, 75), -1)
    remaining  = max(0, close_secs - elapsed_display)
    center_put(frame, t(lang, "closing", n=f"{remaining:.0f}"), h - 20, 0.48, GRAY, 1)


# ── Screen: HISTORY ───────────────────────────────────────────────────────────

def screen_history(frame, rows: list, exercise: Exercise, pb: dict,
                   scroll: int, lang: str):
    h, w = frame.shape[:2]
    frame[:] = (8, 8, 22)

    ex_name = exercise.name_ar if lang == "ar" else exercise.name
    center_put(frame, f"{t(lang, 'history_title')} — {ex_name}", 50, 0.95, WHITE, 2)
    hline(frame, 65)

    # Personal best strip
    trect(frame, w//2 - 300, 72, w//2 + 300, 110, (0, 38, 0))
    pb_txt = (f"{t(lang, 'pb_label')}: "
              f"{pb['best_avg_score']:.0f}% avg  |  "
              f"{pb['best_rep_score']}/100 best rep  |  "
              f"{pb['best_reps']} reps")
    center_put(frame, pb_txt, 100, 0.65, GREEN, 1)

    if not rows:
        center_put(frame, t(lang, "history_empty"), h//2, 0.82, GRAY, 1)
    else:
        # Header row
        put(frame, t(lang, "history_header"), (30, 135), 0.55, GRAY, 1)
        hline(frame, 142)

        row_h   = 36
        visible = (h - 180) // row_h
        shown   = rows[scroll: scroll + visible]

        for i, row in enumerate(shown):
            y    = 148 + i * row_h
            date = row["created_at"][:16].replace("T", " ")
            r_c  = rating_color(row.get("rating", "C"))
            line = (f"  {date:<18} {row['total_reps']:>4}   {row['sets_done']:>3}   "
                    f"{row['avg_score']:>5.1f}  {row['best_score']:>4}   "
                    f" {row.get('rating','C')}     {row['weight_kg']:.1f}")
            col  = WHITE if i % 2 == 0 else (200, 200, 200)
            put(frame, line, (30, y + 24), 0.55, col, 1)
            # Rating in colour
            rx = 30 + int(cv2.getTextSize(f"  {date:<18} {row['total_reps']:>4}   "
                          f"{row['sets_done']:>3}   {row['avg_score']:>5.1f}  "
                          f"{row['best_score']:>4}    ",
                          cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)[0][0])
            put(frame, row.get("rating", "C"), (rx, y + 24), 0.55, r_c, 1)

        if scroll > 0:
            center_put(frame, "▲  scroll up", 158, 0.50, GRAY, 1)
        if scroll + visible < len(rows):
            center_put(frame, "▼  scroll down", h - 35, 0.50, GRAY, 1)

    hline(frame, h - 50)
    center_put(frame, t(lang, "history_hint"), h - 22, 0.58, GRAY, 1)


# ── Shared HUD helpers ────────────────────────────────────────────────────────

def _score_flashes(frame, score_flash: dict, now: float, h: int, w: int,
                   bilateral: bool = True):
    expired = []
    for side, (sc, expiry) in score_flash.items():
        if now < expiry:
            if bilateral:
                x_c = w // 4 if side in ("left", "center") else 3 * w // 4
            else:
                x_c = w // 2
            sc_c = GREEN if sc >= 80 else (ORANGE if sc >= 60 else RED)
            label = f"{sc}/100"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 1.3, 3)
            trect(frame, x_c - tw//2 - 14, h//2 - th - 22,
                  x_c + tw//2 + 14, h//2 + 16, (18, 18, 18), 0.88)
            put(frame, label, (x_c - tw//2, h//2), 1.3, sc_c, 3)
        else:
            expired.append(side)
    for s in expired:
        del score_flash[s]


def _feedback_strip(frame, msgs: list, h: int):
    if not msgs:
        return
    ph = 46 * len(msgs) + 16
    trect(frame, 0, h - ph, frame.shape[1], h, (8, 8, 35))
    for i, (txt, severity) in enumerate(msgs):
        put(frame, txt, (12, h - ph + 36 + i * 46), 0.80, severity_color(severity), 2)


def draw_live_diagnostics(frame, diag: dict, trust) -> None:
    if not diag:
        return
    h, w = frame.shape[:2]
    panel_w = 280
    trect(frame, w - panel_w - 12, 12, w - 12, 164, (6, 6, 18), 0.88)
    rows = [
        f"FPS {diag.get('fps', 0):>5.1f}",
        f"dt  {diag.get('dt_ms', 0):>5.1f} ms",
        f"jit {diag.get('jitter_ms', 0):>5.1f} ms",
        f"Q   {' / '.join(diag.get('qualities', ()))}",
        f"weak {diag.get('weak_frac', 0):.2f}  lost {diag.get('lost_frac', 0):.2f}",
        f"recovery {diag.get('recovery_frac', 0):.2f}",
        f"trust r/c/h {int(trust.render_allowed)}/{int(trust.counting_allowed)}/{int(trust.coaching_allowed)}",
    ]
    for i, text in enumerate(rows):
        put(frame, text, (w - panel_w, 38 + i * 20), 0.54, WHITE, 1)
