import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from luker_launcher.ui import theme_assets

DEEPSEEK_CARD = "luker_launcher/assets/deepseek/card.png"
DEEPSEEK_CHARACTER = "luker_launcher/assets/deepseek/character.png"


class ThemeAssetTests(unittest.TestCase):
    def tearDown(self):
        theme_assets.load_theme_image.cache_clear()

    def test_loads_rgba_image_and_caches_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.png"
            Image.new("RGBA", (4, 6), (1, 2, 3, 128)).save(path)

            with patch.object(theme_assets, "resource_path", return_value=path) as resource:
                first = theme_assets.load_theme_image("sample.png")
                second = theme_assets.load_theme_image("sample.png")

        self.assertIs(first, second)
        self.assertIsNotNone(first)
        self.assertEqual(first.mode, "RGBA")
        self.assertEqual(first.size, (4, 6))
        resource.assert_called_once_with("sample.png")

    def test_missing_file_returns_none_and_logs_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.png"
            with (
                patch.object(theme_assets, "resource_path", return_value=path),
                self.assertLogs("luker_launcher.ui.theme_assets", level="WARNING"),
            ):
                self.assertIsNone(theme_assets.load_theme_image("missing.png"))

    def test_corrupt_image_returns_none_and_logs_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.png"
            path.write_bytes(b"not an image")
            with (
                patch.object(theme_assets, "resource_path", return_value=path),
                self.assertLogs("luker_launcher.ui.theme_assets", level="WARNING"),
            ):
                self.assertIsNone(theme_assets.load_theme_image("broken.png"))

    def test_unexpected_errors_are_not_swallowed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.png"
            path.write_bytes(b"placeholder")
            with (
                patch.object(theme_assets, "resource_path", return_value=path),
                patch.object(theme_assets.Image, "open", side_effect=RuntimeError("bug")),
                self.assertRaises(RuntimeError),
            ):
                theme_assets.load_theme_image("sample.png")

    def test_empty_path_returns_none(self):
        self.assertIsNone(theme_assets.load_theme_image(None))
        self.assertIsNone(theme_assets.load_theme_image(""))

    def test_theme_helpers_read_metadata(self):
        theme = {"card_image": "card.png", "log_image": "character.png"}

        with patch.object(theme_assets, "load_theme_image", side_effect=lambda path: path):
            self.assertEqual(theme_assets.theme_card_image(theme), "card.png")
            self.assertEqual(theme_assets.theme_log_image(theme), "character.png")
            self.assertIsNone(theme_assets.theme_card_image({}))
            self.assertIsNone(theme_assets.theme_log_image({}))

    def test_bundled_deepseek_assets_have_expected_shape(self):
        card = theme_assets.load_theme_image(DEEPSEEK_CARD)
        character = theme_assets.load_theme_image(DEEPSEEK_CHARACTER)

        self.assertIsNotNone(card)
        self.assertIsNotNone(character)
        self.assertGreaterEqual(card.width, 256)
        self.assertLessEqual(card.width, 512)
        self.assertLessEqual(abs(card.width - card.height), 2)
        self.assertGreaterEqual(character.width, 384)
        self.assertLessEqual(character.width, 768)
        self.assertAlmostEqual(character.width / character.height, 3 / 4, delta=0.02)
        self.assertEqual(card.mode, "RGBA")
        self.assertEqual(character.mode, "RGBA")
        self.assertGreaterEqual(card.getchannel("A").getextrema()[1], 200)
        self.assertGreaterEqual(character.getchannel("A").getextrema()[1], 200)

    def test_card_art_fades_out_on_all_four_edges(self):
        card = theme_assets.load_theme_image(DEEPSEEK_CARD)
        self.assertIsNotNone(card)
        alpha = card.getchannel("A")
        width, height = card.size

        for point in (
            (0, height // 2),
            (width - 1, height // 2),
            (width // 2, 0),
            (width // 2, height - 1),
        ):
            self.assertLessEqual(alpha.getpixel(point), 16, point)
        self.assertGreater(alpha.getpixel((width // 2, height // 2)), 200)

    def test_character_art_has_rounded_transparent_corners(self):
        character = theme_assets.load_theme_image(DEEPSEEK_CHARACTER)
        self.assertIsNotNone(character)
        alpha = character.getchannel("A")
        width, height = character.size

        for point in (
            (0, 0),
            (width - 1, 0),
            (0, height - 1),
            (width - 1, height - 1),
        ):
            self.assertLessEqual(alpha.getpixel(point), 8, point)
        self.assertGreater(alpha.getpixel((width // 2, height // 2)), 200)


if __name__ == "__main__":
    unittest.main()
