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

    def test_bundled_deepseek_assets_exist_with_expected_sizes(self):
        card = theme_assets.load_theme_image(DEEPSEEK_CARD)
        character = theme_assets.load_theme_image(DEEPSEEK_CHARACTER)

        self.assertIsNotNone(card)
        self.assertIsNotNone(character)
        self.assertEqual(card.size, (320, 320))
        self.assertEqual(character.size, (528, 704))
        self.assertEqual(card.mode, "RGBA")
        self.assertEqual(character.mode, "RGBA")
        self.assertEqual(card.getchannel("A").getextrema(), (0, 255))
        self.assertEqual(character.getchannel("A").getextrema(), (0, 255))

    def test_card_art_fades_out_on_all_four_edges(self):
        card = theme_assets.load_theme_image(DEEPSEEK_CARD)
        self.assertIsNotNone(card)
        alpha = card.getchannel("A")

        for point in ((0, 160), (319, 160), (160, 0), (160, 319)):
            self.assertLessEqual(alpha.getpixel(point), 4, point)
        self.assertGreater(alpha.getpixel((160, 160)), 200)

    def test_character_art_has_rounded_transparent_corners(self):
        character = theme_assets.load_theme_image(DEEPSEEK_CHARACTER)
        self.assertIsNotNone(character)
        alpha = character.getchannel("A")

        for point in ((0, 0), (527, 0), (0, 703), (527, 703)):
            self.assertEqual(alpha.getpixel(point), 0, point)
        self.assertGreater(alpha.getpixel((264, 352)), 200)


if __name__ == "__main__":
    unittest.main()
