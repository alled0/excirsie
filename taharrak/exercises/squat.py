"""Squat — bodyweight or barbell squat, single (right-side) tracker."""
from .base import Exercise, LH, LK, LA, RH, RK, RA  # noqa: F401

SQUAT = Exercise(
    name              = "Squat",
    name_ar           = "القرفصاء",
    key               = "5",
    joints_left       = (LH, LK, LA),   # hip → knee → ankle
    joints_right      = (RH, RK, RA),
    angle_down        = 168.0,  # legs fully extended (standing)
    angle_up          = 90.0,   # at depth (thighs parallel to floor)
    invert            = False,  # angle decreases to complete rep
    bilateral         = False,  # single right-side tracker (full-body move)
    swing_joint_left  = LH,
    swing_joint_right = RH,
    swing_threshold   = 0.030,
    rom_tolerance     = 12.0,
    ideal_rep_time    = 3.0,
    min_rep_time      = 1.5,
    stage_labels      = ("STAND", "DEPTH"),
    arc_joint_idx     = 1,      # arc gauge on knee
    key_joints_left   = (LK, LA),  # knee + ankle must be visible
    key_joints_right  = (RK, RA),
)
