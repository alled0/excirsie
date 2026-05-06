"""Squat — bodyweight or barbell squat, single (right-side) tracker."""
from .base import Exercise, TechniqueProfile, LH, LK, LA, RH, RK, RA  # noqa: F401

_TECHNIQUE = TechniqueProfile(
    preferred_view="side_or_front",
    primary_signal="knee_flexion_angle",
    secondary_signals=("hip_vertical_displacement", "torso_lean", "knee_tracking", "symmetry"),
    start_thresholds={"knee_angle_deg": (160.0, 175.0)},
    end_thresholds={
        "knee_angle_deg": (90.0, 120.0),
        "hip_drop": "working_depth",
    },
    top_faults=("insufficient_depth", "excessive_forward_lean", "knee_collapse"),
    coaching_cues=(
        "sit_deeper",
        "chest_up",
        "knees_over_toes",
        "stand_tall",
    ),
    confidence_requirements={
        "primary_signal": "GOOD",
        "secondary_signals": "WEAK_OR_BETTER",
    },
    positive_cue_by_stage={"end": "stand_tall"},
)

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
    technique_profile = _TECHNIQUE,
)
