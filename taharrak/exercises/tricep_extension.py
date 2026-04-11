"""Tricep Extension — overhead or cable extension, both arms tracked independently."""
from .base import Exercise, LS, LE, LW, RS, RE, RW

TRICEP_EXTENSION = Exercise(
    name              = "Tricep Extension",
    name_ar           = "تمديد العضلة ثلاثية الرؤوس",
    key               = "4",
    joints_left       = (LS, LE, LW),
    joints_right      = (RS, RE, RW),
    angle_down        = 70.0,    # elbow fully bent (start)
    angle_up          = 165.0,   # arm fully extended
    invert            = True,    # angle increases to complete rep
    bilateral         = True,
    swing_joint_left  = LS,
    swing_joint_right = RS,
    swing_threshold   = 0.020,
    rom_tolerance     = 12.0,
    ideal_rep_time    = 2.5,
    min_rep_time      = 1.2,
    stage_labels      = ("START", "EXTEND"),
    arc_joint_idx     = 1,       # arc gauge on elbow
    key_joints_left   = (LE, LW),  # elbow + wrist must be visible
    key_joints_right  = (RE, RW),
)
