"""
Unit tests for OneEuroFilter and OneEuroLandmarkSmoother.

Run:  python -m pytest tests/ -v
      python -m unittest discover tests/
"""
import math
import unittest

from taharrak.tracker import OneEuroFilter, OneEuroLandmarkSmoother, SmoothedLandmark


class TestOneEuroFilter(unittest.TestCase):

    def test_first_call_passthrough(self):
        """First sample is returned unchanged (no prior state)."""
        f = OneEuroFilter()
        self.assertEqual(f.filter(42.0), 42.0)

    def test_converges_to_constant(self):
        """After many frames of a constant value the output ≈ that value."""
        f = OneEuroFilter(freq=30, min_cutoff=1.5, beta=0.007)
        target = 123.4
        out = 0.0
        for _ in range(200):
            out = f.filter(target, dt=1 / 30)
        self.assertAlmostEqual(out, target, delta=0.1)

    def test_reset_clears_state(self):
        """After reset(), the next call behaves like the first call."""
        f = OneEuroFilter()
        f.filter(100.0)
        f.filter(100.0)
        f.reset()
        # Post-reset: first sample must pass through unfiltered
        self.assertEqual(f.filter(7.0), 7.0)

    def test_high_beta_more_responsive(self):
        """Higher beta → more responsive on a sudden step input."""
        f_hi = OneEuroFilter(freq=30, min_cutoff=1.0, beta=1.0)
        f_lo = OneEuroFilter(freq=30, min_cutoff=1.0, beta=0.0)
        # Warm both filters to 0
        for _ in range(30):
            f_hi.filter(0.0, dt=1 / 30)
            f_lo.filter(0.0, dt=1 / 30)
        # Step to 100
        out_hi = f_hi.filter(100.0, dt=1 / 30)
        out_lo = f_lo.filter(100.0, dt=1 / 30)
        # Higher beta adapts more → larger output on the step frame
        self.assertGreater(out_hi, out_lo)

    def test_smooths_noise(self):
        """Rapid noise around a constant should be attenuated."""
        import random
        rng  = random.Random(0)
        f    = OneEuroFilter(freq=30, min_cutoff=1.5, beta=0.007)
        vals = [50.0 + rng.uniform(-20, 20) for _ in range(200)]
        # Feed all samples
        outputs = [f.filter(v, dt=1 / 30) for v in vals]
        # Variance of output should be much less than variance of input
        def var(seq):
            m = sum(seq) / len(seq)
            return sum((x - m) ** 2 for x in seq) / len(seq)
        self.assertLess(var(outputs), var(vals) * 0.5)

    def test_explicit_dt_accepted(self):
        """Filter should accept explicit dt without errors."""
        f = OneEuroFilter(freq=30)
        f.filter(1.0, dt=0.033)
        f.filter(2.0, dt=0.033)

    def test_alpha_between_zero_and_one(self):
        """Internal _alpha must always return a value in (0, 1)."""
        for cutoff in [0.01, 0.5, 1.0, 5.0, 30.0, 120.0]:
            for dt in [0.001, 0.033, 0.1, 1.0]:
                a = OneEuroFilter._alpha(cutoff, dt)
                self.assertGreater(a, 0.0)
                self.assertLess(a, 1.0)


class TestOneEuroLandmarkSmoother(unittest.TestCase):

    class _FakeLM:
        def __init__(self, x, y, z=0.0, visibility=0.95):
            self.x, self.y, self.z, self.visibility = x, y, z, visibility

    def _make_lm_list(self, val=0.5, n=33):
        return [self._FakeLM(val, val, val) for _ in range(n)]

    def test_returns_smoothed_landmarks(self):
        s   = OneEuroLandmarkSmoother(num_landmarks=33)
        out = s.smooth(self._make_lm_list(0.5))
        self.assertEqual(len(out), 33)
        self.assertIsInstance(out[0], SmoothedLandmark)

    def test_visibility_is_raw(self):
        """Visibility must not be filtered — it should equal the raw input."""
        s   = OneEuroLandmarkSmoother(num_landmarks=33)
        lms = [self._FakeLM(0.5, 0.5, visibility=0.42) for _ in range(33)]
        out = s.smooth(lms)
        self.assertAlmostEqual(out[0].visibility, 0.42, places=5)

    def test_reset_restarts_filters(self):
        """After reset(), the first output equals the input (no history)."""
        s = OneEuroLandmarkSmoother(num_landmarks=2)
        lms = [self._FakeLM(100.0, 100.0), self._FakeLM(100.0, 100.0)]
        for _ in range(50):
            s.smooth(lms)
        s.reset()
        fresh_lms = [self._FakeLM(0.0, 0.0), self._FakeLM(0.0, 0.0)]
        out = s.smooth(fresh_lms)
        self.assertAlmostEqual(out[0].x, 0.0, places=5)


if __name__ == "__main__":
    unittest.main()
