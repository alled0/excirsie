"""Bicep Curl — standing dumbbell curl, both arms tracked independently."""
from .base import Exercise, LS, LE, LW, RS, RE, RW

BICEP_CURL = Exercise(
    name              = "Bicep Curl",
    name_ar           = "تمرين العضلة ذات الرأسين",
    key               = "1",
    joints_left       = (LS, LE, LW),
    joints_right      = (RS, RE, RW),
    angle_down        = 160.0,   # arm fully extended
    angle_up          = 40.0,    # arm fully curled
    invert            = False,   # angle decreases to complete rep
    bilateral         = True,
    swing_joint_left  = LS,
    swing_joint_right = RS,
    swing_threshold   = 0.025,
    rom_tolerance     = 10.0,
    ideal_rep_time    = 2.5,
    min_rep_time      = 1.2,
    stage_labels      = ("DOWN", "UP"),
    arc_joint_idx     = 1,       # arc gauge on elbow
)
