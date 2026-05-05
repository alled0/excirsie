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

Robustness metrics (new)
------------------------
mean_reliability    Mean joint reliability (visibility+presence) over detected frames
recovery_rate       Fraction of detected frames where ≥1 tracker was in recovery mode
unknown_rate        Fraction of detected frames where ≥1 tracker had stage=None
aborted_reps        Total reps discarded by the lost-landmark abort logic
rejected_reps       Total reps blocked by the min-duration gate
signal_quality      Composite score: (1-dropout)·reliability·(1-recovery) ∈ [0,1]
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

from taharrak.config import load_config as _shared_load_config

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
    return _shared_load_config(path or "config.json")


def _positive_float(value, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _positive_int(value, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _resolve_replay_options(cfg: dict, source_fps: float) -> dict:
    """Resolve upload/offline video speed knobs."""
    source_fps = _positive_float(source_fps, 30.0)
    target_fps = _positive_float(cfg.get("analysis_target_fps"), source_fps)
    max_width = _positive_int(cfg.get("analysis_max_width"), 0)

    if target_fps >= source_fps:
        frame_step = 1
        effective_fps = source_fps
    else:
        frame_step = max(1, int(round(source_fps / target_fps)))
        effective_fps = source_fps / frame_step

    return {
        "source_fps": source_fps,
        "target_fps": target_fps,
        "frame_step": frame_step,
        "effective_fps": effective_fps,
        "max_width": max_width,
    }


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
    from taharrak.analysis  import det_quality_ex, joint_reliability

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

    replay_options = _resolve_replay_options(cfg, cap.get(cv2.CAP_PROP_FPS) or 30.0)
    video_fps = replay_options["source_fps"]
    effective_fps = replay_options["effective_fps"]
    frame_step = replay_options["frame_step"]
    max_width = replay_options["max_width"]

    cfg = dict(cfg)
    cfg["camera_fps"] = effective_fps   # use processed-video FPS for filters

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
        freq          = effective_fps,
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

    # Key joints for reliability sampling (same fallback as TrackingGuard)
    _key_idx = exercise.key_joints_right or exercise.joints_right
    if exercise.bilateral:
        _key_idx = _key_idx + (exercise.key_joints_left or exercise.joints_left)

    # Metric accumulators
    frames_total    = 0
    frames_detected = 0
    angle_history: list[list[float]] = [[] for _ in trackers]
    angle_deltas:  list[list[float]] = [[] for _ in trackers]
    prev_angles:   list[Optional[float]] = [None] * len(trackers)

    # Robustness accumulators
    reliability_sum  = 0.0
    recovery_frames  = 0
    unknown_frames   = 0

    wall_start = time.time()
    source_frame_idx = 0
    frames_read = 0

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok = cap.grab()
            if not ok:
                break
            current_source_idx = source_frame_idx
            source_frame_idx += 1
            frames_read += 1

            if current_source_idx % frame_step != 0:
                continue

            ok, frame = cap.retrieve()
            if not ok:
                break
            frames_total += 1

            if max_width and frame.shape[1] > max_width:
                scale = max_width / frame.shape[1]
                new_size = (max_width, max(1, int(round(frame.shape[0] * scale))))
                frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            frame_time_s = current_source_idx / video_fps
            ts     = int(frame_time_s * 1000)
            result = landmarker.detect_for_video(mp_img, ts)

            if not result.pose_landmarks:
                # No detection — signal LOST to all trackers
                for tr in trackers:
                    tr.update_quality("LOST")
                continue

            frames_detected += 1
            lm_smooth = smoother.smooth(result.pose_landmarks[0])

            # Robustness: sample reliability and FSM state every detected frame
            reliability_sum += sum(joint_reliability(lm_smooth[i])
                                   for i in _key_idx) / len(_key_idx)
            if any(tr._recovering for tr in trackers):
                recovery_frames += 1
            if any(tr.stage is None for tr in trackers):
                unknown_frames  += 1

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
                        swing_lm, w, h, now=frame_time_s, landmarks=lm_smooth)
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
                        swing_lm, w, h, now=frame_time_s, landmarks=lm_smooth)
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
                        swing_lm, w, h, now=frame_time_s, landmarks=lm_smooth)
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

    dropout_rate     = round(1.0 - frames_detected / max(frames_total, 1), 4)
    mean_reliability = round(reliability_sum / max(frames_detected, 1), 4)
    recovery_rate    = round(recovery_frames  / max(frames_detected, 1), 4)
    unknown_rate     = round(unknown_frames   / max(frames_detected, 1), 4)

    metrics = {
        "video":            os.path.basename(video_path),
        "exercise":         exercise.name,
        "exercise_key":     exercise_key,
        "frames_read":      frames_read,
        "frames_total":     frames_total,
        "frames_detected":  frames_detected,
        "source_fps":       round(video_fps, 2),
        "analysis_fps":     round(effective_fps, 2),
        "frame_step":       frame_step,
        "analysis_max_width": max_width,
        "dropout_rate":     dropout_rate,
        "angle_delta_mean": round(_mean(all_deltas), 3),
        "angle_delta_p95":  round(_p95(all_deltas), 3),
        "reps_total":       sum(tr.rep_count for tr in trackers),
        "fps_mean":         round(frames_total / elapsed, 1),
        # ── robustness metrics ────────────────────────────────────────
        "mean_reliability": mean_reliability,
        "recovery_rate":    recovery_rate,
        "unknown_rate":     unknown_rate,
        "aborted_reps":     sum(tr.aborted_reps  for tr in trackers),
        "rejected_reps":    sum(tr.rejected_reps for tr in trackers),
        "signal_quality":   compute_signal_quality(dropout_rate,
                                                    mean_reliability,
                                                    recovery_rate),
        "event_log":        [e for tr in trackers for e in tr.event_log],
    }
    if exercise.bilateral:
        metrics["reps_left"]  = trackers[0].rep_count
        metrics["reps_right"] = trackers[1].rep_count
    else:
        metrics["reps_center"] = trackers[0].rep_count

    return metrics


# ── Signal quality formula ─────────────────────────────────────────────────────

def compute_signal_quality(dropout_rate: float, mean_reliability: float,
                            recovery_rate: float) -> float:
    """
    Composite signal-quality score in [0, 1].

    Penalises three independent failure modes multiplicatively:
      - dropout_rate    : fraction of frames with no pose detected
      - mean_reliability: average joint reliability (low = occluded / missing)
      - recovery_rate   : fraction of detected frames in post-loss recovery mode

    Score = (1 - dropout) × reliability × (1 - recovery)

    1.0 = perfect (no dropout, fully reliable, never in recovery)
    0.0 = unusable signal
    """
    return round(
        (1.0 - dropout_rate) * mean_reliability * (1.0 - recovery_rate),
        4,
    )


# ── CLI helpers ────────────────────────────────────────────────────────────────

_BAR = "-" * 52

def _print_table(metrics: dict) -> None:
    print(f"\n{_BAR}")
    print(f"  Taharrak Eval  -  {metrics['exercise']}  ({metrics['video']})")
    print(_BAR)
    print(f"  Frames          {metrics['frames_detected']:>6} / {metrics['frames_total']}")
    print(f"  Dropout rate    {metrics['dropout_rate']:>6.1%}")
    print(f"  Angle d mean    {metrics['angle_delta_mean']:>6.2f} deg/frame")
    print(f"  Angle d p95     {metrics['angle_delta_p95']:>6.2f} deg/frame")
    print(f"  Reps total      {metrics['reps_total']:>6}")
    if "reps_left" in metrics:
        print(f"    left          {metrics['reps_left']:>6}")
        print(f"    right         {metrics['reps_right']:>6}")
    print(f"  Throughput      {metrics['fps_mean']:>6.1f} fps")
    print(f"  -- Robustness ---------------------------")
    print(f"  Mean reliability  {metrics['mean_reliability']:>6.3f}")
    print(f"  Recovery rate     {metrics['recovery_rate']:>6.1%}")
    print(f"  Unknown rate      {metrics['unknown_rate']:>6.1%}")
    print(f"  Aborted reps    {metrics['aborted_reps']:>6}")
    print(f"  Rejected reps   {metrics['rejected_reps']:>6}")
    print(f"  Signal quality  {metrics['signal_quality']:>8.4f}")
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
