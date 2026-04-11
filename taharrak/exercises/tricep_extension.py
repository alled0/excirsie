"""Tricep Extension — overhead or cable extension, both arms tracked independently."""
from .base import Exercise, TechniqueProfile, LS, LE, LW, RS, RE, RW

_TECHNIQUE = TechniqueProfile(
    preferred_view="side_or_slight_angle",
    primary_signal="elbow_extension_angle",
    secondary_signals=("elbow_flare", "shoulder_drift"),
    start_thresholds={"elbow_angle_deg": (65.0, 90.0)},
    end_thresholds={"elbow_angle_deg": (150.0, 170.0)},
    top_faults=("elbow_flare", "shoulder_drift", "incomplete_extension"),
    coaching_cues=(
        "keep_elbows_in",
        "move_only_forearms",
        "finish_extension",
        "keep_shoulders_still",
    ),
    confidence_requirements={
        "primary_signal": "GOOD",
        "secondary_signals": "WEAK_OR_BETTER",
    },
)

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
    technique_profile = _TECHNIQUE,
)
