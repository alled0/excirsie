import unittest

from taharrak.analysis import _profile_feedback
from taharrak.config import get_threshold, load_config, merge_config
from taharrak.exercises import EXERCISES


class _StubTracker:
    def __init__(self, stage="start", rep_elapsed=0.5):
        self.stage = stage
        self.rep_elapsed = rep_elapsed
        self.side = "right"
        self.technique_state = {"faults": (), "signals": {"end_range": (70.0, 95.0)}}


class TestThresholdOverrides(unittest.TestCase):
    def test_missing_config_uses_defaults(self):
        cfg = merge_config({})
        self.assertEqual(get_threshold("lateral_raise", "overheight_warn_deg", cfg), 110.0)

    def test_nested_override_changes_lateral_raise_threshold(self):
        cfg = merge_config({
            "exercise_thresholds": {"lateral_raise": {"overheight_warn_deg": 105.0}}
        })
        self.assertEqual(get_threshold("lateral_raise", "overheight_warn_deg", cfg), 105.0)

    def test_flat_override_still_works(self):
        cfg = merge_config({"lateral_raise_overheight_warn_deg": 108.0})
        self.assertEqual(get_threshold("lateral_raise", "overheight_warn_deg", cfg), 108.0)

    def test_invalid_threshold_value_falls_back_safely(self):
        cfg = merge_config({
            "exercise_thresholds": {"lateral_raise": {"overheight_warn_deg": "not-a-number"}}
        })
        self.assertEqual(get_threshold("lateral_raise", "overheight_warn_deg", cfg), 110.0)

    def test_analysis_reads_same_threshold(self):
        cfg = merge_config({
            "exercise_thresholds": {"lateral_raise": {"overheight_warn_deg": 110.0}}
        })
        tracker = _StubTracker()
        exercise = EXERCISES["3"]
        self.assertIsNone(_profile_feedback(tracker, 100.0, exercise, "GOOD", "en", cfg))
        self.assertIsNotNone(_profile_feedback(tracker, 115.0, exercise, "GOOD", "en", cfg))

    def test_repo_config_loads_threshold_section(self):
        cfg = load_config("config.json")
        self.assertIn("exercise_thresholds", cfg)
        self.assertEqual(cfg["exercise_thresholds"]["lateral_raise"]["overheight_warn_deg"], 110.0)


if __name__ == "__main__":
    unittest.main()
