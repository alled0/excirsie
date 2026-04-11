import unittest

from bicep_curl_counter import _KEY_DOWN, _KEY_ENTER, _KEY_UP, key_matches


class TestInputKeys(unittest.TestCase):
    def test_weight_input_accepts_short_and_extended_up_keys(self):
        self.assertTrue(key_matches(82, *_KEY_UP))
        self.assertTrue(key_matches(2490368, *_KEY_UP))

    def test_weight_input_accepts_short_and_extended_down_keys(self):
        self.assertTrue(key_matches(84, *_KEY_DOWN))
        self.assertTrue(key_matches(2621440, *_KEY_DOWN))

    def test_confirm_keys_include_space_and_enter(self):
        self.assertTrue(key_matches(ord(" "), ord(" "), *_KEY_ENTER))
        self.assertTrue(key_matches(13, ord(" "), *_KEY_ENTER))

    def test_negative_key_does_not_match(self):
        self.assertFalse(key_matches(-1, *_KEY_UP))


if __name__ == "__main__":
    unittest.main()
