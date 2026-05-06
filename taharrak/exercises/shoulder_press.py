"""Shoulder Press — overhead dumbbell press, both arms tracked independently."""
from .base import Exercise, TechniqueProfile, LS, LE, LW, RS, RE, RW

_TECHNIQUE = TechniqueProfile(
    preferred_view="front_or_slight_angle",
    primary_signal="elbow_extension_angle",
    secondary_signals=("wrist_height", "wrist_over_elbow_alignment"),
    start_thresholds={
        "elbow_angle_deg": (75.0, 100.0),
        "wrist_near_elbow_line": True,
    },
    end_thresholds={
        "elbow_angle_deg": (155.0, 170.0),
        "wrist_over_elbow": True,
    },
    top_faults=("excessive_lean_back", "incomplete_lockout", "wrist_elbow_misstacking"),
    coaching_cues=(
        "ribs_down",
        "dont_lean_back",
        "finish_overhead",
        "stack_wrists_over_elbows",
    ),
    confidence_requirements={
        "primary_signal": "GOOD",
        "secondary_signals": "GOOD",
    },
    positive_cue_by_stage={"start": "finish_overhead"},
)

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
    technique_profile = _TECHNIQUE,
)
