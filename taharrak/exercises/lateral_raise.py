"""Lateral Raise — dumbbell side raise, both arms tracked independently."""
from .base import Exercise, TechniqueProfile, LH, LS, LE, RH, RS, RE, LW, RW

_TECHNIQUE = TechniqueProfile(
    preferred_view="front",
    primary_signal="wrist_height_relative_to_shoulder",
    secondary_signals=("shoulder_elevation", "elbow_lead"),
    start_thresholds={
        "wrist_height_vs_shoulder": "near_baseline",
        "shoulder_abduction_deg": (0.0, 20.0),
    },
    end_thresholds={
        "wrist_height_vs_shoulder": "near_shoulder_height",
        "shoulder_abduction_deg": (70.0, 95.0),
    },
    top_faults=("shrugging", "raising_too_high", "elbow_collapse"),
    coaching_cues=(
        "shoulders_down",
        "raise_to_shoulder_height",
        "lead_with_elbows",
        "keep_soft_bend",
    ),
    confidence_requirements={
        "primary_signal": "GOOD",
        "secondary_signals": "GOOD",
    },
)

LATERAL_RAISE = Exercise(
    name              = "Lateral Raise",
    name_ar           = "الرفع الجانبي",
    key               = "3",
    joints_left       = (LH, LS, LE),   # hip → shoulder → elbow
    joints_right      = (RH, RS, RE),
    angle_down        = 15.0,   # arm hanging at side
    angle_up          = 82.0,   # arm raised to shoulder height
    invert            = True,   # angle increases to complete rep
    bilateral         = True,
    swing_joint_left  = LS,
    swing_joint_right = RS,
    swing_threshold   = 0.018,
    rom_tolerance     = 8.0,
    ideal_rep_time    = 2.0,
    min_rep_time      = 1.0,
    stage_labels      = ("DOWN", "UP"),
    arc_joint_idx     = 1,      # arc gauge on shoulder
    key_joints_left   = (LS, LE),   # shoulder + elbow must be visible
    key_joints_right  = (RS, RE),
    technique_profile = _TECHNIQUE,
)
