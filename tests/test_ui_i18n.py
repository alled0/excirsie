import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import taharrak.messages as messages
import taharrak.ui as ui
from bicep_curl_counter import load_config


class TestArabicRendering(unittest.TestCase):
    def test_default_arabic_font_path_exists(self):
        cfg = load_config()
        self.assertTrue(Path(cfg["arabic_font_path"]).is_file())

    def test_put_uses_shared_text_context(self):
        frame = np.zeros((120, 240, 3), dtype=np.uint8)
        font_path = load_config()["arabic_font_path"]
        ui.set_text_context("ar", font_path)

        with patch.object(ui, "put_text") as mocked:
            ui.put(frame, "مرحبا", (20, 40))

        self.assertEqual(mocked.call_args.args[6], "ar")
        self.assertEqual(mocked.call_args.args[7], font_path)

    @unittest.skipUnless(messages._AR_OK, "Arabic rendering dependencies unavailable")
    def test_put_text_draws_arabic_with_valid_font(self):
        frame = np.zeros((120, 240, 3), dtype=np.uint8)
        font_path = load_config()["arabic_font_path"]

        messages.put_text(frame, "مرحبا", (20, 50), lang="ar", font_path=font_path)

        self.assertGreater(int(frame.sum()), 0)


if __name__ == "__main__":
    unittest.main()
