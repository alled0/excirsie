"""
Exercise dataclass and BlazePose landmark index constants.

All exercise files import their joint indices from here so there is
one canonical source of truth for the landmark numbering.
"""
from dataclasses import dataclass


@dataclass
class Exercise:
    name: str                   # English display name
    name_ar: str                # Arabic display name
    key: str                    # keyboard selection key (single char)
    joints_left:  tuple         # (proximal, vertex, distal) landmark indices
    joints_right: tuple
    angle_down: float           # angle at start / relaxed position
    angle_up:   float           # angle at peak / contracted position
    invert: bool                # False = angle decreases to complete rep (curl)
                                # True  = angle increases to complete rep (press)
    bilateral: bool             # True = track left and right arms separately
    swing_joint_left:  int      # landmark index monitored for sway (left side)
    swing_joint_right: int      # landmark index monitored for sway (right side)
    swing_threshold: float
    rom_tolerance: float        # degrees of grace before penalising range-of-motion
    ideal_rep_time: float       # seconds for a perfectly-paced rep
    min_rep_time: float         # below this → "too fast" penalty
    stage_labels: tuple         # (start_label, end_label) shown in the HUD
    arc_joint_idx: int          # which joint in the triplet gets the arc gauge (0/1/2)


# ── BlazePose 33-landmark indices ─────────────────────────────────────────────
LS, LE, LW = 11, 13, 15   # left  shoulder / elbow / wrist
RS, RE, RW = 12, 14, 16   # right shoulder / elbow / wrist
LH, RH     = 23, 24       # left / right hip
LK, RK     = 25, 26       # left / right knee
LA, RA     = 27, 28       # left / right ankle
