from taharrak.eval import _resolve_replay_options


def test_replay_options_downsample_to_target_fps():
    options = _resolve_replay_options(
        {"analysis_target_fps": 15, "analysis_max_width": 720},
        source_fps=30,
    )

    assert options["frame_step"] == 2
    assert options["effective_fps"] == 15
    assert options["max_width"] == 720


def test_replay_options_do_not_upsample_low_fps_video():
    options = _resolve_replay_options(
        {"analysis_target_fps": 15, "analysis_max_width": 720},
        source_fps=10,
    )

    assert options["frame_step"] == 1
    assert options["effective_fps"] == 10


def test_replay_options_ignore_invalid_values():
    options = _resolve_replay_options(
        {"analysis_target_fps": "bad", "analysis_max_width": -10},
        source_fps=0,
    )

    assert options["source_fps"] == 30
    assert options["frame_step"] == 1
    assert options["effective_fps"] == 30
    assert options["max_width"] == 0
