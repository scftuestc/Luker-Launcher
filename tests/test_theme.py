import unittest

from theme import (
    DEFAULT_THEME,
    LEGACY_THEME_ALIASES,
    LOGO_BAR_GLOW_RGB,
    LOGO_BAR_RGB,
    PRESET_THEMES,
    blend_color,
    get_theme_colors,
    is_light_color,
    logo_bar_brightness,
    shade_color,
)

REQUIRED_COLOR_KEYS = (
    "bg",
    "card",
    "card_hover",
    "border",
    "text",
    "text_dim",
    "text_muted",
    "accent",
    "on_accent",
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

    def test_legacy_aliases_point_to_existing_themes(self):
        for legacy, current in LEGACY_THEME_ALIASES.items():
            with self.subTest(legacy=legacy):
                self.assertIn(current, PRESET_THEMES)
                self.assertNotIn(legacy, PRESET_THEMES)

    def test_returned_theme_is_a_copy(self):
        colors = get_theme_colors(DEFAULT_THEME)
        colors["bg"] = "#000000"
        self.assertNotEqual(PRESET_THEMES[DEFAULT_THEME]["bg"], "#000000")


class LogoColorTests(unittest.TestCase):
    def test_brightness_wraps_per_bar(self):
        self.assertAlmostEqual(logo_bar_brightness(0, 0.0), 0.7)
        self.assertEqual(logo_bar_brightness(1, 0.0), logo_bar_brightness(0, 0.25))

    def test_custom_brightness_range(self):
        self.assertAlmostEqual(
            logo_bar_brightness(0, 0.0, center=0.6, amplitude=0.4),
            0.6,
        )
        self.assertAlmostEqual(
            logo_bar_brightness(0, 0.25, center=0.6, amplitude=0.4),
            1.0,
        )
        self.assertAlmostEqual(
            logo_bar_brightness(0, 0.75, center=0.6, amplitude=0.4),
            0.2,
        )

    def test_blend_factor_is_clamped(self):
        self.assertEqual(blend_color((0, 0, 0), (255, 255, 255), 2), "#ffffff")
        self.assertEqual(blend_color((0, 0, 0), (255, 255, 255), -1), "#000000")

    def test_tray_base_scales_from_black(self):
        self.assertEqual(blend_color((0, 0, 0), LOGO_BAR_RGB[0], 0.7), "#b24a4a")

    def test_glow_blends_toward_target(self):
        self.assertEqual(
            blend_color(LOGO_BAR_RGB[0], LOGO_BAR_GLOW_RGB[0], 0.7),
            "#fa6f6f",
        )


class ShadeColorTests(unittest.TestCase):
    def test_darkens_each_channel(self):
        self.assertEqual(shade_color("#3fb950", 0.75), "#2f8b3c")

    def test_clamps_brightness(self):
        self.assertEqual(shade_color("#ffffff", 2), "#ffffff")
        self.assertEqual(shade_color("#000000", 10), "#000000")

    def test_invalid_color_is_returned_unchanged(self):
        self.assertEqual(shade_color("not-a-color", 0.5), "not-a-color")


class LightColorTests(unittest.TestCase):
    def test_light_and_dark_backgrounds(self):
        self.assertTrue(is_light_color(PRESET_THEMES["cloud_gray"]["bg"]))
        self.assertTrue(is_light_color("#ffffff"))
        self.assertFalse(is_light_color(PRESET_THEMES["summer"]["bg"]))
        self.assertFalse(is_light_color("#000000"))

    def test_invalid_color_is_not_light(self):
        self.assertFalse(is_light_color("not-a-color"))
        self.assertFalse(is_light_color("#12345"))


if __name__ == "__main__":
    unittest.main()
