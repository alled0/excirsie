"""Shoulder Press — overhead dumbbell press, both arms tracked independently."""
from .base import Exercise, LS, LE, LW, RS, RE, RW

SHOULDER_PRESS = Exercise(
    name              = "Shoulder Press",
    name_ar           = "ضغط الكتف",
    key               = "2",
    joints_left       = (LS, LE, LW),
    joints_right      = (RS, RE, RW),
    angle_down        = 90.0,    # elbows at 90 ° (start position)
    angle_up          = 165.0,   # arms fully extended overhead
    invert            = True,    # angle increases to complete rep
    bilateral         = True,
    swing_joint_left  = LS,
    swing_joint_right = RS,
    swing_threshold   = 0.020,
    rom_tolerance     = 12.0,
    ideal_rep_time    = 2.0,
    min_rep_time      = 1.0,
    stage_labels      = ("START", "PRESS"),
    arc_joint_idx     = 1,       # arc gauge on elbow
    key_joints_left   = (LE, LW),  # elbow + wrist must be visible
    key_joints_right  = (RE, RW),
)
