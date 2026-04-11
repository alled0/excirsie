import unittest

from taharrak.exercises import EXERCISES
from taharrak.exercises.base import TechniqueProfile
from taharrak.messages import MESSAGES


EXPECTED_PROFILES = {
    "1": {
        "preferred_view": "front",
        "primary_signal": "elbow_flexion_angle",
        "secondary_signals": ("upper_arm_drift", "trunk_swing"),
        "start_thresholds": {"elbow_angle_deg": (150.0, 165.0)},
        "end_thresholds": {"elbow_angle_deg": (55.0, 75.0)},
        "top_faults": ("upper_arm_drift", "trunk_swing", "incomplete_rom"),
        "coaching_cues": (
            "keep_upper_arm_still",
            "dont_swing_body",
            "curl_higher",
            "lower_with_control",
        ),
    },
    "2": {
        "preferred_view": "front_or_slight_angle",
        "primary_signal": "elbow_extension_angle",
        "secondary_signals": ("wrist_height", "wrist_over_elbow_alignment"),
        "start_thresholds": {
            "elbow_angle_deg": (75.0, 100.0),
            "wrist_near_elbow_line": True,
        },
        "end_thresholds": {
            "elbow_angle_deg": (155.0, 170.0),
            "wrist_over_elbow": True,
        },
        "top_faults": ("excessive_lean_back", "incomplete_lockout", "wrist_elbow_misstacking"),
        "coaching_cues": (
            "ribs_down",
            "dont_lean_back",
            "finish_overhead",
            "stack_wrists_over_elbows",
        ),
    },
    "3": {
        "preferred_view": "front",
        "primary_signal": "wrist_height_relative_to_shoulder",
        "secondary_signals": ("shoulder_elevation", "elbow_lead"),
        "start_thresholds": {
            "wrist_height_vs_shoulder": "near_baseline",
            "shoulder_abduction_deg": (0.0, 20.0),
        },
        "end_thresholds": {
            "wrist_height_vs_shoulder": "near_shoulder_height",
            "shoulder_abduction_deg": (70.0, 95.0),
        },
        "top_faults": ("shrugging", "raising_too_high", "elbow_collapse"),
        "coaching_cues": (
            "shoulders_down",
            "raise_to_shoulder_height",
            "lead_with_elbows",
            "keep_soft_bend",
        ),
    },
    "4": {
        "preferred_view": "side_or_slight_angle",
        "primary_signal": "elbow_extension_angle",
        "secondary_signals": ("elbow_flare", "shoulder_drift"),
        "start_thresholds": {"elbow_angle_deg": (65.0, 90.0)},
        "end_thresholds": {"elbow_angle_deg": (150.0, 170.0)},
        "top_faults": ("elbow_flare", "shoulder_drift", "incomplete_extension"),
        "coaching_cues": (
            "keep_elbows_in",
            "move_only_forearms",
            "finish_extension",
            "keep_shoulders_still",
        ),
    },
    "5": {
        "preferred_view": "side_or_front",
        "primary_signal": "knee_flexion_angle",
        "secondary_signals": ("hip_vertical_displacement", "torso_lean", "knee_tracking", "symmetry"),
        "start_thresholds": {"knee_angle_deg": (160.0, 175.0)},
        "end_thresholds": {
            "knee_angle_deg": (90.0, 120.0),
            "hip_drop": "working_depth",
        },
        "top_faults": ("insufficient_depth", "excessive_forward_lean", "knee_collapse"),
        "coaching_cues": (
            "sit_deeper",
            "chest_up",
            "knees_over_toes",
            "stand_tall",
        ),
    },
}


class TestTechniqueProfiles(unittest.TestCase):
    def test_supported_exercises_have_profiles(self):
        self.assertEqual(set(EXERCISES.keys()), set(EXPECTED_PROFILES.keys()))
        for exercise in EXERCISES.values():
            self.assertIsInstance(exercise.technique_profile, TechniqueProfile)

    def test_profile_fields_match_expected_rules(self):
        for key, expected in EXPECTED_PROFILES.items():
            profile = EXERCISES[key].technique_profile
            self.assertEqual(profile.preferred_view, expected["preferred_view"])
            self.assertEqual(profile.primary_signal, expected["primary_signal"])
            self.assertEqual(profile.secondary_signals, expected["secondary_signals"])
            self.assertEqual(profile.start_thresholds, expected["start_thresholds"])
            self.assertEqual(profile.end_thresholds, expected["end_thresholds"])
            self.assertEqual(profile.top_faults, expected["top_faults"])
            self.assertEqual(profile.coaching_cues, expected["coaching_cues"])
            self.assertTrue(profile.confidence_requirements)

    def test_all_coaching_cues_exist_in_en_and_ar_messages(self):
        for exercise in EXERCISES.values():
            for cue_key in exercise.technique_profile.coaching_cues:
                self.assertIn(cue_key, MESSAGES["en"])
                self.assertIn(cue_key, MESSAGES["ar"])
                self.assertTrue(MESSAGES["en"][cue_key])
                self.assertTrue(MESSAGES["ar"][cue_key])


if __name__ == "__main__":
    unittest.main()
