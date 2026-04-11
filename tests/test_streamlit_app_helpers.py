import unittest

import app


class TestStreamlitRuntimeSettings(unittest.TestCase):
    def test_runtime_settings_capture_video_mode_and_segmentation(self):
        settings = app._runtime_settings("2", "ar", True)
        self.assertEqual(settings["exercise_key"], "2")
        self.assertEqual(settings["lang"], "ar")
        self.assertTrue(settings["segmentation_enabled"])
        self.assertEqual(settings["running_mode"], "VIDEO")

    def test_restart_warning_none_when_settings_match(self):
        settings = app._runtime_settings("1", "en", False)
        self.assertIsNone(app._restart_required_message(settings, dict(settings)))

    def test_restart_warning_lists_changed_fields(self):
        requested = app._runtime_settings("2", "ar", False)
        applied = app._runtime_settings("1", "en", True)
        warning = app._restart_required_message(requested, applied)
        self.assertIn("exercise", warning)
        self.assertIn("language", warning)
        self.assertIn("segmentation", warning)


class TestRtcConfigHelpers(unittest.TestCase):
    def test_coerce_urls_accepts_multiline_string(self):
        urls = app._coerce_urls("turn:a.example.com\nturn:b.example.com")
        self.assertEqual(urls, ["turn:a.example.com", "turn:b.example.com"])

    def test_build_rtc_config_falls_back_to_stun_only(self):
        rtc = app._build_rtc_config(secrets={})
        self.assertEqual(len(rtc["iceServers"]), 3)
        self.assertTrue(all("stun:" in server["urls"][0] for server in rtc["iceServers"]))

    def test_build_rtc_config_adds_turn_server_when_secrets_exist(self):
        rtc = app._build_rtc_config(secrets={
            "TURN_URL": "turn:relay.example.com:3478?transport=udp\nturns:relay.example.com:5349",
            "TURN_USERNAME": "user1",
            "TURN_CREDENTIAL": "pass1",
        })
        self.assertEqual(len(rtc["iceServers"]), 4)
        turn_server = rtc["iceServers"][-1]
        self.assertEqual(
            turn_server["urls"],
            ["turn:relay.example.com:3478?transport=udp", "turns:relay.example.com:5349"],
        )
        self.assertEqual(turn_server["username"], "user1")
        self.assertEqual(turn_server["credential"], "pass1")

    def test_connection_help_message_mentions_retry_and_turn(self):
        message = app._connection_help_message().lower()
        self.assertIn("refresh", message)
        self.assertIn("network", message)
        self.assertIn("turn", message)


class TestVideoTimestamps(unittest.TestCase):
    def test_timestamp_uses_frame_time_when_available(self):
        ts = app._next_video_timestamp_ms(None, frame_time_s=1.234)
        self.assertEqual(ts, 1234)

    def test_timestamp_stays_strictly_monotonic(self):
        ts = app._next_video_timestamp_ms(1234, frame_time_s=1.234)
        self.assertEqual(ts, 1235)
        ts = app._next_video_timestamp_ms(1235, monotonic_ns=1_000_000_000)
        self.assertEqual(ts, 1236)


class TestDiagnosticsRows(unittest.TestCase):
    def test_bilateral_rows_include_quality_trust_and_segmentation(self):
        diag = {
            "mode": "VIDEO",
            "segmentation": True,
            "fps": 29.9,
            "dt_ms": 33.4,
            "jitter_ms": 2.1,
            "qualities": ("GOOD", "WEAK"),
            "weak_frac": 0.25,
            "lost_frac": 0.1,
            "recovery_frac": 0.05,
            "trust": {
                "render_allowed": True,
                "counting_sides": (True, False),
                "coaching_sides": (True, False),
            },
        }
        rows = app._diagnostic_rows(diag, bilateral=True)
        self.assertEqual(len(rows), 5)
        self.assertIn("Seg on", rows[0])
        self.assertIn("L GOOD", rows[2])
        self.assertIn("count L on / R off", rows[3])

    def test_unilateral_rows_handle_missing_side_flags(self):
        diag = {
            "mode": "VIDEO",
            "segmentation": False,
            "fps": 30.0,
            "dt_ms": 33.3,
            "jitter_ms": 1.0,
            "qualities": ("GOOD",),
            "weak_frac": 0.0,
            "lost_frac": 0.0,
            "recovery_frac": 0.0,
            "trust": {
                "render_allowed": True,
                "counting_sides": (),
                "coaching_sides": (),
            },
        }
        rows = app._diagnostic_rows(diag, bilateral=False)
        self.assertEqual(len(rows), 5)
        self.assertIn("Seg off", rows[0])
        self.assertIn("count off", rows[3])


if __name__ == "__main__":
    unittest.main()
