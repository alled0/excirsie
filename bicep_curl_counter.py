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

from taharrak.config     import load_config as _shared_load_config
from taharrak.exercises  import EXERCISES
from taharrak.tracker    import (RepTracker, VoiceEngine, OneEuroLandmarkSmoother,
                                 TrackingGuard, LiveTrustGate, LiveDiagnostics)
from taharrak.analysis   import (det_quality_ex, build_msgs, build_post_rep_summary,
                                  analyze_camera_position, check_exercise_framing)
from taharrak.correction import CorrectionEngine
from taharrak.session    import save_csv, save_events_csv, persist_session
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
    return _shared_load_config(path)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Taharrak — AI Fitness Trainer")
    ap.add_argument("--camera",    type=int, default=0)
    ap.add_argument("--reps",      type=int, default=None)
    ap.add_argument("--no-voice",  action="store_true")
    ap.add_argument("--no-mirror", action="store_true")
    seg_group = ap.add_mutually_exclusive_group()
    seg_group.add_argument("--seg", dest="seg_enabled", action="store_true")
    seg_group.add_argument("--no-seg", dest="seg_enabled", action="store_false")
    ap.set_defaults(seg_enabled=None)
    ap.add_argument("--rest",      type=int, default=None)
    ap.add_argument("--lang",      type=str, default=None, choices=["en", "ar"])
    return ap.parse_args(argv)


def resolve_segmentation_enabled(cfg: dict, cli_value: bool | None) -> bool:
    if cli_value is None:
        return bool(cfg.get("segmentation_enabled", True))
    return bool(cli_value)


_KEY_UP = (82, 2490368)
_KEY_DOWN = (84, 2621440)
_KEY_ENTER = (13, 10)


def key_matches(key: int, *codes: int) -> bool:
    if key < 0:
        return False
    low = key & 0xFF
    return key in codes or low in codes


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
    cfg["segmentation_enabled"] = resolve_segmentation_enabled(cfg, args.seg_enabled)
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
    trust_gate = None
    diagnostics = LiveDiagnostics()
    engine    = CorrectionEngine()
    post_rep_flash: dict = {}   # side → (msg_list, expiry_time)
    show_diag = False
    frame_idx = 0
    mirror    = cfg.get("mirror_mode", True)
    last_frame_t = time.perf_counter()

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            h, w = frame.shape[:2]
            ui.set_text_context(lang, cfg.get("arabic_font_path", ""))

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

            now_perf = time.perf_counter()
            frame_dt = max(now_perf - last_frame_t, 1e-6)
            last_frame_t = now_perf

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
                raw_quals = ["LOST"] * len(trackers)
                warmup = (set_count == 0)
                cam_feedback = []
                trust = (trust_gate.update(quals, [False] * len(trackers),
                                           count_qualities=raw_quals)
                         if trust_gate else None)

                if lm_smooth:
                    lm    = lm_smooth
                    l_q_raw, r_q_raw = det_quality_ex(lm, exercise, cfg)
                    cam_feedback = (analyze_camera_position(lm) +
                                    check_exercise_framing(lm, exercise, cfg))

                    if exercise.bilateral:
                        l_q = trackers[0].smooth_quality(l_q_raw)
                        r_q = trackers[1].smooth_quality(r_q_raw)
                        quals = [l_q, r_q]
                        raw_quals = [l_q_raw, r_q_raw]
                        trust = trust_gate.update(
                            quals, [tr._recovering for tr in trackers],
                            count_qualities=raw_quals
                        )
                        diagnostics.update(frame_dt, quals, [tr._recovering for tr in trackers])

                        if trust.render_allowed:
                            lm_px = ui.lm_to_px(lm, w, h, mirror)
                            ui.draw_skeleton(display, lm_px)
                        if trust.render_allowed and l_q_raw != "LOST":
                            a, b, c = exercise.joints_left
                            ui.draw_arm(display, lm_px, a, b, c, ui.L_COL)
                            if trust.counting_sides[0]:
                                swing_lm = lm[exercise.swing_joint_left]
                                ang, sw, done, sc = trackers[0].update(
                                    lm[a], lm[b], lm[c], swing_lm, w, h, warmup,
                                    landmarks=lm)
                                angles[0], swings[0] = ang, sw
                                ui.arc_gauge(display,
                                             lm_px[exercise.joints_left[exercise.arc_joint_idx]],
                                             ang)
                                if done and sc is not None:
                                    score_flash["left"] = (sc, time.time() + cfg["score_flash_duration"])
                                    voice.say(f"{t(lang,'left')} {trackers[0].rep_count}. {sc}", 1.0)
                                    correction, summary = engine.assess_rep(trackers[0], quals[0], lang)
                                    trackers[0].last_correction = correction
                                    rep_msgs = build_post_rep_summary(summary, lang)
                                    if rep_msgs:
                                        post_rep_flash["left"] = (rep_msgs, time.time() + cfg["score_flash_duration"])

                        if trust.render_allowed and r_q_raw != "LOST":
                            a, b, c = exercise.joints_right
                            ui.draw_arm(display, lm_px, a, b, c, ui.R_COL)
                            if trust.counting_sides[1]:
                                swing_lm = lm[exercise.swing_joint_right]
                                ang, sw, done, sc = trackers[1].update(
                                    lm[a], lm[b], lm[c], swing_lm, w, h, warmup,
                                    landmarks=lm)
                                angles[1], swings[1] = ang, sw
                                ui.arc_gauge(display,
                                             lm_px[exercise.joints_right[exercise.arc_joint_idx]],
                                             ang)
                                if done and sc is not None:
                                    score_flash["right"] = (sc, time.time() + cfg["score_flash_duration"])
                                    voice.say(f"{t(lang,'right')} {trackers[1].rep_count}. {sc}", 1.0)
                                    correction, summary = engine.assess_rep(trackers[1], quals[1], lang)
                                    trackers[1].last_correction = correction
                                    rep_msgs = build_post_rep_summary(summary, lang)
                                    if rep_msgs:
                                        post_rep_flash["right"] = (rep_msgs, time.time() + cfg["score_flash_duration"])
                    else:
                        r_q = trackers[0].smooth_quality(r_q_raw)
                        quals = [r_q]
                        raw_quals = [r_q_raw]
                        trust = trust_gate.update(
                            quals, [trackers[0]._recovering],
                            count_qualities=raw_quals
                        )
                        diagnostics.update(frame_dt, quals, [trackers[0]._recovering])

                        if trust.render_allowed:
                            lm_px = ui.lm_to_px(lm, w, h, mirror)
                            ui.draw_skeleton(display, lm_px)
                        if trust.render_allowed and r_q_raw != "LOST":
                            a, b, c = exercise.joints_right
                            ui.draw_arm(display, lm_px, a, b, c, ui.R_COL)
                            if trust.counting_sides[0]:
                                swing_lm = lm[exercise.swing_joint_right]
                                ang, sw, done, sc = trackers[0].update(
                                    lm[a], lm[b], lm[c], swing_lm, w, h, warmup,
                                    landmarks=lm)
                                angles[0], swings[0] = ang, sw
                                ui.arc_gauge(display,
                                             lm_px[exercise.joints_right[exercise.arc_joint_idx]],
                                             ang)
                                if done and sc is not None:
                                    score_flash["center"] = (sc, time.time() + cfg["score_flash_duration"])
                                    voice.say(f"Rep {trackers[0].rep_count}. Score {sc}", 1.0)
                                    correction, summary = engine.assess_rep(trackers[0], quals[0], lang)
                                    trackers[0].last_correction = correction
                                    rep_msgs = build_post_rep_summary(summary, lang)
                                    if rep_msgs:
                                        post_rep_flash["center"] = (rep_msgs, time.time() + cfg["score_flash_duration"])
                elif trackers:
                    for tr in trackers:
                        tr.smooth_quality("LOST")
                    quals = ["LOST"] * len(trackers)
                    raw_quals = quals[:]
                    trust = trust_gate.update(
                        quals, [tr._recovering for tr in trackers],
                        count_qualities=raw_quals
                    )
                    diagnostics.update(frame_dt, quals, [tr._recovering for tr in trackers])

                if lm_smooth and guard and guard.update(lm_smooth, trackers, exercise):
                    for tr in trackers:
                        tr.reset_tracking()
                    lm_smoother.reset()
                    guard.reset()

                # Post-rep summary overrides live coaching for score_flash_duration
                _now = time.time()
                _active_post_rep = next(
                    (flash_msgs for flash_msgs, expiry in post_rep_flash.values()
                     if _now < expiry),
                    None,
                )
                if _active_post_rep:
                    msgs = _active_post_rep
                else:
                    msgs = build_msgs(trackers, angles, swings,
                                      exercise, cfg, lang,
                                      voice=voice,
                                      qualities=quals, trust=trust,
                                      cam_feedback=cam_feedback)

                if exercise.bilateral:
                    ui.screen_workout_bilateral(
                        display, trackers[0], trackers[1],
                        angles[0], angles[1], swings[0], swings[1],
                        quals[0], quals[1], set_count + 1,
                        score_flash, msgs, exercise, cfg, lang,
                        angle_visible=tuple(trust.render_allowed and q == "GOOD" for q in quals),
                        tempo_visible=tuple(trust.counting_sides[i] and q == "GOOD" and trackers[i]._in_rep
                                            for i, q in enumerate(quals)),
                        comparison_allowed=trust.bilateral_compare_allowed)
                    if show_diag and trust is not None:
                        ui.draw_live_diagnostics(display, diagnostics.snapshot(), trust,
                                                 raw_quals=raw_quals, trackers=trackers,
                                                 seg_enabled=seg_enabled, lang=lang)
                else:
                    ui.screen_workout_single(
                        display, trackers[0], angles[0], swings[0],
                        quals[0], set_count + 1, score_flash,
                        msgs, exercise, cfg, lang,
                        angle_visible=(trust.render_allowed and quals[0] == "GOOD"),
                        tempo_visible=(trust.counting_sides[0] and quals[0] == "GOOD" and
                                       trackers[0]._in_rep))
                    if show_diag and trust is not None:
                        ui.draw_live_diagnostics(display, diagnostics.snapshot(), trust,
                                                 raw_quals=raw_quals, trackers=trackers,
                                                 seg_enabled=seg_enabled, lang=lang)

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
                    engine.reset()
                    post_rep_flash.clear()
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

            key = cv2.waitKeyEx(1)

            # Global toggles (any state)
            if key == ord("l"):
                lang = "ar" if lang == "en" else "en"
            if key == ord("m"):
                mirror = not mirror
                cfg["mirror_mode"] = mirror
            if key == ord("d"):
                show_diag = not show_diag

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
                if key_matches(key, *_KEY_UP, ord("+")):
                    weight_kg = min(weight_kg + step, cfg.get("weight_max_kg", 200))
                elif key_matches(key, *_KEY_DOWN, ord("-")):
                    weight_kg = max(weight_kg - step, cfg.get("weight_min_kg", 0))
                elif key_matches(key, ord(" "), *_KEY_ENTER):   # SPACE or ENTER — confirm weight
                    trackers = (
                        [RepTracker("left", exercise, cfg),
                         RepTracker("right", exercise, cfg)]
                        if exercise.bilateral
                        else [RepTracker("center", exercise, cfg)]
                    )
                    guard         = TrackingGuard(cfg)
                    trust_gate    = LiveTrustGate(cfg, exercise.bilateral)
                    diagnostics   = LiveDiagnostics()
                    engine        = CorrectionEngine()
                    post_rep_flash = {}
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
                    save_events_csv(trackers)
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
                    engine.reset()
                    post_rep_flash.clear()

            elif state == "REST":
                if key == ord(" "):
                    _start_next_set(trackers, set_count)
                    engine.reset()
                    post_rep_flash.clear()
                    state = "WORKOUT"
                    voice.say(t(lang, "go"))
                elif key in (ord("q"), 27):
                    persist_session(cfg, trackers, exercise,
                                    weight_kg, set_count, session_start)
                    save_csv(trackers)
                    save_events_csv(trackers)
                    summary_start = time.time()
                    state = "SUMMARY"

            elif state == "SUMMARY":
                if key != 0xFF:
                    break

            elif state == "HISTORY":
                if key in (27, 8, ord("h")):
                    state = "EXERCISE_SELECT"
                elif key_matches(key, *_KEY_UP):
                    history_scroll = max(0, history_scroll - 1)
                elif key_matches(key, *_KEY_DOWN):
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
