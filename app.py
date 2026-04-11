"""
app.py — Taharrak Streamlit web interface.

Wraps the taharrak/ package into a browser-accessible real-time fitness coach.
Uses streamlit-webrtc for webcam access.  All thresholds come from config.json.

Run locally:
    streamlit run app.py
"""

import json
import os
import threading
import time
import types
import urllib.request
from collections import Counter

try:
    import av
except ImportError:
    av = types.SimpleNamespace(VideoFrame=object)

import cv2
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
except ImportError:
    mp = None
    mp_python = None
    vision = None
import numpy as np
try:
    import streamlit as st
except ImportError:
    class _StreamlitShim:
        @staticmethod
        def cache_data(func=None, **kwargs):
            if func is None:
                def _decorator(inner):
                    return inner
                return _decorator
            return func

        def __getattr__(self, name):
            raise RuntimeError("Streamlit is required to run app.py")

    st = _StreamlitShim()

try:
    from streamlit_webrtc import RTCConfiguration, VideoProcessorBase, webrtc_streamer
except ImportError:
    class VideoProcessorBase:
        pass

    class RTCConfiguration(dict):
        pass

    def webrtc_streamer(*args, **kwargs):
        raise RuntimeError("streamlit-webrtc is required to run app.py")

from taharrak.analysis import build_msgs, build_post_rep_summary, det_quality_ex
from taharrak.correction import CorrectionEngine
from taharrak.exercises import EXERCISES
from taharrak.messages import t
from taharrak.tracker import (
    LiveDiagnostics,
    LiveTrustGate,
    OneEuroLandmarkSmoother,
    RepTracker,
    TrackingGuard,
)

# ── Model ─────────────────────────────────────────────────────────────────────

_MODEL_PATH = "pose_landmarker_lite.task"
_MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)

# ── WebRTC ────────────────────────────────────────────────────────────────────

_RTC_CONFIG = RTCConfiguration(
    {
        "iceServers": [
            {"urls": ["stun:stun.l.google.com:19302"]},
            {"urls": ["stun:stun1.l.google.com:19302"]},
            {"urls": ["stun:stun2.l.google.com:19302"]},
        ]
    }
)

# ── Config defaults (mirrors load_config in bicep_curl_counter.py) ────────────

_CFG_DEFAULTS: dict = {
    "vis_good":                 0.68,
    "vis_weak":                 0.38,
    "score_flash_duration":     2.5,
    "min_rep_time":             1.2,
    "ideal_rep_time":           2.5,
    "one_euro_min_cutoff":      1.5,
    "one_euro_beta":            0.007,
    "one_euro_d_cutoff":        1.0,
    "fsm_recovery_frames":      3,
    "fsm_max_lost_frames":      15,
    "guard_max_low_rel_frames": 20,
    "guard_bbox_jump":          0.25,
    "guard_scale_jump":         0.30,
    "guard_recovery_window":    5.0,
    "guard_max_recoveries":     4,
    "trust_count_frames":       1,
    "trust_coach_frames":       5,
    "swing_window":             15,
    "confidence_smoother_window": 10,
    "fatigue_score_gap":        20,
    "camera_fps":               30,
}

# ── Drawing constants ─────────────────────────────────────────────────────────

# BlazePose 33-landmark skeleton connections (hardcoded — mp.solutions.pose
# is not present in mediapipe >= 0.10 Tasks-only builds).
_POSE_CONNECTIONS: frozenset = frozenset([
    # Face
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    # Left arm
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    # Right arm
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    # Shoulders
    (11, 12),
    # Torso
    (11, 23), (12, 24), (23, 24),
    # Left leg
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    # Right leg
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
])


def _pose_connections():
    return _POSE_CONNECTIONS

_SEV_BGR: dict = {
    "error":   (50,  50, 230),
    "warning": (50, 165, 230),
    "ok":      (80, 220,  80),
}

_QUALITY_BGR: dict = {
    "GOOD": ( 60, 210,  60),
    "WEAK": ( 60, 180, 220),
    "LOST": ( 60,  60, 220),
}

_RUNTIME_MODE = "VIDEO"


def _require_runtime_deps() -> None:
    if mp is None or mp_python is None or vision is None:
        raise RuntimeError("mediapipe is required to run the Streamlit app")


def _runtime_settings(exercise_key: str, lang: str,
                      segmentation_enabled: bool) -> dict:
    return {
        "exercise_key": exercise_key,
        "lang": lang,
        "segmentation_enabled": bool(segmentation_enabled),
        "running_mode": _RUNTIME_MODE,
    }


def _restart_required_message(requested: dict, applied: dict | None) -> str | None:
    if not applied:
        return None
    changed = []
    labels = {
        "exercise_key": "exercise",
        "lang": "language",
        "segmentation_enabled": "segmentation",
    }
    for key, label in labels.items():
        if requested.get(key) != applied.get(key):
            changed.append(label)
    if not changed:
        return None
    changed_str = ", ".join(changed)
    return (
        "Settings changed while the stream is running "
        f"({changed_str}). Stop and Start again to apply them."
    )


def _next_video_timestamp_ms(last_ms: int | None,
                             frame_time_s: float | None = None,
                             monotonic_ns: int | None = None) -> int:
    if frame_time_s is not None and frame_time_s >= 0:
        candidate = int(frame_time_s * 1000)
    else:
        now_ns = time.monotonic_ns() if monotonic_ns is None else int(monotonic_ns)
        candidate = now_ns // 1_000_000
    if last_ms is not None and candidate <= last_ms:
        return last_ms + 1
    return candidate


def _apply_segmentation(frame: np.ndarray, result, bg_color: tuple[int, int, int]) -> np.ndarray:
    if not getattr(result, "segmentation_masks", None):
        return frame
    mask = result.segmentation_masks[0].numpy_view()
    mask_u8 = (mask * 255).astype(np.uint8)
    mask3 = cv2.merge([mask_u8, mask_u8, mask_u8])
    bg = np.full_like(frame, bg_color, dtype=np.uint8)
    return cv2.convertScaleAbs(
        frame.astype(np.float32) * (mask3 / 255.0) +
        bg.astype(np.float32) * (1.0 - mask3 / 255.0)
    )


def _diagnostic_rows(diag: dict, bilateral: bool) -> list[str]:
    if not diag:
        return []
    trust = diag.get("trust", {})
    qualities = diag.get("qualities", ())
    def _side_flag(values, idx):
        if idx < len(values):
            return bool(values[idx])
        return False
    rows = [
        f"Mode: {diag.get('mode', '?')} · {'Seg on' if diag.get('segmentation') else 'Seg off'}",
        f"FPS: {diag.get('fps', 0.0):.1f} · dt: {diag.get('dt_ms', 0.0):.1f} ms · jitter: {diag.get('jitter_ms', 0.0):.1f} ms",
    ]
    if bilateral:
        q_left = qualities[0] if len(qualities) > 0 else "LOST"
        q_right = qualities[1] if len(qualities) > 1 else "LOST"
        count_sides = tuple(trust.get("counting_sides", (False, False)))
        coach_sides = tuple(trust.get("coaching_sides", (False, False)))
        rows.append(f"Quality: L {q_left} · R {q_right}")
        rows.append(
            "Trust: "
            f"render {'on' if trust.get('render_allowed') else 'off'} · "
            f"count L {'on' if _side_flag(count_sides, 0) else 'off'} / R {'on' if _side_flag(count_sides, 1) else 'off'} · "
            f"coach L {'on' if _side_flag(coach_sides, 0) else 'off'} / R {'on' if _side_flag(coach_sides, 1) else 'off'}"
        )
    else:
        q_center = qualities[0] if qualities else "LOST"
        count_side = _side_flag(tuple(trust.get("counting_sides", ())), 0)
        coach_side = _side_flag(tuple(trust.get("coaching_sides", ())), 0)
        rows.append(f"Quality: {q_center}")
        rows.append(
            "Trust: "
            f"render {'on' if trust.get('render_allowed') else 'off'} · "
            f"count {'on' if count_side else 'off'} · "
            f"coach {'on' if coach_side else 'off'}"
        )
    rows.append(
        "Recovery: "
        f"{diag.get('recovery_frac', 0.0):.0%} · "
        f"weak: {diag.get('weak_frac', 0.0):.0%} · "
        f"lost: {diag.get('lost_frac', 0.0):.0%}"
    )
    return rows


# ── Null voice (no TTS in web version) ───────────────────────────────────────

class _NullVoice:
    """Drop-in replacement for VoiceEngine; silently ignores all calls."""
    def say(self, *a, **kw) -> None:  # noqa: D401
        pass


# ── Thread-safe shared state ──────────────────────────────────────────────────

class _SharedState:
    """
    Container written by the VideoProcessor thread and read by Streamlit.
    Every write/read pair is guarded by a lock.
    """

    def __init__(self) -> None:
        self._lock           = threading.Lock()
        self.rep_counts:  dict    = {}
        self.avg_scores:  dict    = {}
        self.qualities:   dict    = {}
        self.form_msgs:   list    = []
        self.last_correction      = None  # RepCorrection | None
        self.session_faults       = Counter()
        self.diagnostics: dict    = {}
        self.applied_settings: dict = {}
        self.frames: int          = 0

    def push(
        self,
        rep_counts:    dict,
        avg_scores:    dict,
        qualities:     dict,
        form_msgs:     list,
        last_correction,
        session_faults: Counter,
        diagnostics: dict,
        applied_settings: dict,
        frames: int,
    ) -> None:
        with self._lock:
            self.rep_counts      = dict(rep_counts)
            self.avg_scores      = dict(avg_scores)
            self.qualities       = dict(qualities)
            self.form_msgs       = list(form_msgs)
            self.last_correction = last_correction
            self.session_faults  = Counter(session_faults)
            self.diagnostics     = dict(diagnostics)
            self.applied_settings = dict(applied_settings)
            self.frames          = frames

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "rep_counts":      dict(self.rep_counts),
                "avg_scores":      dict(self.avg_scores),
                "qualities":       dict(self.qualities),
                "form_msgs":       list(self.form_msgs),
                "last_correction": self.last_correction,
                "session_faults":  Counter(self.session_faults),
                "diagnostics":     dict(self.diagnostics),
                "applied_settings": dict(self.applied_settings),
                "frames":          self.frames,
            }


# ── Video processor ───────────────────────────────────────────────────────────

class TaharrrakProcessor(VideoProcessorBase):
    """
    Receives raw webcam frames from streamlit-webrtc, runs the full
    Taharrak pose → tracking → correction pipeline, draws the HUD,
    and exposes live state via ``self.shared``.

    One instance lives for the entire stream session.
    """

    def __init__(self, exercise_key: str, lang: str, cfg: dict,
                 segmentation_enabled: bool) -> None:
        _require_runtime_deps()
        self.exercise_key = exercise_key
        self.lang         = lang
        self.cfg          = cfg
        self.shared       = _SharedState()
        self._voice       = _NullVoice()
        self.segmentation_enabled = bool(segmentation_enabled)
        self.running_mode = _RUNTIME_MODE
        self._seg_bg = tuple(cfg.get("segmentation_bg_color", [10, 10, 25]))
        self._applied_settings = _runtime_settings(
            exercise_key, lang, self.segmentation_enabled
        )

        exercise       = EXERCISES[exercise_key]
        self._exercise = exercise

        base_opts = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        opts = vision.PoseLandmarkerOptions(
            base_options=base_opts,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.48,
            min_pose_presence_confidence=0.48,
            min_tracking_confidence=0.48,
            output_segmentation_masks=self.segmentation_enabled,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(opts)

        # Landmark smoother
        self._smoother = OneEuroLandmarkSmoother(
            num_landmarks=33,
            freq=float(cfg.get("camera_fps", 30)),
            min_cutoff=cfg.get("one_euro_min_cutoff", 1.5),
            beta=cfg.get("one_euro_beta", 0.007),
            d_cutoff=cfg.get("one_euro_d_cutoff", 1.0),
        )

        # Trackers (one per arm for bilateral exercises, one for unilateral)
        if exercise.bilateral:
            self._trackers = [
                RepTracker("left",   exercise, cfg),
                RepTracker("right",  exercise, cfg),
            ]
        else:
            self._trackers = [RepTracker("center", exercise, cfg)]

        # Trust gate and tracking guard
        self._trust_gate = LiveTrustGate(cfg, exercise.bilateral)
        self._guard      = TrackingGuard(cfg)
        self._diagnostics = LiveDiagnostics()

        # Correction engine
        self._engine = CorrectionEngine()

        # Post-rep flash: side → (msgs_list, expiry_timestamp)
        self._post_rep_flash: dict = {}

        # Fault counter accumulated across all completed reps this session
        self._session_faults: Counter = Counter()

        self._frame_idx: int = 0
        self._last_recv_t: float | None = None
        self._last_video_ts_ms: int | None = None

        # Cache pose connections once
        self._connections = _pose_connections()

    # ── Frame processing ──────────────────────────────────────────────────────

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        h, w = img.shape[:2]
        recv_t = time.monotonic()
        dt = recv_t - self._last_recv_t if self._last_recv_t is not None else 1.0 / max(float(self.cfg.get("camera_fps", 30)), 1.0)
        self._last_recv_t = recv_t

        # Detect pose
        rgb    = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms = _next_video_timestamp_ms(
            self._last_video_ts_ms,
            frame_time_s=getattr(frame, "time", None),
        )
        self._last_video_ts_ms = ts_ms
        result = self._landmarker.detect_for_video(mp_img, ts_ms)
        if self.segmentation_enabled:
            img = _apply_segmentation(img, result, self._seg_bg)

        lm_smooth = (
            self._smoother.smooth(result.pose_landmarks[0])
            if result.pose_landmarks
            else None
        )

        exercise  = self._exercise
        trackers  = self._trackers
        cfg       = self.cfg
        lang      = self.lang

        angles    = [None]  * len(trackers)
        swings    = [False] * len(trackers)
        quals     = ["LOST"] * len(trackers)
        raw_quals = ["LOST"] * len(trackers)
        trust     = None

        if lm_smooth:
            lm               = lm_smooth
            l_q_raw, r_q_raw = det_quality_ex(lm, exercise, cfg)

            if exercise.bilateral:
                l_q       = trackers[0].smooth_quality(l_q_raw)
                r_q       = trackers[1].smooth_quality(r_q_raw)
                quals     = [l_q, r_q]
                raw_quals = [l_q_raw, r_q_raw]
            else:
                r_q       = trackers[0].smooth_quality(r_q_raw)
                quals     = [r_q]
                raw_quals = [r_q_raw]

            trust = self._trust_gate.update(
                quals,
                [tr._recovering for tr in trackers],
                count_qualities=raw_quals,
            )

            if exercise.bilateral:
                # Left arm
                a, b, c = exercise.joints_left
                if l_q_raw != "LOST" and trust.counting_sides[0]:
                    ang, sw, done, sc = trackers[0].update(
                        lm[a], lm[b], lm[c],
                        lm[exercise.swing_joint_left],
                        w, h, False,
                    )
                    angles[0], swings[0] = ang, sw
                    if done and sc is not None:
                        self._session_faults.update(trackers[0]._fault_frames)
                        corr, summary = self._engine.assess_rep(
                            trackers[0], quals[0], lang)
                        trackers[0].last_correction = corr
                        rep_msgs = build_post_rep_summary(summary, lang)
                        if rep_msgs:
                            self._post_rep_flash["left"] = (
                                rep_msgs,
                                time.time() + cfg.get("score_flash_duration", 2.5),
                            )

                # Right arm
                a, b, c = exercise.joints_right
                if r_q_raw != "LOST" and trust.counting_sides[1]:
                    ang, sw, done, sc = trackers[1].update(
                        lm[a], lm[b], lm[c],
                        lm[exercise.swing_joint_right],
                        w, h, False,
                    )
                    angles[1], swings[1] = ang, sw
                    if done and sc is not None:
                        self._session_faults.update(trackers[1]._fault_frames)
                        corr, summary = self._engine.assess_rep(
                            trackers[1], quals[1], lang)
                        trackers[1].last_correction = corr
                        rep_msgs = build_post_rep_summary(summary, lang)
                        if rep_msgs:
                            self._post_rep_flash["right"] = (
                                rep_msgs,
                                time.time() + cfg.get("score_flash_duration", 2.5),
                            )

            else:
                # Unilateral — track right-side joints (matches main app behaviour)
                a, b, c = exercise.joints_right
                if r_q_raw != "LOST" and trust.counting_sides[0]:
                    ang, sw, done, sc = trackers[0].update(
                        lm[a], lm[b], lm[c],
                        lm[exercise.swing_joint_right],
                        w, h, False,
                    )
                    angles[0], swings[0] = ang, sw
                    if done and sc is not None:
                        self._session_faults.update(trackers[0]._fault_frames)
                        corr, summary = self._engine.assess_rep(
                            trackers[0], quals[0], lang)
                        trackers[0].last_correction = corr
                        rep_msgs = build_post_rep_summary(summary, lang)
                        if rep_msgs:
                            self._post_rep_flash["center"] = (
                                rep_msgs,
                                time.time() + cfg.get("score_flash_duration", 2.5),
                            )

            # TrackingGuard — fires a soft reset when tracking degrades
            if self._guard.update(lm_smooth, trackers, exercise):
                for tr in trackers:
                    tr.reset_tracking()
                self._smoother.reset()
                self._guard.reset()

        else:
            # No pose detected — propagate LOST to all trackers + trust gate
            for tr in trackers:
                tr.smooth_quality("LOST")
            trust = self._trust_gate.update(
                ["LOST"] * len(trackers),
                [tr._recovering for tr in trackers],
                count_qualities=["LOST"] * len(trackers),
            )

        self._diagnostics.update(dt, quals, [tr._recovering for tr in trackers])

        # Post-rep flash overrides live coaching for score_flash_duration seconds
        _now   = time.time()
        _flash = next(
            (msgs for msgs, exp in self._post_rep_flash.values() if _now < exp),
            None,
        )
        msgs = _flash or build_msgs(
            trackers, angles, swings, exercise,
            self._voice, cfg, lang,
            qualities=quals, trust=trust, cam_feedback=[],
        )

        # Draw HUD on the frame
        self._draw(img, w, h, lm_smooth, exercise, trackers, quals, msgs)

        self._frame_idx += 1
        self._push_state(trackers, quals, msgs, exercise, trust)

        return av.VideoFrame.from_ndarray(img, format="bgr24")

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(
        self, img, w, h, lm_smooth, exercise, trackers, quals, msgs
    ) -> None:
        if lm_smooth:
            self._draw_skeleton(img, lm_smooth, w, h)
            self._draw_exercise_joints(img, lm_smooth, exercise, w, h)

        # Exercise name — top-centre
        name = exercise.name.upper()
        (tw, _), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
        cv2.putText(img, name, ((w - tw) // 2, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (230, 230, 230), 2, cv2.LINE_AA)

        # Rep counts
        if exercise.bilateral and len(trackers) >= 2:
            cv2.putText(img, f"L: {trackers[0].rep_count}",
                        (16, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.1,
                        (100, 200, 255), 2, cv2.LINE_AA)
            cv2.putText(img, f"R: {trackers[1].rep_count}",
                        (w - 150, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.1,
                        (255, 180, 80), 2, cv2.LINE_AA)
        else:
            cv2.putText(img, f"Reps: {trackers[0].rep_count}",
                        (16, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.1,
                        (180, 240, 180), 2, cv2.LINE_AA)

        # Signal quality — small, below rep count
        if exercise.bilateral and len(quals) >= 2:
            lq, rq = quals[0], quals[1]
            label  = f"L:{lq}  R:{rq}"
            color  = _QUALITY_BGR.get("GOOD" if lq == "GOOD" == rq else "WEAK", (150, 150, 150))
        else:
            lq    = quals[0] if quals else "LOST"
            label = lq
            color = _QUALITY_BGR.get(lq, (150, 150, 150))
        cv2.putText(img, label, (16, 95),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, color, 1, cv2.LINE_AA)

        # Form feedback — bottom strip with dark background
        if msgs:
            text, severity = msgs[0]
            text  = text.strip()
            fcolor = _SEV_BGR.get(severity, (200, 200, 200))
            (tw, th), bl = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
            pad = 10
            bar_top = h - th - pad * 3
            cv2.rectangle(img, (0, bar_top), (min(tw + pad * 2, w), h),
                          (0, 0, 0), -1)
            cv2.putText(img, text, (pad, h - pad - bl),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, fcolor, 2, cv2.LINE_AA)

    def _draw_skeleton(self, img, lm, w, h) -> None:
        """Thin grey skeleton over the full body."""
        pts = [(int(lm[i].x * w), int(lm[i].y * h)) for i in range(len(lm))]
        for s, e in self._connections:
            if s < len(lm) and e < len(lm):
                if lm[s].visibility > 0.4 and lm[e].visibility > 0.4:
                    cv2.line(img, pts[s], pts[e], (70, 70, 70), 1, cv2.LINE_AA)

    def _draw_exercise_joints(self, img, lm, exercise, w, h) -> None:
        """Highlight the exercise-specific joint triplet in a distinct colour."""
        def _triplet(indices, color):
            a, b, c = indices
            px = [(int(lm[i].x * w), int(lm[i].y * h)) for i in (a, b, c)]
            if all(lm[i].visibility > 0.4 for i in (a, b, c)):
                cv2.line(img, px[0], px[1], color, 3, cv2.LINE_AA)
                cv2.line(img, px[1], px[2], color, 3, cv2.LINE_AA)
                cv2.circle(img, px[1], 9, color, -1, cv2.LINE_AA)

        if exercise.bilateral:
            _triplet(exercise.joints_left,  (255, 160,  80))   # warm orange = left
        _triplet(exercise.joints_right, (80,  160, 255))        # cool blue  = right

    # ── State update ──────────────────────────────────────────────────────────

    def _push_state(self, trackers, quals, msgs, exercise, trust) -> None:
        rep_counts: dict = {}
        avg_scores: dict = {}
        qualities:  dict = {}

        if exercise.bilateral:
            for i, side in enumerate(("left", "right")):
                if i < len(trackers):
                    tr = trackers[i]
                    rep_counts[side] = tr.rep_count
                    avg_scores[side] = tr.avg_score
                    qualities[side]  = quals[i] if i < len(quals) else "LOST"
        else:
            tr = trackers[0]
            rep_counts["center"] = tr.rep_count
            avg_scores["center"] = tr.avg_score
            qualities["center"]  = quals[0] if quals else "LOST"

        last_correction = next(
            (tr.last_correction for tr in trackers
             if tr.last_correction and tr.last_correction.main_error),
            None,
        )
        diag = self._diagnostics.snapshot()
        diag.update({
            "mode": self.running_mode,
            "segmentation": self.segmentation_enabled,
            "trust": {
                "render_allowed": bool(trust.render_allowed) if trust else False,
                "counting_allowed": bool(trust.counting_allowed) if trust else False,
                "coaching_allowed": bool(trust.coaching_allowed) if trust else False,
                "bilateral_compare_allowed": bool(trust.bilateral_compare_allowed) if trust else False,
                "counting_sides": tuple(getattr(trust, "counting_sides", ())),
                "coaching_sides": tuple(getattr(trust, "coaching_sides", ())),
            },
        })

        self.shared.push(
            rep_counts, avg_scores, qualities, msgs,
            last_correction, self._session_faults,
            diag, self._applied_settings, self._frame_idx,
        )


# ── Config + model helpers ────────────────────────────────────────────────────

@st.cache_data
def _load_cfg() -> dict:
    cfg = dict(_CFG_DEFAULTS)
    if os.path.exists("config.json"):
        with open("config.json") as f:
            cfg.update(json.load(f))
    return cfg


def _ensure_model() -> None:
    _require_runtime_deps()
    if not os.path.exists(_MODEL_PATH):
        with st.spinner("Downloading MediaPipe pose model (~6 MB)…"):
            urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)


# ── Streamlit page ────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Taharrak — AI Fitness",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _ensure_model()
    cfg = _load_cfg()

    # ── Sidebar controls ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## Taharrak  تحرك")
        st.caption("Real-time AI fitness coach — runs in your browser")
        st.divider()

        ex_name_to_key = {v.name: k for k, v in EXERCISES.items()}
        selected_name  = st.selectbox(
            "Exercise",
            list(ex_name_to_key.keys()),
            index=0,
            help="Stop and restart the stream to switch exercises mid-session.",
        )
        exercise_key = ex_name_to_key[selected_name]
        exercise     = EXERCISES[exercise_key]

        lang_label = st.radio("Language", ["English", "عربي"], horizontal=True)
        lang       = "en" if lang_label == "English" else "ar"

        seg_default = bool(cfg.get("segmentation_enabled", True))
        segmentation_enabled = st.toggle(
            "Segmentation",
            value=seg_default,
            help="Applies the desktop-style background mask. Restart the stream to apply changes.",
        )
        show_diagnostics = st.toggle(
            "Diagnostics",
            value=False,
            help="Show FPS, frame timing, quality, trust, and recovery details.",
        )

        st.divider()
        st.markdown(
            "**Setup tips**\n"
            "- Stand ~1.5 m from the camera\n"
            "- Camera at shoulder height\n"
            "- Show both arms if bilateral\n"
            "- Good lighting improves tracking"
        )
        st.divider()
        st.caption("Powered by MediaPipe BlazePose · streamlit-webrtc")

    # ── Main panel ────────────────────────────────────────────────────
    st.title("Taharrak — AI Fitness Coach")
    st.caption(
        f"**{exercise.name}** — "
        + ("bilateral: tracks left & right independently"
           if exercise.bilateral
           else "unilateral: tracks right side")
    )

    # Factory closure — captures exercise_key, lang, cfg at call time.
    # streamlit-webrtc calls this once when the user clicks Start.
    def _factory() -> TaharrrakProcessor:
        return TaharrrakProcessor(exercise_key, lang, cfg, segmentation_enabled)

    ctx = webrtc_streamer(
        key="taharrak",
        video_processor_factory=_factory,
        rtc_configuration=_RTC_CONFIG,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )

    requested_settings = _runtime_settings(exercise_key, lang, segmentation_enabled)
    if ctx.video_processor is not None:
        warning = _restart_required_message(
            requested_settings,
            getattr(ctx.video_processor, "_applied_settings", None),
        )
        if warning:
            st.warning(warning, icon="⚠️")

    st.divider()

    # ── Stats panel ───────────────────────────────────────────────────
    if ctx.video_processor:
        snap = ctx.video_processor.shared.snapshot()
        _render_stats(snap, exercise, lang, show_diagnostics)
    else:
        st.info(
            "Click **Start** in the webcam panel, then allow camera access.  "
            "Form cues will appear on the live video.",
            icon="ℹ️",
        )


def _render_stats(snap: dict, exercise, lang: str, show_diagnostics: bool = False) -> None:
    """Render rep counters, live coaching cue, correction detail, and summary."""
    rep_counts  = snap["rep_counts"]
    avg_scores  = snap["avg_scores"]
    qualities   = snap["qualities"]
    form_msgs   = snap["form_msgs"]
    last_corr   = snap["last_correction"]
    sess_faults = snap["session_faults"]
    diagnostics = snap.get("diagnostics", {})

    # ── Metric row ────────────────────────────────────────────────────
    if exercise.bilateral:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Left Reps",  rep_counts.get("left",  0))
        with c2:
            st.metric("Right Reps", rep_counts.get("right", 0))
        with c3:
            l_a = avg_scores.get("left",  0.0)
            r_a = avg_scores.get("right", 0.0)
            den = (1 if l_a else 0) + (1 if r_a else 0)
            avg = (l_a + r_a) / den if den else 0.0
            st.metric("Avg Form", f"{avg:.0f} / 100")
        with c4:
            lq  = qualities.get("left",  "—")
            rq  = qualities.get("right", "—")
            lqi = lq[0] if lq not in ("—", "") else "?"
            rqi = rq[0] if rq not in ("—", "") else "?"
            st.metric("Signal", f"L:{lqi}  R:{rqi}")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Reps", rep_counts.get("center", 0))
        with c2:
            avg = avg_scores.get("center", 0.0)
            st.metric("Avg Form", f"{avg:.0f} / 100")
        with c3:
            st.metric("Signal", qualities.get("center", "—"))

    # ── Live coaching cue ─────────────────────────────────────────────
    if form_msgs:
        text, severity = form_msgs[0]
        clean = text.strip()
        if severity == "error":
            st.error(f"🔴 {clean}")
        elif severity == "ok":
            st.success(f"🟢 {clean}")
        else:
            st.warning(f"🟡 {clean}")

    # ── Last rep correction (Phase 3) ─────────────────────────────────
    if last_corr and last_corr.main_error:
        with st.expander("Last Rep Correction", expanded=False):
            lc1, lc2 = st.columns(2)
            with lc1:
                fault_label = last_corr.main_error.replace("_", " ").title()
                st.write(f"**Fault:** {fault_label}")
                cue_text = t(lang, last_corr.cue_key) if last_corr.cue_key else "—"
                st.write(f"**Cue:** {cue_text}")
            with lc2:
                st.write(f"**Severity:** {last_corr.severity:.0%}")
                st.write(f"**Confidence:** {last_corr.confidence:.0%}")
                tier_labels = {1: "Safety / form", 2: "ROM / structural",
                               3: "Tempo", 4: "Symmetry"}
                tier_text = tier_labels.get(last_corr.priority_tier,
                                            f"Tier {last_corr.priority_tier}")
                st.write(f"**Priority:** {tier_text}")

    # ── Session summary ───────────────────────────────────────────────
    total_reps = sum(rep_counts.values())
    if total_reps > 0:
        with st.expander("Session Summary", expanded=False):
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.metric("Total Reps", total_reps)
            with sc2:
                all_avgs = [v for v in avg_scores.values() if v > 0]
                s_avg    = sum(all_avgs) / len(all_avgs) if all_avgs else 0.0
                st.metric("Avg Form Score", f"{s_avg:.0f} / 100")
            with sc3:
                top = sess_faults.most_common(1)
                top_label = (
                    top[0][0].replace("_", " ").title() if top else "None"
                )
                st.metric("Top Fault", top_label)

            if exercise.bilateral:
                st.caption(
                    f"Left: {rep_counts.get('left', 0)} reps  ·  "
                    f"Right: {rep_counts.get('right', 0)} reps"
                )

            if sess_faults:
                st.caption("**Fault breakdown (frame counts this session):**")
                for fault, count in sess_faults.most_common(5):
                    st.caption(f"  • {fault.replace('_', ' ')}: {count} frames")

    if show_diagnostics and diagnostics:
        with st.expander("Diagnostics", expanded=True):
            for row in _diagnostic_rows(diagnostics, exercise.bilateral):
                st.caption(row)


if __name__ == "__main__":
    main()
