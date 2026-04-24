import unittest

from taharrak.exercises import EXERCISES
from taharrak.phase import ExercisePhaseFSM


def _run_sequence(exercise_key: str, angles: list[float], cfg: dict | None = None):
    fsm = ExercisePhaseFSM(EXERCISES[exercise_key], cfg or {})
    results = [fsm.update(angle) for angle in angles]
    return fsm, results


class TestPhaseValidation(unittest.TestCase):
    def test_valid_squat_phase_sequence_counts_once(self):
        _, results = _run_sequence("5", [170, 170, 150, 120, 88, 90, 125, 150, 170, 170])
        counted = [result for result in results if result.counted]
        self.assertEqual(len(counted), 1)
        self.assertTrue(counted[0].valid)

    def test_shallow_squat_does_not_count(self):
        _, results = _run_sequence("5", [170, 170, 150, 132, 145, 170, 170])
        counted = [result for result in results if result.counted]
        invalid = [result for result in results if result.invalid_reasons]
        self.assertEqual(counted, [])
        self.assertTrue(invalid)
        self.assertIn("insufficient_depth", invalid[-1].invalid_reasons)

    def test_threshold_bounce_does_not_double_count(self):
        _, results = _run_sequence("1", [165, 165, 120, 70, 38, 38, 70, 120, 165, 165, 164, 165])
        counted = [result for result in results if result.counted]
        self.assertEqual(len(counted), 1)

    def test_valid_curl_counts_once(self):
        _, results = _run_sequence("1", [165, 165, 120, 80, 36, 36, 70, 120, 165, 165])
        counted = [result for result in results if result.counted]
        self.assertEqual(len(counted), 1)

    def test_partial_curl_does_not_count(self):
        _, results = _run_sequence("1", [165, 165, 120, 95, 120, 165, 165])
        counted = [result for result in results if result.counted]
        invalid = [result for result in results if result.invalid_reasons]
        self.assertEqual(counted, [])
        self.assertTrue(invalid)
        self.assertIn("incomplete_rom", invalid[-1].invalid_reasons)

    def test_shoulder_press_without_lockout_does_not_count(self):
        _, results = _run_sequence("2", [85, 85, 105, 135, 150, 135, 95, 85, 85])
        counted = [result for result in results if result.counted]
        invalid = [result for result in results if result.invalid_reasons]
        self.assertEqual(counted, [])
        self.assertTrue(invalid)
        self.assertIn("incomplete_lockout", invalid[-1].invalid_reasons)

    def test_tricep_extension_completes_after_return(self):
        _, results = _run_sequence("4", [75, 75, 110, 145, 168, 168, 150, 110, 75, 75])
        counted = [result for result in results if result.counted]
        self.assertEqual(len(counted), 1)
        self.assertEqual(counted[0].phase, "COMPLETE")


if __name__ == "__main__":
    unittest.main()
