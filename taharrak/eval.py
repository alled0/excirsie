"""
Taharrak — Offline Evaluation Harness
======================================
Replays a video file through the full MediaPipe + tracker pipeline and
reports quantitative metrics without any GUI.

Usage
-----
    python -m taharrak.eval --video path/to/clip.mp4 --exercise 1
    python -m taharrak.eval --video clip.mp4 --exercise 3 --config config.json --out results.json

Exercise keys  (same as the in-app selection)
    1 = Bicep Curl        4 = Tricep Extension
    2 = Shoulder Press    5 = Squat
    3 = Lateral Raise

Metrics reported
----------------
frames_total        Total frames in the video
frames_detected     Frames where MediaPipe found a pose
dropout_rate        1 - detected/total   (0.0 = perfect, 1.0 = no pose at all)
angle_delta_mean    Mean |angle[t] - angle[t-1]| per arm — jitter/stability metric
angle_delta_p95     95th-percentile frame-to-frame angle delta
reps_left           Reps counted on left arm  (bilateral exercises)
reps_right          Reps counted on right arm (bilateral exercises)
reps_total          Total reps across all trackers
fps_mean            Wall-clock processing throughput (frames / elapsed seconds)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

MODEL_PATH = "pose_landmarker_lite.task"
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)


def _ensure_model() -> None:
    if not os.path.exists(MODEL_PATH):
        print(f"[eval] Downloading model to {MODEL_PATH} …", flush=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[eval] Model ready.", flush=True)


def _load_cfg(path: Optional[str]) -> dict:
    """Load config.json (if present) and merge with hard-coded defaults."""
    defaults = {
        "vis_good": 0.68, "vis_weak": 0.38,
        "swing_threshold": 0.025, "swing_window": 15,
        "min_rep_time": 1.2, "ideal_rep_time": 2.5,
        "one_euro_min_cutoff": 1.5, "one_euro_beta": 0.007,
        "one_euro_d_cutoff": 1.0, "camera_fps": 30,
        "confidence_smoother_window": 10, "fatigue_score_gap": 20,
        "fsm_recovery_frames": 3, "fsm_max_lost_frames": 15,
        "landmark_smooth_window": 7,
    }
    cfg_path = path or "config.json"
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            defaults.update(json.load(f))
    return defaults


# ── Core replay function ───────────────────────────────────────────────────────

def replay_video(video_path: str, exercise_key: str,
                 cfg: dict) -> dict:
    """
    Run a video file through the full pipeline.
    Returns a metrics dict.
    """
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    from taharrak.exercises import EXERCISES
    from taharrak.tracker   import RepTracker, OneEuroLandmarkSmoother
    from taharrak.analysis  import det_quality_ex

    if exercise_key not in EXERCISES:
        raise ValueError(
            f"Unknown exercise key '{exercise_key}'. "
            f"Valid keys: {list(EXERCISES.keys())}"
        )
    exercise = EXERCISES[exercise_key]
    _ensure_model()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cfg = dict(cfg)
    cfg["camera_fps"] = video_fps   # use actual video FPS for filters

    # Build trackers (same logic as main loop)
    if exercise.bilateral:
        trackers = [
            RepTracker("left",   exercise, cfg),
            RepTracker("right",  exercise, cfg),
        ]
    else:
        trackers = [RepTracker("center", exercise, cfg)]

    smoother = OneEuroLandmarkSmoother(
        num_landmarks = 33,
        freq          = video_fps,
        min_cutoff    = cfg.get("one_euro_min_cutoff", 1.5),
        beta          = cfg.get("one_euro_beta",       0.007),
    )

    # MediaPipe pose landmarker in VIDEO mode
    base_opts = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options   = vision.PoseLandmarkerOptions(
        base_options                = base_opts,
        running_mode                = vision.RunningMode.VIDEO,
        num_poses                   = 1,
        min_pose_detection_confidence = 0.48,
        min_pose_presence_confidence  = 0.48,
        min_tracking_confidence       = 0.48,
        output_segmentation_masks     = False,
    )

    # Metric accumulators
    frames_total    = 0
    frames_detected = 0
    angle_history: list[list[float]] = [[] for _ in trackers]
    angle_deltas:  list[list[float]] = [[] for _ in trackers]
    prev_angles:   list[Optional[float]] = [None] * len(trackers)

    wall_start = time.time()
    frame_idx  = 0

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames_total += 1

            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts     = int(frame_idx * 1000 / video_fps)
            result = landmarker.detect_for_video(mp_img, ts)
            frame_idx += 1

            if not result.pose_landmarks:
                # No detection — signal LOST to all trackers
                for tr in trackers:
                    tr.update_quality("LOST")
                continue

            frames_detected += 1
            lm_smooth = smoother.smooth(result.pose_landmarks[0])

            l_q_raw, r_q_raw = det_quality_ex(lm_smooth, exercise, cfg)
            h, w = frame.shape[:2]

            if exercise.bilateral:
                # Left tracker
                l_q = trackers[0].update_quality(l_q_raw)
                if l_q != "LOST":
                    a, b, c   = exercise.joints_left
                    swing_lm  = lm_smooth[exercise.swing_joint_left]
                    ang, _, done, _ = trackers[0].update(
                        lm_smooth[a], lm_smooth[b], lm_smooth[c],
                        swing_lm, w, h)
                    angle_history[0].append(ang)
                    if prev_angles[0] is not None:
                        angle_deltas[0].append(abs(ang - prev_angles[0]))
                    prev_angles[0] = ang

                # Right tracker
                r_q = trackers[1].update_quality(r_q_raw)
                if r_q != "LOST":
                    a, b, c   = exercise.joints_right
                    swing_lm  = lm_smooth[exercise.swing_joint_right]
                    ang, _, done, _ = trackers[1].update(
                        lm_smooth[a], lm_smooth[b], lm_smooth[c],
                        swing_lm, w, h)
                    angle_history[1].append(ang)
                    if prev_angles[1] is not None:
                        angle_deltas[1].append(abs(ang - prev_angles[1]))
                    prev_angles[1] = ang
            else:
                # Single (right-side) tracker
                r_q = trackers[0].update_quality(r_q_raw)
                if r_q != "LOST":
                    a, b, c   = exercise.joints_right
                    swing_lm  = lm_smooth[exercise.swing_joint_right]
                    ang, _, done, _ = trackers[0].update(
                        lm_smooth[a], lm_smooth[b], lm_smooth[c],
                        swing_lm, w, h)
                    angle_history[0].append(ang)
                    if prev_angles[0] is not None:
                        angle_deltas[0].append(abs(ang - prev_angles[0]))
                    prev_angles[0] = ang

    cap.release()
    elapsed = max(time.time() - wall_start, 1e-3)

    # ── Aggregate metrics ──────────────────────────────────────────────────────
    all_deltas = [d for arm in angle_deltas for d in arm]

    def _mean(lst):
        return sum(lst) / len(lst) if lst else 0.0

    def _p95(lst):
        if not lst:
            return 0.0
        s = sorted(lst)
        idx = max(0, int(len(s) * 0.95) - 1)
        return s[idx]

    metrics = {
        "video":            os.path.basename(video_path),
        "exercise":         exercise.name,
        "exercise_key":     exercise_key,
        "frames_total":     frames_total,
        "frames_detected":  frames_detected,
        "dropout_rate":     round(1.0 - frames_detected / max(frames_total, 1), 4),
        "angle_delta_mean": round(_mean(all_deltas), 3),
        "angle_delta_p95":  round(_p95(all_deltas), 3),
        "reps_total":       sum(tr.rep_count for tr in trackers),
        "fps_mean":         round(frames_total / elapsed, 1),
    }
    if exercise.bilateral:
        metrics["reps_left"]  = trackers[0].rep_count
        metrics["reps_right"] = trackers[1].rep_count
    else:
        metrics["reps_center"] = trackers[0].rep_count

    return metrics


# ── CLI helpers ────────────────────────────────────────────────────────────────

_BAR = "─" * 52

def _print_table(metrics: dict) -> None:
    print(f"\n{_BAR}")
    print(f"  Taharrak Eval  —  {metrics['exercise']}  ({metrics['video']})")
    print(_BAR)
    print(f"  Frames          {metrics['frames_detected']:>6} / {metrics['frames_total']}")
    print(f"  Dropout rate    {metrics['dropout_rate']:>6.1%}")
    print(f"  Angle Δ mean    {metrics['angle_delta_mean']:>6.2f} °/frame")
    print(f"  Angle Δ p95     {metrics['angle_delta_p95']:>6.2f} °/frame")
    print(f"  Reps total      {metrics['reps_total']:>6}")
    if "reps_left" in metrics:
        print(f"    left          {metrics['reps_left']:>6}")
        print(f"    right         {metrics['reps_right']:>6}")
    print(f"  Throughput      {metrics['fps_mean']:>6.1f} fps")
    print(_BAR)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Taharrak offline evaluation harness — replay a video through the pipeline."
    )
    ap.add_argument("--video",    required=True,  help="Path to the input video file")
    ap.add_argument("--exercise", required=True,  help="Exercise key (1-5)")
    ap.add_argument("--config",   default=None,   help="Path to config.json (optional)")
    ap.add_argument("--out",      default=None,   help="Write JSON results to this file")
    args = ap.parse_args()

    if not Path(args.video).exists():
        print(f"[eval] ERROR: video file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    cfg     = _load_cfg(args.config)
    metrics = replay_video(args.video, args.exercise, cfg)
    _print_table(metrics)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"[eval] Results written to {args.out}")


if __name__ == "__main__":
    main()
