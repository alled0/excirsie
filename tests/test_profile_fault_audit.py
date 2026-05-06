import unittest

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
                    # message_key is the single source of truth now that _FAULT_RULES
                    # in analysis.py has been removed and severity/signal_kind live on FaultRule.
                    self.assertIsNotNone(rule.message_key,
                                         f"{rule.fault} has no message_key on its FaultRule")
                    self.assertIn(rule.message_key, MESSAGES["en"])
                    self.assertIn(rule.message_key, MESSAGES["ar"])
                    if rule.threshold_key is not None and rule.fault != "shrugging":
                        threshold = get_threshold(rule.exercise, rule.threshold_key, cfg)
                        self.assertIsInstance(threshold, float)

    def test_fault_rules_have_severity_and_signal_kind(self):
        """Every FaultRule now carries severity and signal_kind for the HUD layer."""
        valid_severities = {"error", "warning"}
        valid_kinds = {"primary_signal", "secondary_signals"}
        for key, rules in FAULT_RULES.items():
            for rule in rules:
                with self.subTest(exercise=key, fault=rule.fault):
                    self.assertIn(rule.severity, valid_severities)
                    self.assertIn(rule.signal_kind, valid_kinds)


if __name__ == "__main__":
    unittest.main()
