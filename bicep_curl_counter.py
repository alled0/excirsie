"""
Taharrak — AI Fitness Platform
Main entry point. Manages the state machine and camera loop.

States:
  EXERCISE_SELECT → WEIGHT_INPUT → CALIBRATION → COUNTDOWN
  → WORKOUT → REST → WORKOUT → ... → SUMMARY
  EXERCISE_SELECT → HISTORY → EXERCISE_SELECT
"""

import argparse
import csv
import json
import os
import time
import urllib.request
from collections import deque
from datetime import datetime

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from taharrak.exercises import EXERCISES, Exercise
from taharrak.tracker    import RepTracker, VoiceEngine
from taharrak.messages   import t
from taharrak.database   import (init_db, save_session, get_last_sessions,
                                  get_last_weight, check_overload_suggestion,
                                  get_personal_bests)
import taharrak.ui as ui

# ── Model ─────────────────────────────────────────────────────────────────────
MODEL_PATH = "pose_landmarker_lite.task"
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)

def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print("Downloading pose landmarker model (~6 MB)…")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Model ready.")


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path="config.json") -> dict:
    defaults = {
        "angle_down": 160, "angle_up": 45,
        "swing_threshold": 0.025, "swing_window": 15,
        "vis_good": 0.68, "vis_weak": 0.38,
        "rest_duration": 60, "countdown_secs": 3,
        "score_flash_duration": 2.5, "symmetry_warn_ratio": 0.15,
        "summary_auto_close": 12, "target_reps": 12,
        "ideal_rep_time": 2.5, "min_rep_time": 1.2,
        "mirror_mode": True, "voice_enabled": True, "voice_rate": 160,
        "confidence_smoother_window": 10, "fatigue_score_gap": 20,
        "overload_sessions_needed": 3, "overload_min_avg_score": 75,
        "overload_step_kg": 2.5, "weight_step_kg": 2.5,
        "weight_min_kg": 0.0, "weight_max_kg": 200.0,
        "db_path": "~/.taharrak/sessions.db",
        "arabic_font_path": "assets/NotoNaskhArabic-Regular.ttf",
        "warmup_mode": True,
    }
    if os.path.exists(path):
        with open(path) as f:
            defaults.update(json.load(f))
    return defaults


# ── Detection helpers ─────────────────────────────────────────────────────────

def det_quality_ex(lm, exercise: Exercise, cfg: dict) -> tuple:
    """Returns (left_quality, right_quality) for exercise joints."""
    VG, VW = cfg.get("vis_good", 0.68), cfg.get("vis_weak", 0.38)
    def q(indices):
        vis = [lm[i].visibility for i in indices]
        if all(v > VG for v in vis): return "GOOD"
        if all(v > VW for v in vis): return "WEAK"
        return "LOST"
    return q(exercise.joints_left), q(exercise.joints_right)


def lm_to_px(lm, w: int, h: int, mirror: bool) -> list:
    if mirror:
        return [(w - int(p.x * w), int(p.y * h)) for p in lm]
    return [(int(p.x * w), int(p.y * h)) for p in lm]


# ── Form feedback messages ────────────────────────────────────────────────────

def build_msgs(trackers: list, angles: list, swings: list,
               exercise: Exercise, voice: VoiceEngine,
               cfg: dict, lang: str) -> list:
    msgs = []
    sides_en = ["LEFT",  "RIGHT"]
    sides_ln = [t(lang, "left"), t(lang, "right")]

    for i, (tracker, angle, swinging) in enumerate(zip(trackers, angles, swings)):
        side_en = sides_en[i] if i < 2 else "CENTER"
        side_ln = sides_ln[i] if i < 2 else ""

        if swinging:
            msgs.append((f"  {t(lang, 'swing_warn', side=side_ln)}", ui.RED))
            voice.say(f"Stop swinging your {side_en.lower()} side", 4.0)

        if angle is None:
            continue

        if not exercise.invert:
            # curl / squat type
            if tracker.stage == "start" and angle > exercise.angle_down - 12:
                msgs.append((f"  {t(lang, 'extend_fully', side=side_ln)}", ui.ORANGE))
            elif tracker.stage == "end" and angle > exercise.angle_up + 15:
                msgs.append((f"  {t(lang, 'curl_fully', side=side_ln)}", ui.ORANGE))
        else:
            # press / raise / extension type
            if tracker.stage == "start" and angle > exercise.angle_down + 15:
                msgs.append((f"  {t(lang, 'extend_fully', side=side_ln)}", ui.ORANGE))
            elif tracker.stage == "end" and angle < exercise.angle_up - 15:
                msgs.append((f"  {t(lang, 'press_up', side=side_ln)}", ui.ORANGE))

        if 0 < tracker.rep_elapsed < cfg.get("min_rep_time", 1.2):
            msgs.append((f"  {t(lang, 'slow_down', side=side_ln)}", ui.RED))
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
            msgs.append(("  " + "   ·   ".join(hints), ui.GREEN))

    return msgs


# ── CSV export ────────────────────────────────────────────────────────────────

def save_csv(trackers: list):
    all_rows = []
    for tr in trackers:
        all_rows.extend(tr.all_rep_logs())
    if not all_rows:
        return
    all_rows.sort(key=lambda r: r["timestamp"])
    fname = f"workout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fname, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        w.writeheader()
        w.writerows(all_rows)
    print(f"Workout log saved → {fname}")


# ── Session save helper ───────────────────────────────────────────────────────

def persist_session(cfg: dict, trackers: list, exercise: Exercise,
                    weight_kg: float, set_count: int, session_start: float):
    all_scores = []
    all_reps   = 0
    all_logs   = []
    for tr in trackers:
        all_scores += tr.form_scores
        all_reps   += tr.total_reps
        all_logs   += tr.all_rep_logs()

    avg  = sum(all_scores) / len(all_scores) if all_scores else 0.0
    best = max(all_scores) if all_scores else 0

    session_data = {
        "created_at":    datetime.now().isoformat(),
        "exercise_key":  exercise.key,
        "exercise_name": exercise.name,
        "weight_kg":     weight_kg,
        "sets_done":     set_count,
        "total_reps":    all_reps,
        "avg_score":     round(avg, 1),
        "best_score":    best,
        "duration_secs": int(time.time() - session_start),
        "rating":        ui.rating(avg),
    }
    save_session(cfg, session_data, all_logs)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="Taharrak — AI Fitness Trainer")
    ap.add_argument("--camera",    type=int,  default=0)
    ap.add_argument("--reps",      type=int,  default=None)
    ap.add_argument("--no-voice",  action="store_true")
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--rest",      type=int,  default=None)
    ap.add_argument("--lang",      type=str,  default=None, choices=["en", "ar"])
    return ap.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    cfg  = load_config()

    if args.reps      is not None: cfg["target_reps"]   = args.reps
    if args.no_voice:               cfg["voice_enabled"] = False
    if args.no_mirror:              cfg["mirror_mode"]   = False
    if args.rest      is not None: cfg["rest_duration"]  = args.rest

    lang      = args.lang or cfg.get("default_language", "en")
    font_path = cfg.get("arabic_font_path", "")

    ensure_model()
    init_db(cfg)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {args.camera}.")

    # Request a larger capture resolution so the window has more pixels to work with
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Create a resizable, maximised window
    cv2.namedWindow("Taharrak — AI Fitness", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Taharrak — AI Fitness", 1280, 720)
    cv2.setWindowProperty("Taharrak — AI Fitness",
                          cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    fps   = cap.get(cv2.CAP_PROP_FPS) or 30
    voice = VoiceEngine(cfg["voice_enabled"], cfg.get("voice_rate", 160))

    base_opts = python.BaseOptions(model_asset_path=MODEL_PATH)
    options   = vision.PoseLandmarkerOptions(
        base_options=base_opts,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.48,
        min_pose_presence_confidence=0.48,
        min_tracking_confidence=0.48,
    )

    # ── State machine variables ───────────────────────────────────────
    state           = "EXERCISE_SELECT"
    exercise        = None
    trackers        = []       # list of RepTracker (1 or 2)
    weight_kg       = 0.0
    suggest_overload = False

    countdown_start = None
    rest_start      = None
    set_count       = 0
    set_history     = []
    summary_start   = None
    session_start   = None
    score_flash     = {}

    history_rows    = []
    history_scroll  = 0
    pb              = {}

    frame_idx = 0
    mirror    = cfg.get("mirror_mode", True)

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            h, w = frame.shape[:2]
            display = cv2.flip(frame, 1) if mirror else frame.copy()

            # Run MediaPipe on the original (non-flipped) frame
            mp_img = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            )
            ts     = int(frame_idx * 1000 / fps)
            result = landmarker.detect_for_video(mp_img, ts)
            frame_idx += 1

            # ── EXERCISE SELECT ───────────────────────────────────────
            if state == "EXERCISE_SELECT":
                ui.screen_exercise_select(display, lang, font_path)

            # ── WEIGHT INPUT ──────────────────────────────────────────
            elif state == "WEIGHT_INPUT":
                ui.screen_weight_input(display, exercise, weight_kg,
                                       lang, suggest_overload, cfg)

            # ── CALIBRATION ───────────────────────────────────────────
            elif state == "CALIBRATION":
                l_q = r_q = "LOST"
                can_start = False
                if result.pose_landmarks:
                    lm = result.pose_landmarks[0]
                    l_q, r_q = det_quality_ex(lm, exercise, cfg)
                    can_start = (l_q == "GOOD") and (r_q == "GOOD" or not exercise.bilateral)
                ui.screen_calibration(display, result, exercise,
                                      can_start, lang, cfg)

            # ── COUNTDOWN ─────────────────────────────────────────────
            elif state == "COUNTDOWN":
                if result.pose_landmarks:
                    lm    = result.pose_landmarks[0]
                    lm_px = lm_to_px(lm, w, h, mirror)
                    ui.draw_skeleton(display, lm_px)
                    a, b, c = exercise.joints_left
                    ui.draw_arm(display, lm_px, a, b, c, ui.L_COL)
                    a, b, c = exercise.joints_right
                    ui.draw_arm(display, lm_px, a, b, c, ui.R_COL)
                elapsed   = time.time() - countdown_start
                remaining = max(0, cfg["countdown_secs"] - int(elapsed))
                ui.screen_countdown(display, remaining, lang)
                if elapsed >= cfg["countdown_secs"]:
                    state = "WORKOUT"
                    voice.say(t(lang, "go"))

            # ── WORKOUT ───────────────────────────────────────────────
            elif state == "WORKOUT":
                angles  = [None] * len(trackers)
                swings  = [False] * len(trackers)
                quals   = ["LOST"] * len(trackers)
                warmup  = (set_count == 0)   # first set is warm-up

                if result.pose_landmarks:
                    lm    = result.pose_landmarks[0]
                    lm_px = lm_to_px(lm, w, h, mirror)
                    ui.draw_skeleton(display, lm_px)

                    l_q_raw, r_q_raw = det_quality_ex(lm, exercise, cfg)

                    if exercise.bilateral:
                        # Left tracker (index 0)
                        l_q = trackers[0].smooth_quality(l_q_raw)
                        quals[0] = l_q
                        if l_q != "LOST":
                            a, b, c = exercise.joints_left
                            swing_lm = lm[exercise.swing_joint_left]
                            ang, sw, done, sc = trackers[0].update(
                                lm[a], lm[b], lm[c], swing_lm, w, h, warmup)
                            angles[0] = ang
                            swings[0] = sw
                            ui.draw_arm(display, lm_px, a, b, c, ui.L_COL)
                            arc_pt = lm_px[exercise.joints_left[exercise.arc_joint_idx]]
                            ui.arc_gauge(display, arc_pt, ang)
                            if done and sc is not None:
                                score_flash["left"] = (sc, time.time() + cfg["score_flash_duration"])
                                voice.say(f"{t(lang, 'left')} {trackers[0].rep_count}. {sc}", 1.0)

                        # Right tracker (index 1)
                        r_q = trackers[1].smooth_quality(r_q_raw)
                        quals[1] = r_q
                        if r_q != "LOST":
                            a, b, c = exercise.joints_right
                            swing_lm = lm[exercise.swing_joint_right]
                            ang, sw, done, sc = trackers[1].update(
                                lm[a], lm[b], lm[c], swing_lm, w, h, warmup)
                            angles[1] = ang
                            swings[1] = sw
                            ui.draw_arm(display, lm_px, a, b, c, ui.R_COL)
                            arc_pt = lm_px[exercise.joints_right[exercise.arc_joint_idx]]
                            ui.arc_gauge(display, arc_pt, ang)
                            if done and sc is not None:
                                score_flash["right"] = (sc, time.time() + cfg["score_flash_duration"])
                                voice.say(f"{t(lang, 'right')} {trackers[1].rep_count}. {sc}", 1.0)
                    else:
                        # Single (right-side) tracker
                        r_q = trackers[0].smooth_quality(r_q_raw)
                        quals[0] = r_q
                        if r_q != "LOST":
                            a, b, c = exercise.joints_right
                            swing_lm = lm[exercise.swing_joint_right]
                            ang, sw, done, sc = trackers[0].update(
                                lm[a], lm[b], lm[c], swing_lm, w, h, warmup)
                            angles[0] = ang
                            swings[0] = sw
                            ui.draw_arm(display, lm_px, a, b, c, ui.R_COL)
                            arc_pt = lm_px[exercise.joints_right[exercise.arc_joint_idx]]
                            ui.arc_gauge(display, arc_pt, ang)
                            if done and sc is not None:
                                score_flash["center"] = (sc, time.time() + cfg["score_flash_duration"])
                                voice.say(f"Rep {trackers[0].rep_count}. Score {sc}", 1.0)

                msgs = build_msgs(trackers, angles, swings,
                                  exercise, voice, cfg, lang)

                if exercise.bilateral:
                    ui.screen_workout_bilateral(
                        display, trackers[0], trackers[1],
                        angles[0], angles[1], swings[0], swings[1],
                        quals[0], quals[1], set_count + 1,
                        score_flash, msgs, exercise, cfg, lang)
                else:
                    ui.screen_workout_single(
                        display, trackers[0], angles[0], swings[0],
                        quals[0], set_count + 1, score_flash,
                        msgs, exercise, cfg, lang)

            # ── REST ──────────────────────────────────────────────────
            elif state == "REST":
                elapsed   = time.time() - rest_start
                remaining = max(0, int(cfg["rest_duration"] - elapsed))
                last      = set_history[-1] if set_history else (0, 0, 0)
                l_r, r_r  = last[0], last[1]
                l_sc      = trackers[0].avg_score if trackers else 0.0
                r_sc      = trackers[1].avg_score if len(trackers) > 1 else 0.0
                ui.screen_rest(display, remaining, cfg["rest_duration"],
                               set_count, l_r, r_r, l_sc, r_sc,
                               lang, exercise.bilateral)
                if elapsed >= cfg["rest_duration"]:
                    _start_next_set(trackers, set_count)
                    state = "WORKOUT"
                    voice.say(t(lang, "go"))

            # ── SUMMARY ───────────────────────────────────────────────
            elif state == "SUMMARY":
                elapsed_d = time.time() - summary_start
                elapsed_s = time.time() - session_start
                ui.screen_summary(display, trackers, set_count,
                                  elapsed_s, elapsed_d,
                                  exercise, weight_kg, pb, cfg, lang)
                if elapsed_d >= cfg["summary_auto_close"]:
                    break

            # ── HISTORY ───────────────────────────────────────────────
            elif state == "HISTORY":
                ui.screen_history(display, history_rows, exercise,
                                  pb, history_scroll, lang)

            cv2.imshow("Taharrak — AI Fitness", display)

            # ── KEY HANDLING ──────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            # Global toggles
            if key == ord("l"):
                lang = "ar" if lang == "en" else "en"
            if key == ord("m"):
                mirror = not mirror
                cfg["mirror_mode"] = mirror

            if state == "EXERCISE_SELECT":
                if key in (ord("q"), 27):
                    break
                if key == ord("h"):
                    # Show history — need to pick an exercise first if none selected
                    if exercise is not None:
                        history_rows   = get_last_sessions(cfg, exercise.key)
                        pb             = get_personal_bests(cfg, exercise.key)
                        history_scroll = 0
                        state = "HISTORY"
                for ex_key, ex in EXERCISES.items():
                    if key == ord(ex_key):
                        exercise  = ex
                        weight_kg = get_last_weight(cfg, ex.key)
                        suggest_overload = check_overload_suggestion(
                            cfg, ex.key, weight_kg)
                        state = "WEIGHT_INPUT"
                        break

            elif state == "WEIGHT_INPUT":
                step = cfg.get("weight_step_kg", 2.5)
                if key in (82, ord("+")):    # UP arrow (82) or +
                    weight_kg = min(weight_kg + step, cfg.get("weight_max_kg", 200))
                elif key in (84, ord("-")):  # DOWN arrow (84) or -
                    weight_kg = max(weight_kg - step, cfg.get("weight_min_kg", 0))
                elif key in (ord(" "), 13):  # SPACE or ENTER
                    # Init trackers
                    if exercise.bilateral:
                        trackers = [
                            RepTracker("left",   exercise, cfg),
                            RepTracker("right",  exercise, cfg),
                        ]
                    else:
                        trackers = [RepTracker("center", exercise, cfg)]
                    set_count     = 0
                    set_history   = []
                    session_start = time.time()
                    pb            = get_personal_bests(cfg, exercise.key)
                    state = "CALIBRATION"
                elif key in (8, 27):         # BACKSPACE or ESC
                    state = "EXERCISE_SELECT"

            elif state == "CALIBRATION":
                if key == ord(" ") and can_start:
                    countdown_start = time.time()
                    state = "COUNTDOWN"
                elif key == 27:
                    state = "EXERCISE_SELECT"

            elif state == "WORKOUT":
                if key in (ord("q"), 27):
                    _close_set(trackers, set_count, set_history)
                    if any(tr.total_reps > 0 for tr in trackers):
                        set_count += 1
                    persist_session(cfg, trackers, exercise,
                                    weight_kg, set_count, session_start)
                    save_csv(trackers)
                    summary_start = time.time()
                    state = "SUMMARY"
                elif key == ord("s"):
                    set_count += 1
                    _close_set(trackers, set_count, set_history)
                    rest_start = time.time()
                    state = "REST"
                    voice.say(f"Set {set_count} done. Rest.")
                elif key == ord("r"):
                    for tr in trackers:
                        tr.reset_set()

            elif state == "REST":
                if key == ord(" "):
                    _start_next_set(trackers, set_count)
                    state = "WORKOUT"
                    voice.say(t(lang, "go"))
                elif key in (ord("q"), 27):
                    persist_session(cfg, trackers, exercise,
                                    weight_kg, set_count, session_start)
                    save_csv(trackers)
                    summary_start = time.time()
                    state = "SUMMARY"

            elif state == "SUMMARY":
                if key != 0xFF:
                    break

            elif state == "HISTORY":
                if key in (27, 8, ord("h")):
                    state = "EXERCISE_SELECT"
                elif key == 82:              # UP arrow
                    history_scroll = max(0, history_scroll - 1)
                elif key == 84:              # DOWN arrow
                    history_scroll = min(max(0, len(history_rows) - 1),
                                         history_scroll + 1)

    cap.release()
    cv2.destroyAllWindows()

    if trackers:
        total = sum(tr.total_reps for tr in trackers)
        all_s = []
        for tr in trackers:
            all_s += tr.form_scores
        avg = sum(all_s) / len(all_s) if all_s else 0.0
        print(f"\nSession finished.  {total} total reps  |  "
              f"Avg score: {avg:.0f}  |  Rating: {ui.rating(avg)}")


# ── Set management helpers ────────────────────────────────────────────────────

def _close_set(trackers: list, set_count: int, set_history: list):
    entry = tuple(tr.rep_count for tr in trackers)
    set_history.append(entry)
    for tr in trackers:
        tr.current_set = set_count + 1


def _start_next_set(trackers: list, set_count: int):
    for tr in trackers:
        tr.reset_set()
        tr.current_set = set_count + 1


if __name__ == "__main__":
    main()
