"""
Exercise definitions for Taharrak.
Each exercise specifies the joint triplets, angle thresholds, and scoring config.
"""

from dataclasses import dataclass


@dataclass
class Exercise:
    name: str                          # English display name
    name_ar: str                       # Arabic display name
    key: str                           # keyboard selection key
    joints_left:  tuple                # (proximal, vertex, distal) landmark indices
    joints_right: tuple
    angle_down: float                  # angle at start/relaxed position
    angle_up:   float                  # angle at peak/contracted position
    invert: bool                       # False = angle decreases to complete rep
                                       # True  = angle increases to complete rep
    bilateral: bool                    # True = track both arms separately
    swing_joint_left:  int             # landmark index to monitor for sway (left)
    swing_joint_right: int             # landmark index to monitor for sway (right)
    swing_threshold: float
    rom_tolerance: float               # degrees grace before penalising RoM
    ideal_rep_time: float              # seconds for a well-paced rep
    min_rep_time: float
    stage_labels: tuple                # (start_label, end_label) for HUD
    arc_joint_idx: int                 # which joint in the triplet gets the arc gauge (0/1/2)


# ── MediaPipe BlazePose landmark indices ──────────────────────────────────────
_LS, _LE, _LW = 11, 13, 15   # left  shoulder / elbow / wrist
_RS, _RE, _RW = 12, 14, 16   # right shoulder / elbow / wrist
_LH, _RH      = 23, 24       # left / right hip
_LK, _RK      = 25, 26       # left / right knee
_LA, _RA      = 27, 28       # left / right ankle


EXERCISES: dict[str, Exercise] = {

    "1": Exercise(
        name          = "Bicep Curl",
        name_ar       = "تمرين العضلة ذات الرأسين",
        key           = "1",
        joints_left   = (_LS, _LE, _LW),
        joints_right  = (_RS, _RE, _RW),
        angle_down    = 160.0,
        angle_up      = 40.0,
        invert        = False,
        bilateral     = True,
        swing_joint_left  = _LS,
        swing_joint_right = _RS,
        swing_threshold   = 0.025,
        rom_tolerance     = 10.0,
        ideal_rep_time    = 2.5,
        min_rep_time      = 1.2,
        stage_labels      = ("DOWN", "UP"),
        arc_joint_idx     = 1,          # arc on elbow
    ),

    "2": Exercise(
        name          = "Shoulder Press",
        name_ar       = "ضغط الكتف",
        key           = "2",
        joints_left   = (_LS, _LE, _LW),
        joints_right  = (_RS, _RE, _RW),
        angle_down    = 90.0,
        angle_up      = 165.0,
        invert        = True,
        bilateral     = True,
        swing_joint_left  = _LS,
        swing_joint_right = _RS,
        swing_threshold   = 0.020,
        rom_tolerance     = 12.0,
        ideal_rep_time    = 2.0,
        min_rep_time      = 1.0,
        stage_labels      = ("START", "PRESS"),
        arc_joint_idx     = 1,
    ),

    "3": Exercise(
        name          = "Lateral Raise",
        name_ar       = "الرفع الجانبي",
        key           = "3",
        joints_left   = (_LH, _LS, _LE),   # hip → shoulder → elbow
        joints_right  = (_RH, _RS, _RE),
        angle_down    = 15.0,
        angle_up      = 82.0,
        invert        = True,
        bilateral     = True,
        swing_joint_left  = _LS,
        swing_joint_right = _RS,
        swing_threshold   = 0.018,
        rom_tolerance     = 8.0,
        ideal_rep_time    = 2.0,
        min_rep_time      = 1.0,
        stage_labels      = ("DOWN", "UP"),
        arc_joint_idx     = 1,             # arc on shoulder
    ),

    "4": Exercise(
        name          = "Tricep Extension",
        name_ar       = "تمديد العضلة ثلاثية الرؤوس",
        key           = "4",
        joints_left   = (_LS, _LE, _LW),
        joints_right  = (_RS, _RE, _RW),
        angle_down    = 70.0,
        angle_up      = 165.0,
        invert        = True,
        bilateral     = True,
        swing_joint_left  = _LS,
        swing_joint_right = _RS,
        swing_threshold   = 0.020,
        rom_tolerance     = 12.0,
        ideal_rep_time    = 2.5,
        min_rep_time      = 1.2,
        stage_labels      = ("START", "EXTEND"),
        arc_joint_idx     = 1,
    ),

    "5": Exercise(
        name          = "Squat",
        name_ar       = "القرفصاء",
        key           = "5",
        joints_left   = (_LH, _LK, _LA),
        joints_right  = (_RH, _RK, _RA),
        angle_down    = 168.0,
        angle_up      = 90.0,
        invert        = False,
        bilateral     = False,            # single right-side tracker
        swing_joint_left  = _LH,
        swing_joint_right = _RH,
        swing_threshold   = 0.030,
        rom_tolerance     = 12.0,
        ideal_rep_time    = 3.0,
        min_rep_time      = 1.5,
        stage_labels      = ("STAND", "DEPTH"),
        arc_joint_idx     = 1,            # arc on knee
    ),
}
