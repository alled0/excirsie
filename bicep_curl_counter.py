"""
Taharrak — AI Fitness Platform
Main entry point.  Owns only the camera loop and state machine;
all other logic lives in the taharrak/ package.

States
──────
  EXERCISE_SELECT → WEIGHT_INPUT → CALIBRATION → COUNTDOWN
  → WORKOUT → REST → WORKOUT → … → SUMMARY
  EXERCISE_SELECT → HISTORY → EXERCISE_SELECT
"""

import argparse
import json
import os
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from taharrak.exercises  import EXERCISES
from taharrak.tracker    import RepTracker, VoiceEngine, OneEuroLandmarkSmoother, TrackingGuard
from taharrak.analysis   import (det_quality_ex, build_msgs,
                                  analyze_camera_position, check_exercise_framing)
from taharrak.session    import save_csv, persist_session
from taharrak.messages   import t
from taharrak.database   import (init_db, get_last_sessions,
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
        "default_language": "en",
        "warmup_mode": True,
        "landmark_smooth_window": 7,
        "segmentation_enabled": True,
        "segmentation_bg_color": [10, 10, 25],
    }
    if os.path.exists(path):
        with open(path) as f:
            defaults.update(json.load(f))
    return defaults


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="Taharrak — AI Fitness Trainer")
    ap.add_argument("--camera",    type=int, default=0)
    ap.add_argument("--reps",      type=int, default=None)
    ap.add_argument("--no-voice",  action="store_true")
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--rest",      type=int, default=None)
    ap.add_argument("--lang",      type=str, default=None, choices=["en", "ar"])
    return ap.parse_args()


# ── Set helpers ───────────────────────────────────────────────────────────────

def _close_set(trackers: list, set_count: int, set_history: list):
    set_history.append(tuple(tr.rep_count for tr in trackers))
    for tr in trackers:
        tr.current_set = set_count + 1


def _start_next_set(trackers: list, set_count: int):
    for tr in trackers:
        tr.reset_set()
        tr.current_set = set_count + 1


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    cfg  = load_config()

    if args.reps      is not None: cfg["target_reps"]    = args.reps
    if args.no_voice:               cfg["voice_enabled"]  = False
    if args.no_mirror:              cfg["mirror_mode"]    = False
    if args.rest      is not None: cfg["rest_duration"]   = args.rest

    lang = args.lang or cfg.get("default_language", "en")

    ensure_model()
    init_db(cfg)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {args.camera}.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    cv2.namedWindow("Taharrak — AI Fitness", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Taharrak — AI Fitness", 1280, 720)
    cv2.setWindowProperty("Taharrak — AI Fitness",
                          cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    fps   = cap.get(cv2.CAP_PROP_FPS) or 30
    voice = VoiceEngine(cfg["voice_enabled"], cfg.get("voice_rate", 160))

    seg_enabled = cfg.get("segmentation_enabled", True)
    seg_bg      = tuple(cfg.get("segmentation_bg_color", [10, 10, 25]))

    base_opts = python.BaseOptions(model_asset_path=MODEL_PATH)
    options   = vision.PoseLandmarkerOptions(
        base_options=base_opts,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.48,
        min_pose_presence_confidence=0.48,
        min_tracking_confidence=0.48,
        output_segmentation_masks=seg_enabled,
    )

    lm_smoother = OneEuroLandmarkSmoother(
        num_landmarks = 33,
        freq          = fps,
        min_cutoff    = cfg.get("one_euro_min_cutoff", 1.5),
        beta          = cfg.get("one_euro_beta",       0.007),
        d_cutoff      = cfg.get("one_euro_d_cutoff",   1.0),
    )

    # ── State machine variables ───────────────────────────────────────
    state            = "EXERCISE_SELECT"
    exercise         = None
    trackers         = []
    weight_kg        = 0.0
    suggest_overload = False

    countdown_start  = None
    rest_start       = None
    set_count        = 0
    set_history      = []
    summary_start    = None
    session_start    = None
    score_flash      = {}
    cam_feedback     = []
    can_start        = False

    history_rows    = []
    history_scroll  = 0
    pb              = {}

    guard     = None
    frame_idx = 0
    mirror    = cfg.get("mirror_mode", True)

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            h, w = frame.shape[:2]

            # ── Pose detection ────────────────────────────────────────
            mp_img = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            )
            ts     = int(frame_idx * 1000 / fps)
            result = landmarker.detect_for_video(mp_img, ts)
            frame_idx += 1

            # ── Landmark smoothing ────────────────────────────────────
            lm_smooth = None
            if result.pose_landmarks:
                lm_smooth = lm_smoother.smooth(result.pose_landmarks[0])

            # ── Background segmentation ───────────────────────────────
            if seg_enabled and result.segmentation_masks:
                mask    = result.segmentation_masks[0].numpy_view()
                mask_u8 = (mask * 255).astype(np.uint8)
                mask3   = cv2.merge([mask_u8, mask_u8, mask_u8])
                bg      = np.full_like(frame, seg_bg, dtype=np.uint8)
                display = cv2.convertScaleAbs(
                    frame.astype(np.float32) * (mask3 / 255.0) +
                    bg.astype(np.float32)    * (1.0 - mask3 / 255.0)
                )
            else:
                display = frame.copy()

            if mirror:
                display = cv2.flip(display, 1)

            # ─────────────────────────────────────────────────────────
            # STATE RENDERING
            # ─────────────────────────────────────────────────────────

            if state == "EXERCISE_SELECT":
                ui.screen_exercise_select(display, lang,
                                          cfg.get("arabic_font_path", ""))

            elif state == "WEIGHT_INPUT":
                ui.screen_weight_input(display, exercise, weight_kg,
                                       lang, suggest_overload, cfg)

            elif state == "CALIBRATION":
                can_start    = False
                cam_feedback = []
                if lm_smooth:
                    l_q, r_q = det_quality_ex(lm_smooth, exercise, cfg)
                    cam_feedback = (analyze_camera_position(lm_smooth) +
                                   check_exercise_framing(lm_smooth, exercise, cfg))
                    can_start = (
                        l_q == "GOOD" and
                        (r_q == "GOOD" or not exercise.bilateral) and
                        not cam_feedback
                    )
                ui.screen_calibration(display, result, exercise,
                                      can_start, cam_feedback, lang, cfg)

            elif state == "COUNTDOWN":
                if lm_smooth:
                    lm_px = ui.lm_to_px(lm_smooth, w, h, mirror)
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

            elif state == "WORKOUT":
                angles = [None]  * len(trackers)
                swings = [False] * len(trackers)
                quals  = ["LOST"] * len(trackers)
                warmup = (set_count == 0)

                if lm_smooth:
                    lm    = lm_smooth
                    lm_px = ui.lm_to_px(lm, w, h, mirror)
                    ui.draw_skeleton(display, lm_px)

                    l_q_raw, r_q_raw = det_quality_ex(lm, exercise, cfg)

                    if exercise.bilateral:
                        # Left tracker
                        l_q = trackers[0].smooth_quality(l_q_raw)
                        quals[0] = l_q
                        if l_q != "LOST":
                            a, b, c  = exercise.joints_left
                            swing_lm = lm[exercise.swing_joint_left]
                            ang, sw, done, sc = trackers[0].update(
                                lm[a], lm[b], lm[c], swing_lm, w, h, warmup)
                            angles[0], swings[0] = ang, sw
                            ui.draw_arm(display, lm_px, a, b, c, ui.L_COL)
                            ui.arc_gauge(display,
                                         lm_px[exercise.joints_left[exercise.arc_joint_idx]],
                                         ang)
                            if done and sc is not None:
                                score_flash["left"] = (sc, time.time() + cfg["score_flash_duration"])
                                voice.say(f"{t(lang,'left')} {trackers[0].rep_count}. {sc}", 1.0)

                        # Right tracker
                        r_q = trackers[1].smooth_quality(r_q_raw)
                        quals[1] = r_q
                        if r_q != "LOST":
                            a, b, c  = exercise.joints_right
                            swing_lm = lm[exercise.swing_joint_right]
                            ang, sw, done, sc = trackers[1].update(
                                lm[a], lm[b], lm[c], swing_lm, w, h, warmup)
                            angles[1], swings[1] = ang, sw
                            ui.draw_arm(display, lm_px, a, b, c, ui.R_COL)
                            ui.arc_gauge(display,
                                         lm_px[exercise.joints_right[exercise.arc_joint_idx]],
                                         ang)
                            if done and sc is not None:
                                score_flash["right"] = (sc, time.time() + cfg["score_flash_duration"])
                                voice.say(f"{t(lang,'right')} {trackers[1].rep_count}. {sc}", 1.0)
                    else:
                        # Single tracker (right side)
                        r_q = trackers[0].smooth_quality(r_q_raw)
                        quals[0] = r_q
                        if r_q != "LOST":
                            a, b, c  = exercise.joints_right
                            swing_lm = lm[exercise.swing_joint_right]
                            ang, sw, done, sc = trackers[0].update(
                                lm[a], lm[b], lm[c], swing_lm, w, h, warmup)
                            angles[0], swings[0] = ang, sw
                            ui.draw_arm(display, lm_px, a, b, c, ui.R_COL)
                            ui.arc_gauge(display,
                                         lm_px[exercise.joints_right[exercise.arc_joint_idx]],
                                         ang)
                            if done and sc is not None:
                                score_flash["center"] = (sc, time.time() + cfg["score_flash_duration"])
                                voice.say(f"Rep {trackers[0].rep_count}. Score {sc}", 1.0)

                if lm_smooth and guard and guard.update(lm_smooth, trackers, exercise):
                    for tr in trackers:
                        tr.reset_tracking()
                    lm_smoother.reset()
                    guard.reset()

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

            elif state == "SUMMARY":
                elapsed_d = time.time() - summary_start
                elapsed_s = time.time() - session_start
                ui.screen_summary(display, trackers, set_count,
                                  elapsed_s, elapsed_d,
                                  exercise, weight_kg, pb, cfg, lang)
                if elapsed_d >= cfg["summary_auto_close"]:
                    break

            elif state == "HISTORY":
                ui.screen_history(display, history_rows, exercise,
                                  pb, history_scroll, lang)

            cv2.imshow("Taharrak — AI Fitness", display)

            # ─────────────────────────────────────────────────────────
            # KEY HANDLING
            # ─────────────────────────────────────────────────────────

            key = cv2.waitKey(1) & 0xFF

            # Global toggles (any state)
            if key == ord("l"):
                lang = "ar" if lang == "en" else "en"
            if key == ord("m"):
                mirror = not mirror
                cfg["mirror_mode"] = mirror

            if state == "EXERCISE_SELECT":
                if key in (ord("q"), 27):
                    break
                if key == ord("h") and exercise is not None:
                    history_rows   = get_last_sessions(cfg, exercise.key)
                    pb             = get_personal_bests(cfg, exercise.key)
                    history_scroll = 0
                    state = "HISTORY"
                for ex_key, ex in EXERCISES.items():
                    if key == ord(ex_key):
                        exercise         = ex
                        weight_kg        = get_last_weight(cfg, ex.key)
                        suggest_overload = check_overload_suggestion(cfg, ex.key, weight_kg)
                        state = "WEIGHT_INPUT"
                        break

            elif state == "WEIGHT_INPUT":
                step = cfg.get("weight_step_kg", 2.5)
                if key in (82, ord("+")):
                    weight_kg = min(weight_kg + step, cfg.get("weight_max_kg", 200))
                elif key in (84, ord("-")):
                    weight_kg = max(weight_kg - step, cfg.get("weight_min_kg", 0))
                elif key in (ord(" "), 13):   # SPACE or ENTER — confirm weight
                    trackers = (
                        [RepTracker("left", exercise, cfg),
                         RepTracker("right", exercise, cfg)]
                        if exercise.bilateral
                        else [RepTracker("center", exercise, cfg)]
                    )
                    guard         = TrackingGuard(cfg)
                    set_count     = 0
                    set_history   = []
                    session_start = time.time()
                    pb            = get_personal_bests(cfg, exercise.key)
                    lm_smoother.reset()
                    state = "CALIBRATION"
                elif key in (8, 27):          # BACKSPACE or ESC
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
                elif key == 82:
                    history_scroll = max(0, history_scroll - 1)
                elif key == 84:
                    history_scroll = min(max(0, len(history_rows) - 1),
                                         history_scroll + 1)

    cap.release()
    cv2.destroyAllWindows()

    if trackers:
        total = sum(tr.total_reps for tr in trackers)
        all_s = [sc for tr in trackers for sc in tr.form_scores]
        avg   = sum(all_s) / len(all_s) if all_s else 0.0
        print(f"\nSession finished.  {total} total reps  |  "
              f"Avg score: {avg:.0f}  |  Rating: {ui.rating(avg)}")


if __name__ == "__main__":
    main()
