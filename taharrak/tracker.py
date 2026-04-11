"""
Core tracking classes for Taharrak.
- RepTracker       : generic rep counter + form scorer for any exercise
- ConfidenceSmoother: prevents flickering GOOD/WEAK/LOST via majority vote
- FatigueDetector  : detects form breakdown within a set
- VoiceEngine      : background TTS thread
"""

import queue
import threading
import time
from collections import Counter, deque
from datetime import datetime

import numpy as np


# ── Smoothed Landmark ─────────────────────────────────────────────────────────

class SmoothedLandmark:
    """Lightweight landmark proxy returned by LandmarkSmoother."""
    __slots__ = ('x', 'y', 'z', 'visibility')

    def __init__(self, x: float, y: float, z: float, visibility: float):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility


# ── Landmark Smoother ─────────────────────────────────────────────────────────

class LandmarkSmoother:
    """
    Sliding-window average of landmark x/y/z coordinates to reduce jitter
    caused by loose clothing obscuring true joint positions.
    Visibility is kept raw (not averaged) so detection quality is unaffected.
    Window size is configurable via config.json → landmark_smooth_window.
    """

    def __init__(self, num_landmarks: int = 33, window: int = 7):
        self._bufs: list = [deque(maxlen=window) for _ in range(num_landmarks)]

    def smooth(self, landmarks) -> list:
        """Takes a raw MediaPipe landmark list, returns List[SmoothedLandmark]."""
        result = []
        for i, lm in enumerate(landmarks):
            buf = self._bufs[i]
            buf.append((lm.x, lm.y, lm.z))
            n = len(buf)
            result.append(SmoothedLandmark(
                x=sum(p[0] for p in buf) / n,
                y=sum(p[1] for p in buf) / n,
                z=sum(p[2] for p in buf) / n,
                visibility=lm.visibility,
            ))
        return result

    def reset(self):
        for b in self._bufs:
            b.clear()

try:
    import pyttsx3
    _TTS_OK = True
except ImportError:
    _TTS_OK = False

from taharrak.exercises import Exercise


# ── Helpers ───────────────────────────────────────────────────────────────────

def compute_angle(a, b, c) -> float:
    a, b, c = map(np.asarray, (a, b, c))
    ba, bc  = a - b, c - b
    cos     = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


# ── Confidence Smoother ───────────────────────────────────────────────────────

class ConfidenceSmoother:
    def __init__(self, window: int = 10):
        self._buf: deque = deque(maxlen=window)

    def update(self, quality: str) -> str:
        self._buf.append(quality)
        return Counter(self._buf).most_common(1)[0][0]


# ── Fatigue Detector ──────────────────────────────────────────────────────────

class FatigueDetector:
    def __init__(self, gap: float = 20.0):
        self.gap = gap

    def check(self, scores: list) -> bool:
        if len(scores) < 4:
            return False
        mid        = len(scores) // 2
        first_avg  = sum(scores[:mid]) / mid
        second_avg = sum(scores[mid:]) / (len(scores) - mid)
        return (first_avg - second_avg) >= self.gap


# ── Rep Tracker ───────────────────────────────────────────────────────────────

class RepTracker:
    def __init__(self, side: str, exercise: Exercise, cfg: dict):
        self.side     = side        # "left", "right", or "center"
        self.exercise = exercise
        self.cfg      = cfg

        self.stage      = None      # "start" | "end"
        self.rep_count  = 0         # reps this set
        self.total_reps = 0         # all-time reps
        self.current_set = 1
        self.form_scores: list  = []
        self.rep_log: list      = []

        self._angle_buf     = deque(maxlen=5)
        self._sh_y_hist     = deque(maxlen=cfg.get("swing_window", 15))
        self._rep_start     = None
        self._rep_min_a     = 180.0
        self._rep_max_a     = 0.0
        self._swing_frames  = 0
        self._in_rep        = False
        self.rep_elapsed    = 0.0

        self._smoother      = ConfidenceSmoother(cfg.get("confidence_smoother_window", 10))
        self._fatigue       = FatigueDetector(cfg.get("fatigue_score_gap", 20))

    # ------------------------------------------------------------------
    def update(self, p_lm, v_lm, d_lm, swing_lm, w: int, h: int,
               warmup_mode: bool = False):
        """
        p_lm / v_lm / d_lm  : proximal, vertex, distal landmarks
        swing_lm             : landmark used for sway detection (shoulder or hip)
        Returns (angle, swinging, rep_done, score_or_None)
        """
        p = (p_lm.x * w, p_lm.y * h)
        v = (v_lm.x * w, v_lm.y * h)
        d = (d_lm.x * w, d_lm.y * h)

        self._angle_buf.append(compute_angle(p, v, d))
        angle = float(np.mean(self._angle_buf))

        self._sh_y_hist.append(swing_lm.y)
        swinging = (
            len(self._sh_y_hist) >= 8 and
            (max(self._sh_y_hist) - min(self._sh_y_hist)) > self.exercise.swing_threshold
        )

        # Tempo tracking
        self.rep_elapsed = (time.time() - self._rep_start) if self._rep_start else 0.0

        rep_done = False
        score    = None
        ex       = self.exercise

        if not ex.invert:
            # Angle decreases to complete rep (curl, squat)
            if angle > ex.angle_down and self.stage != "start":
                self._begin_rep()
            if angle < ex.angle_up and self.stage == "start":
                dur   = (time.time() - self._rep_start) if self._rep_start else 2.0
                score = self._score(dur, warmup_mode)
                self._finish_rep(score)
                rep_done = True
        else:
            # Angle increases to complete rep (press, lateral raise, tricep)
            if angle < ex.angle_down and self.stage != "start":
                self._begin_rep()
            if angle > ex.angle_up and self.stage == "start":
                dur   = (time.time() - self._rep_start) if self._rep_start else 2.0
                score = self._score(dur, warmup_mode)
                self._finish_rep(score)
                rep_done = True

        if self._in_rep:
            self._rep_min_a = min(self._rep_min_a, angle)
            self._rep_max_a = max(self._rep_max_a, angle)
            if swinging:
                self._swing_frames += 1

        return angle, swinging, rep_done, score

    def _begin_rep(self):
        self.stage          = "start"
        self._rep_start     = time.time()
        self.rep_elapsed    = 0.0
        self._rep_min_a     = 180.0
        self._rep_max_a     = 0.0
        self._swing_frames  = 0
        self._in_rep        = True

    def _finish_rep(self, score: int):
        self.stage      = "end"
        self.rep_count  += 1
        self.total_reps += 1
        self.form_scores.append(score)
        self.rep_log.append({
            "timestamp":   datetime.now().isoformat(),
            "side":        self.side,
            "set_num":     self.current_set,
            "rep_num":     self.rep_count,
            "score":       score,
            "duration_s":  round((time.time() - self._rep_start) if self._rep_start else 0, 2),
            "min_angle":   round(self._rep_min_a, 1),
            "max_angle":   round(self._rep_max_a, 1),
            "swing_frames": self._swing_frames,
        })
        self._in_rep    = False
        self._rep_start = None
        self.rep_elapsed = 0.0

    def _score(self, duration: float, warmup_mode: bool) -> int:
        ex  = self.exercise
        tol = ex.rom_tolerance
        s   = 100

        if not ex.invert:
            start_deficit = max(0, (ex.angle_down - tol) - self._rep_max_a)
            end_deficit   = max(0, self._rep_min_a - (ex.angle_up + tol))
        else:
            start_deficit = max(0, self._rep_min_a - (ex.angle_down + tol))
            end_deficit   = max(0, (ex.angle_up - tol) - self._rep_max_a)

        s -= min(int(start_deficit * 0.8), 25)
        s -= min(int(end_deficit   * 0.8), 25)

        if self._swing_frames >= 3:
            s -= 30
        elif self._swing_frames >= 1:
            s -= 15

        if duration < ex.min_rep_time:
            s -= 20
        elif duration < ex.ideal_rep_time * 0.6:
            s -= 10

        if warmup_mode:
            penalty = 100 - s
            s       = 100 - (penalty // 2)

        return max(0, min(100, s))

    # ------------------------------------------------------------------
    def smooth_quality(self, raw_quality: str) -> str:
        return self._smoother.update(raw_quality)

    def is_fatigued(self) -> bool:
        return self._fatigue.check(self.form_scores)

    @property
    def avg_score(self) -> float:
        return sum(self.form_scores) / len(self.form_scores) if self.form_scores else 0.0

    @property
    def best_score(self) -> int:
        return max(self.form_scores) if self.form_scores else 0

    def reset_set(self):
        self.rep_count     = 0
        self.stage         = None
        self._in_rep       = False
        self._rep_start    = None
        self._rep_min_a    = 180.0
        self._rep_max_a    = 0.0
        self._swing_frames = 0
        self.rep_elapsed   = 0.0
        self._angle_buf.clear()
        self._sh_y_hist.clear()

    def all_rep_logs(self) -> list:
        return self.rep_log


# ── Voice Engine ──────────────────────────────────────────────────────────────

class VoiceEngine:
    def __init__(self, enabled: bool, rate: int = 160):
        self._enabled = enabled and _TTS_OK
        self._q: queue.Queue = queue.Queue(maxsize=3)
        self._last: dict     = {}
        if self._enabled:
            t = threading.Thread(target=self._worker, args=(rate,), daemon=True)
            t.start()

    def say(self, msg: str, cooldown: float = 3.5):
        if not self._enabled:
            return
        now = time.time()
        if now - self._last.get(msg, 0) < cooldown:
            return
        self._last[msg] = now
        try:
            self._q.put_nowait(msg)
        except queue.Full:
            pass

    def _worker(self, rate: int):
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        while True:
            msg = self._q.get()
            engine.say(msg)
            engine.runAndWait()
