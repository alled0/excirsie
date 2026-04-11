"""
Core tracking classes for Taharrak.
- RepTracker            : generic rep counter + form scorer for any exercise
- ConfidenceSmoother    : prevents flickering GOOD/WEAK/LOST via majority vote
- FatigueDetector       : detects form breakdown within a set
- VoiceEngine           : background TTS thread
- OneEuroFilter         : adaptive low-pass filter for real-time signals
- OneEuroLandmarkSmoother: per-landmark One Euro filter (replaces sliding window)
- LandmarkSmoother      : legacy alias → OneEuroLandmarkSmoother
"""

import math
import queue
import threading
import time
from collections import Counter, deque
from datetime import datetime

import numpy as np


# ── Smoothed Landmark ─────────────────────────────────────────────────────────

class SmoothedLandmark:
    """Lightweight landmark proxy returned by any landmark smoother."""
    __slots__ = ('x', 'y', 'z', 'visibility', 'presence')

    def __init__(self, x: float, y: float, z: float, visibility: float,
                 presence: float = 1.0):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility
        self.presence   = presence


# ── One Euro Filter ───────────────────────────────────────────────────────────

class OneEuroFilter:
    """
    1€ filter — adaptive low-pass filter for real-time scalar smoothing.

    At low velocity (joint held still) it applies heavy smoothing to kill
    jitter.  At high velocity (rep boundary) it opens up the cutoff and
    tracks the signal with minimal lag.

    Reference: Casiez et al., CHI 2012, "1€ Filter: A Simple Speed-based
    Low-pass Filter for Noisy Input in Interactive Systems."

    Parameters
    ----------
    freq        : nominal sampling frequency (Hz).  Used as fallback dt.
    min_cutoff  : base cutoff frequency (Hz) at zero velocity.
                  Lower → smoother at rest, more lag on fast motion.
    beta        : speed coefficient.  Higher → more responsive at velocity.
    d_cutoff    : cutoff for the derivative low-pass (Hz).
    """

    def __init__(self, freq: float = 30.0, min_cutoff: float = 1.5,
                 beta: float = 0.007, d_cutoff: float = 1.0):
        self.freq       = max(float(freq), 1e-6)
        self.min_cutoff = min_cutoff
        self.beta       = beta
        self.d_cutoff   = d_cutoff
        self._x_prev: float | None = None
        self._dx_prev: float       = 0.0

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / max(dt, 1e-9))

    def filter(self, x: float, dt: float | None = None) -> float:
        """
        Filter a new sample x.  Pass dt (seconds) for accurate timing;
        omit to use 1/freq as the nominal frame period.
        Returns the filtered value.
        """
        if dt is None:
            dt = 1.0 / self.freq
        dt = max(dt, 1e-9)

        if self._x_prev is None:
            self._x_prev = x
            return x

        # Low-pass filter the derivative
        dx       = (x - self._x_prev) / dt
        a_d      = self._alpha(self.d_cutoff, dt)
        dx_hat   = a_d * dx + (1.0 - a_d) * self._dx_prev

        # Adaptive cutoff — opens up when motion is fast
        cutoff   = self.min_cutoff + self.beta * abs(dx_hat)
        a        = self._alpha(cutoff, dt)
        x_hat    = a * x + (1.0 - a) * self._x_prev

        self._x_prev  = x_hat
        self._dx_prev = dx_hat
        return x_hat

    def reset(self) -> None:
        """Clear filter state (e.g. after landmark loss / set restart)."""
        self._x_prev  = None
        self._dx_prev = 0.0


# ── One Euro Landmark Smoother ────────────────────────────────────────────────

class OneEuroLandmarkSmoother:
    """
    Per-landmark One Euro filter applied independently to x, y, z.
    Visibility is kept raw (filtering it would slow down LOST detection).

    Compared with the old sliding-window average:
    - Adapts smoothing strength to motion speed
    - Less lag at rep boundaries (high angular velocity)
    - More smoothing during holds (low velocity)

    Parameters map directly to OneEuroFilter:
      min_cutoff (config: one_euro_min_cutoff, default 1.5 Hz)
      beta       (config: one_euro_beta,       default 0.007)
      d_cutoff   (config: one_euro_d_cutoff,   default 1.0 Hz)
    """

    def __init__(self, num_landmarks: int = 33, freq: float = 30.0,
                 min_cutoff: float = 1.5, beta: float = 0.007,
                 d_cutoff: float = 1.0):
        def _f():
            return OneEuroFilter(freq, min_cutoff, beta, d_cutoff)
        self._fx = [_f() for _ in range(num_landmarks)]
        self._fy = [_f() for _ in range(num_landmarks)]
        self._fz = [_f() for _ in range(num_landmarks)]

    def smooth(self, landmarks) -> list:
        """Takes a raw MediaPipe landmark list, returns List[SmoothedLandmark]."""
        result = []
        for i, lm in enumerate(landmarks):
            result.append(SmoothedLandmark(
                x=self._fx[i].filter(lm.x),
                y=self._fy[i].filter(lm.y),
                z=self._fz[i].filter(lm.z),
                visibility=lm.visibility,
                presence=getattr(lm, 'presence', 1.0),
            ))
        return result

    def reset(self) -> None:
        """Reset all per-landmark filters (call at set start or after loss)."""
        for f in self._fx + self._fy + self._fz:
            f.reset()


# ── Backward-compatible alias ──────────────────────────────────────────────────
# Old code that does LandmarkSmoother(num_landmarks=33, window=7) still works
# because window is silently ignored.  New code should use OneEuroLandmarkSmoother.

class LandmarkSmoother(OneEuroLandmarkSmoother):
    """Legacy name for OneEuroLandmarkSmoother.  window kwarg is ignored."""
    def __init__(self, num_landmarks: int = 33, window: int = 7, **kw):
        super().__init__(num_landmarks=num_landmarks, **kw)

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

        self.stage      = None      # "start" | "end" | None (unknown)
        self.rep_count  = 0         # reps this set
        self.total_reps = 0         # all-time reps
        self.current_set = 1
        self.form_scores: list  = []
        self.rep_log: list      = []

        # One Euro filter for the angle signal (replaces 5-frame mean buffer)
        fps = float(cfg.get("camera_fps", 30))
        self._angle_filter   = OneEuroFilter(
            freq       = fps,
            min_cutoff = cfg.get("one_euro_min_cutoff", 1.5),
            beta       = cfg.get("one_euro_beta",       0.007),
            d_cutoff   = cfg.get("one_euro_d_cutoff",   1.0),
        )
        self._last_upd_t: float = 0.0   # wall-clock timestamp of last update()

        self._sh_y_hist     = deque(maxlen=cfg.get("swing_window", 15))
        self._rep_start     = None
        self._rep_min_a     = 180.0
        self._rep_max_a     = 0.0
        self._swing_frames  = 0
        self._in_rep        = False
        self.rep_elapsed    = 0.0

        # Per-set robustness counters (used by eval harness + coaching)
        self.aborted_reps      = 0   # reps discarded by _abort_rep()
        self.rejected_reps     = 0   # reps blocked by min_rep_time gate
        self._min_dur_blocked  = False  # True while held below threshold w/ short dur

        # Structured event log for non-completion events
        # Categories: lost_visibility, below_min_duration, recovery_interrupted,
        #             tracking_reset
        # Preserved across reset_tracking(); cleared on reset_set().
        self.event_log: list   = []

        # Recovery / lost-frame gating
        # After the landmark comes back from LOST, we wait _recovery_frames
        # consecutive GOOD frames before allowing new FSM transitions.
        # If a rep is in-progress and LOST persists for _max_lost_frames, the
        # in-progress rep is discarded to avoid phantom counts on re-appear.
        self._recovery_frames  = cfg.get("fsm_recovery_frames", 3)
        self._max_lost_frames  = cfg.get("fsm_max_lost_frames", 15)
        self._consecutive_good = 0
        self._consecutive_lost = 0
        self._recovering       = False

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

        # One Euro filtered angle (replaces 5-frame mean buffer)
        now = time.time()
        dt  = (now - self._last_upd_t) if self._last_upd_t else None
        self._last_upd_t = now
        angle = self._angle_filter.filter(compute_angle(p, v, d), dt)

        self._sh_y_hist.append(swing_lm.y)
        swinging = (
            len(self._sh_y_hist) >= 8 and
            (max(self._sh_y_hist) - min(self._sh_y_hist)) > self.exercise.swing_threshold
        )

        # Tempo tracking
        self.rep_elapsed = (now - self._rep_start) if self._rep_start else 0.0

        # ── Recovery gate ──────────────────────────────────────────────
        # After landmark loss, suppress FSM transitions until the signal
        # has been stable for _recovery_frames consecutive GOOD frames.
        # Still compute and return angle/swing so the HUD stays live.
        if self._recovering:
            if self._in_rep:
                self._rep_min_a = min(self._rep_min_a, angle)
                self._rep_max_a = max(self._rep_max_a, angle)
            return angle, swinging, False, None

        rep_done = False
        score    = None
        ex       = self.exercise

        if not ex.invert:
            # Angle decreases to complete rep (curl, squat)
            if angle > ex.angle_down and self.stage != "start":
                self._begin_rep()
            if angle < ex.angle_up and self.stage == "start":
                dur = (now - self._rep_start) if self._rep_start else 2.0
                # Hard block: ignore transitions faster than min_rep_time
                if dur >= ex.min_rep_time:
                    self._min_dur_blocked = False
                    score = self._score(dur, warmup_mode)
                    self._finish_rep(score)
                    rep_done = True
                elif not self._min_dur_blocked:
                    self.rejected_reps    += 1
                    self._min_dur_blocked  = True
                    self._log_event("below_min_duration",
                                    duration_s=round(dur, 3),
                                    min_rep_time=ex.min_rep_time)
        else:
            # Angle increases to complete rep (press, lateral raise, tricep)
            if angle < ex.angle_down and self.stage != "start":
                self._begin_rep()
            if angle > ex.angle_up and self.stage == "start":
                dur = (now - self._rep_start) if self._rep_start else 2.0
                if dur >= ex.min_rep_time:
                    self._min_dur_blocked = False
                    score = self._score(dur, warmup_mode)
                    self._finish_rep(score)
                    rep_done = True
                elif not self._min_dur_blocked:
                    self.rejected_reps    += 1
                    self._min_dur_blocked  = True
                    self._log_event("below_min_duration",
                                    duration_s=round(dur, 3),
                                    min_rep_time=ex.min_rep_time)

        if self._in_rep:
            self._rep_min_a = min(self._rep_min_a, angle)
            self._rep_max_a = max(self._rep_max_a, angle)
            if swinging:
                self._swing_frames += 1

        return angle, swinging, rep_done, score

    def _begin_rep(self) -> None:
        self.stage             = "start"
        self._rep_start        = time.time()
        self.rep_elapsed       = 0.0
        self._rep_min_a        = 180.0
        self._rep_max_a        = 0.0
        self._swing_frames     = 0
        self._in_rep           = True
        self._min_dur_blocked  = False

    def _abort_rep(self) -> None:
        """
        Discard an in-progress rep after prolonged landmark loss.
        Resets to 'unknown' stage so the FSM waits for a clean starting
        position before accepting the next rep — prevents phantom counts
        when landmarks reappear mid-movement.
        """
        self._log_event("lost_visibility",
                        consecutive_lost=self._consecutive_lost,
                        elapsed_s=round(self.rep_elapsed, 2),
                        min_angle=round(self._rep_min_a, 1),
                        max_angle=round(self._rep_max_a, 1))
        self._in_rep           = False
        self._rep_start        = None
        self._rep_min_a        = 180.0
        self._rep_max_a        = 0.0
        self._swing_frames     = 0
        self.stage             = None   # unknown — wait for clear start position
        self.rep_elapsed       = 0.0
        self._min_dur_blocked  = False
        self._angle_filter.reset()
        self.aborted_reps     += 1

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

    def _log_event(self, category: str, **ctx) -> None:
        """Append a structured non-completion event to event_log."""
        self.event_log.append({
            "timestamp": datetime.now().isoformat(),
            "side":      self.side,
            "set_num":   self.current_set,
            "category":  category,
            **ctx,
        })

    # ------------------------------------------------------------------
    def update_quality(self, raw_quality: str) -> str:
        """
        Update confidence smoother + recovery-gating state machine.
        Call every frame, regardless of whether update() will be called.
        Returns the smoothed quality string ('GOOD' / 'WEAK' / 'LOST').

        Recovery logic
        ──────────────
        • LOST for N ≥ max_lost_frames frames while in-rep → abort rep
        • GOOD after any LOST period → enter recovery mode
        • After recovery_frames consecutive GOOD frames → exit recovery
          and allow FSM transitions again
        """
        smoothed = self._smoother.update(raw_quality)

        if smoothed == "LOST":
            self._consecutive_good  = 0
            self._consecutive_lost += 1
            if self._in_rep and self._consecutive_lost >= self._max_lost_frames:
                self._abort_rep()
        else:
            if self._consecutive_lost > 0:
                # Transition: just came back from a loss period
                self._recovering       = True
                self._consecutive_good = 0
                if self._in_rep:
                    self._log_event("recovery_interrupted",
                                    consecutive_lost=self._consecutive_lost)
            self._consecutive_lost = 0
            self._consecutive_good += 1
            if self._recovering and self._consecutive_good >= self._recovery_frames:
                self._recovering = False

        return smoothed

    # Backward-compatible alias
    def smooth_quality(self, raw_quality: str) -> str:
        return self.update_quality(raw_quality)

    def is_fatigued(self) -> bool:
        return self._fatigue.check(self.form_scores)

    @property
    def avg_score(self) -> float:
        return sum(self.form_scores) / len(self.form_scores) if self.form_scores else 0.0

    @property
    def best_score(self) -> int:
        return max(self.form_scores) if self.form_scores else 0

    def reset_set(self) -> None:
        self.rep_count        = 0
        self.stage            = None
        self._in_rep          = False
        self._rep_start       = None
        self._rep_min_a       = 180.0
        self._rep_max_a       = 0.0
        self._swing_frames    = 0
        self.rep_elapsed      = 0.0
        self._last_upd_t      = 0.0
        self._min_dur_blocked = False
        self.aborted_reps     = 0
        self.rejected_reps    = 0
        self.event_log        = []
        self._angle_filter.reset()
        self._sh_y_hist.clear()
        # Reset recovery state so the next set starts fresh
        self._consecutive_good = 0
        self._consecutive_lost = 0
        self._recovering       = False

    def reset_tracking(self) -> None:
        """
        Soft reset: clear per-rep FSM and filter state without touching rep_count.
        Called by TrackingGuard on re-acquisition to prevent phantom reps while
        preserving the set's accumulated count.
        """
        if self._in_rep:
            self._log_event("tracking_reset",
                            min_angle=round(self._rep_min_a, 1),
                            max_angle=round(self._rep_max_a, 1),
                            elapsed_s=round(self.rep_elapsed, 2))
        self._in_rep          = False
        self._rep_start       = None
        self._rep_min_a       = 180.0
        self._rep_max_a       = 0.0
        self._swing_frames    = 0
        self._sh_y_hist.clear()
        self.stage            = None
        self.rep_elapsed      = 0.0
        self._last_upd_t      = 0.0
        self._min_dur_blocked = False
        self._angle_filter.reset()
        self._consecutive_good = 0
        self._consecutive_lost = 0
        self._recovering       = False

    def all_rep_logs(self) -> list:
        return self.rep_log

    def all_event_logs(self) -> list:
        """Return the list of non-completion events (abort / reject / suppress)."""
        return self.event_log


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


# ── Tracking Guard ────────────────────────────────────────────────────────────

class TrackingGuard:
    """
    System-level re-acquisition guard sitting above the per-arm RepTrackers.

    Monitors four signals each frame and returns True when the overall tracking
    quality has degraded enough to warrant a hard reset of all FSM / filter state.

    Triggers
    --------
    1. Low reliability  — mean key-joint reliability stays below vis_weak for
                          guard_max_low_rel_frames consecutive frames
    2. Bbox centroid jump — skeleton centre moves > guard_bbox_jump (normalised)
                            in a single frame  (large position discontinuity)
    3. Scale jump        — shoulder span changes > guard_scale_jump relatively
                            in a single frame  (abrupt zoom / person swap)
    4. Recovery frequency — trackers enter recovery mode ≥ guard_max_recoveries
                            times within guard_recovery_window seconds

    Call update() once per WORKOUT frame **after** quality signals have been
    sent to the trackers so their _recovering flags are current.

    After a trigger, call reset() to clear guard state so the next frame starts
    fresh comparison instead of immediately re-triggering.
    """

    def __init__(self, cfg: dict):
        vw = cfg.get("vis_weak", 0.38)

        self._rel_threshold      = vw
        self._max_low_rel_frames = int(cfg.get("guard_max_low_rel_frames", 20))
        self._low_rel_frames     = 0

        self._bbox_jump_thresh   = float(cfg.get("guard_bbox_jump",   0.25))
        self._scale_jump_thresh  = float(cfg.get("guard_scale_jump",  0.30))
        self._prev_centroid: tuple | None = None
        self._prev_scale:    float | None = None

        self._recovery_window    = float(cfg.get("guard_recovery_window", 5.0))
        self._max_recoveries     = int(cfg.get("guard_max_recoveries",   4))
        self._recovery_entries: deque = deque()
        self._prev_recovering    = False

    # ------------------------------------------------------------------
    def update(self, lm, trackers: list, exercise) -> bool:
        """
        Returns True when a tracking reset is recommended.
        lm       : smoothed landmark list (33 elements)
        trackers : list of RepTracker instances
        exercise : current Exercise (for key-joint indices)
        """
        from taharrak.analysis import joint_reliability  # late import — avoids circular dep

        now    = time.time()
        fired  = False

        # 1 ── Low reliability ──────────────────────────────────────────
        key_idx = exercise.key_joints_right or exercise.joints_right
        if exercise.bilateral:
            key_idx = key_idx + (exercise.key_joints_left or exercise.joints_left)
        rel = sum(joint_reliability(lm[i]) for i in key_idx) / len(key_idx)
        if rel < self._rel_threshold:
            self._low_rel_frames += 1
            if self._low_rel_frames >= self._max_low_rel_frames:
                fired = True
        else:
            self._low_rel_frames = 0

        # 2 ── Bbox centroid jump ───────────────────────────────────────
        cx = sum(lm[i].x for i in range(33)) / 33
        cy = sum(lm[i].y for i in range(33)) / 33
        if self._prev_centroid is not None:
            dx = cx - self._prev_centroid[0]
            dy = cy - self._prev_centroid[1]
            if (dx * dx + dy * dy) ** 0.5 > self._bbox_jump_thresh:
                fired = True
        self._prev_centroid = (cx, cy)

        # 3 ── Scale jump (shoulder span) ──────────────────────────────
        scale = abs(lm[11].x - lm[12].x)
        if self._prev_scale is not None and self._prev_scale > 1e-4:
            if abs(scale - self._prev_scale) / self._prev_scale > self._scale_jump_thresh:
                fired = True
        self._prev_scale = scale

        # 4 ── Recovery frequency ──────────────────────────────────────
        recovering_now = any(tr._recovering for tr in trackers)
        if recovering_now and not self._prev_recovering:
            self._recovery_entries.append(now)
        self._prev_recovering = recovering_now
        # Purge entries outside the sliding window
        while self._recovery_entries and \
                now - self._recovery_entries[0] > self._recovery_window:
            self._recovery_entries.popleft()
        if len(self._recovery_entries) >= self._max_recoveries:
            self._recovery_entries.clear()
            fired = True

        return fired

    def reset(self) -> None:
        """Clear guard state — call after triggering a tracking reset."""
        self._low_rel_frames  = 0
        self._prev_centroid   = None
        self._prev_scale      = None
        self._prev_recovering = False
        self._recovery_entries.clear()
