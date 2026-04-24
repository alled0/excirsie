import importlib.util
import unittest
from pathlib import Path

from taharrak.config import get_threshold
from taharrak.exercises import EXERCISES
from taharrak.eval import _load_cfg
from taharrak.tracker import OneEuroLandmarkSmoother, RepTracker
from tests.helpers_pose import make_lateral_raise_landmarks


def _load_model_service_module():
    module_path = Path("web/model-service/main.py").resolve()
    spec = importlib.util.spec_from_file_location("taharrak_model_service_main", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Voice:
    def say(self, *args, **kwargs):
        pass


def _build_test_session(exercise_key: str):
    exercise = EXERCISES[exercise_key]
    cfg = _load_cfg("config.json")
    cfg["camera_fps"] = 30
    trackers = (
        [RepTracker("left", exercise, cfg), RepTracker("right", exercise, cfg)]
        if exercise.bilateral else [RepTracker("center", exercise, cfg)]
    )
    return {
        "exercise": exercise,
        "trackers": trackers,
        "smoother": OneEuroLandmarkSmoother(
            num_landmarks=33,
            freq=30.0,
            min_cutoff=cfg.get("one_euro_min_cutoff", 1.5),
            beta=cfg.get("one_euro_beta", 0.007),
        ),
        "cfg": cfg,
        "voice": _Voice(),
        "frames_total": 0,
        "frames_detected": 0,
        "reliability_sum": 0.0,
    }


class TestModelServiceImport(unittest.TestCase):
    def test_missing_config_file_does_not_crash_loader(self):
        cfg = _load_cfg("definitely-missing-config.json")
        self.assertIn("exercise_thresholds", cfg)
        self.assertEqual(get_threshold("lateral_raise", "overheight_warn_deg", cfg), 110.0)

    def test_model_service_module_imports(self):
        module = _load_model_service_module()

        self.assertTrue(hasattr(module, "app"))
        self.assertIn("exercise_thresholds", module._cfg)

    def test_live_landmark_handler_preserves_schema_and_uses_kinematics_path(self):
        module = _load_model_service_module()
        session = _build_test_session("3")

        response = module._process_landmarks(
            session,
            make_lateral_raise_landmarks(115.0),
            (1280, 720),
        )

        for key in ("detected", "reps_total", "reps_left", "reps_right", "quality", "feedback", "severity", "angles"):
            self.assertIn(key, response)
        self.assertEqual(response["processing_path"], "kinematics")
        self.assertTrue(all(path == "kinematics" for path in response["processing_paths"]))
        self.assertEqual(len(response["phases"]), 2)
        self.assertEqual(len(response["landmarks"]), 33)
        self.assertTrue(any("raising_too_high" in faults for faults in response["faults"]))
        self.assertIn("shoulder height", response["feedback"].lower())

    def test_live_landmark_handler_uses_110_degree_lateral_raise_default(self):
        module = _load_model_service_module()
        session = _build_test_session("3")

        response = module._process_landmarks(
            session,
            make_lateral_raise_landmarks(100.0),
            (1280, 720),
        )

        self.assertEqual(response["processing_path"], "kinematics")
        self.assertEqual(len(response["landmarks"]), 33)
        self.assertFalse(any("raising_too_high" in faults for faults in response["faults"]))


if __name__ == "__main__":
    unittest.main()
