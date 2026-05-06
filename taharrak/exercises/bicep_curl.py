"""Bicep Curl — standing dumbbell curl, both arms tracked independently."""
from .base import Exercise, TechniqueProfile, LS, LE, LW, RS, RE, RW

_TECHNIQUE = TechniqueProfile(
    preferred_view="front",
    primary_signal="elbow_flexion_angle",
    secondary_signals=("upper_arm_drift", "trunk_swing"),
    start_thresholds={"elbow_angle_deg": (150.0, 165.0)},
    end_thresholds={"elbow_angle_deg": (55.0, 75.0)},
    top_faults=("upper_arm_drift", "trunk_swing", "incomplete_rom"),
    coaching_cues=(
        "keep_upper_arm_still",
        "dont_swing_body",
        "curl_higher",
        "lower_with_control",
    ),
    confidence_requirements={
        "primary_signal": "GOOD",
        "secondary_signals": "WEAK_OR_BETTER",
    },
    positive_cue_by_stage={"end": "lower_with_control"},
)

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
    key_joints_left   = (LE, LW),  # elbow + wrist must be visible
    key_joints_right  = (RE, RW),
    technique_profile = _TECHNIQUE,
)
