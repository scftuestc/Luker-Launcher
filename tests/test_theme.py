import unittest

from theme import DEFAULT_THEME, PRESET_THEMES, get_theme_colors

REQUIRED_COLOR_KEYS = (
    "bg",
    "card",
    "card_hover",
    "border",
    "text",
    "text_dim",
    "text_muted",
    "accent",
    "accent_blue",
    "success",
    "error",
    "warning",
    "info",
)


class ThemeTests(unittest.TestCase):
    def test_default_theme_exists(self):
        self.assertIn(DEFAULT_THEME, PRESET_THEMES)

    def test_all_themes_have_colors_and_metadata(self):
        for name, theme in PRESET_THEMES.items():
            with self.subTest(theme=name):
                for key in REQUIRED_COLOR_KEYS:
                    self.assertIn(key, theme)
                self.assertTrue(theme["name"])
                self.assertTrue(theme["short_name"])
                self.assertTrue(theme["icon"])

    def test_invalid_theme_falls_back_to_default(self):
        colors = get_theme_colors("not-a-theme")
        self.assertEqual(colors, PRESET_THEMES[DEFAULT_THEME])

    def test_returned_theme_is_a_copy(self):
        colors = get_theme_colors(DEFAULT_THEME)
        colors["bg"] = "#000000"
        self.assertNotEqual(PRESET_THEMES[DEFAULT_THEME]["bg"], "#000000")


if __name__ == "__main__":
    unittest.main()
