import unittest

from taharrak.analysis import _FAULT_RULES
from taharrak.config import get_threshold, merge_config
from taharrak.correction import FAULT_PRIORITY
from taharrak.exercises import EXERCISES
from taharrak.faults.rules import FAULT_RULES
from taharrak.messages import MESSAGES


class TestProfileFaultAudit(unittest.TestCase):
    def test_declared_profile_faults_are_supported_by_fault_engine(self):
        for key, exercise in EXERCISES.items():
            with self.subTest(exercise=exercise.name):
                profile = exercise.technique_profile
                declared = set(profile.top_faults if profile else ())
                computed = {rule.fault for rule in FAULT_RULES.get(key, ())}
                self.assertTrue(
                    declared.issubset(computed),
                    f"{exercise.name} declares unsupported faults: {sorted(declared - computed)}",
                )

    def test_computed_faults_have_thresholds_priorities_and_bilingual_messages(self):
        cfg = merge_config({})
        for key, rules in FAULT_RULES.items():
            for rule in rules:
                with self.subTest(exercise=key, fault=rule.fault):
                    self.assertIn(rule.fault, FAULT_PRIORITY)
                    self.assertIn(rule.fault, _FAULT_RULES[key])
                    cue_key = rule.message_key or _FAULT_RULES[key][rule.fault][0]
                    self.assertIn(cue_key, MESSAGES["en"])
                    self.assertIn(cue_key, MESSAGES["ar"])
                    if rule.threshold_key is not None and rule.fault != "shrugging":
                        threshold = get_threshold(rule.exercise, rule.threshold_key, cfg)
                        self.assertIsInstance(threshold, float)


if __name__ == "__main__":
    unittest.main()
