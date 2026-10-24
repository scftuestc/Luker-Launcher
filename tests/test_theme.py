import math
import unittest

from theme import (
    DEFAULT_THEME,
    LEGACY_THEME_ALIASES,
    LOGO_BAR_COLORS,
    LOGO_BAR_RGB,
    LOGO_STOPPED_COLOR,
    PRESET_THEMES,
    THEME_SWATCH_KEYS,
    _parse_hex_color,
    blend_color,
    get_theme_colors,
    is_light_color,
    logo_bar_brightness,
    logo_bar_glow_color,
    mix_color,
    shade_color,
    theme_swatch_colors,
)
from ui_icons import THEME_ICON_KINDS

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


class LogoGlowColorTests(unittest.TestCase):
    def test_stopped_color_matches_tray_icon(self):
        self.assertEqual(LOGO_STOPPED_COLOR, '#6e7681')

    def test_glow_dims_to_forty_percent(self):
        self.assertEqual(
            logo_bar_glow_color(0, 0.75),
            shade_color(LOGO_BAR_COLORS[0], 0.4),
        )

    def test_glow_peaks_at_base_color(self):
        self.assertEqual(logo_bar_glow_color(0, 0.25), LOGO_BAR_COLORS[0])

    def test_glow_range_is_visible_on_every_bar(self):
        def channels(color: str) -> tuple[int, int, int]:
            return (
                int(color[1:3], 16),
                int(color[3:5], 16),
                int(color[5:7], 16),
            )

        for index in range(4):
            with self.subTest(index=index):
                samples = [channels(logo_bar_glow_color(index, phase / 20)) for phase in range(20)]
                channel_ranges = [
                    max(sample[channel] for sample in samples)
                    - min(sample[channel] for sample in samples)
                    for channel in range(3)
                ]
                self.assertGreater(max(channel_ranges), 100)


class ShadeColorTests(unittest.TestCase):
    def test_darkens_each_channel(self):
        self.assertEqual(shade_color("#3fb950", 0.75), "#2f8b3c")

    def test_clamps_brightness(self):
        self.assertEqual(shade_color("#ffffff", 2), "#ffffff")
        self.assertEqual(shade_color("#000000", 10), "#000000")

    def test_invalid_color_is_returned_unchanged(self):
        self.assertEqual(shade_color("not-a-color", 0.5), "not-a-color")


class MixColorTests(unittest.TestCase):
    def test_blends_channels(self):
        self.assertEqual(mix_color("#000000", "#ffffff", 0.5), "#808080")
        self.assertEqual(mix_color("#ff0000", "#0000ff", 0.5), "#800080")

    def test_ratio_is_clamped(self):
        self.assertEqual(mix_color("#102030", "#ffffff", 2), "#ffffff")
        self.assertEqual(mix_color("#102030", "#ffffff", -1), "#102030")

    def test_invalid_colors_return_base(self):
        self.assertEqual(mix_color("not-a-color", "#ffffff", 0.5), "not-a-color")
        self.assertEqual(mix_color("#102030", "not-a-color", 0.5), "#102030")


class LightColorTests(unittest.TestCase):
    def test_light_and_dark_backgrounds(self):
        self.assertTrue(is_light_color(PRESET_THEMES["cloud_gray"]["bg"]))
        self.assertTrue(is_light_color("#ffffff"))
        self.assertFalse(is_light_color(PRESET_THEMES["summer"]["bg"]))
        self.assertFalse(is_light_color("#000000"))

    def test_invalid_color_is_not_light(self):
        self.assertFalse(is_light_color("not-a-color"))
        self.assertFalse(is_light_color("#12345"))


def _srgb_to_lab(color: str) -> tuple[float, float, float]:
    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (
        linear(int(color[1:3], 16) / 255),
        linear(int(color[3:5], 16) / 255),
        linear(int(color[5:7], 16) / 255),
    )
    x = (red * 0.4124 + green * 0.3576 + blue * 0.1805) / 0.95047
    y = red * 0.2126 + green * 0.7152 + blue * 0.0722
    z = (red * 0.0193 + green * 0.1192 + blue * 0.9505) / 1.08883

    def f(value: float) -> float:
        return value ** (1 / 3) if value > 0.008856 else 7.787 * value + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _delta_e(first: str, second: str) -> float:
    return math.dist(_srgb_to_lab(first), _srgb_to_lab(second))


class ThemeSwatchTests(unittest.TestCase):
    def test_every_theme_has_four_distinct_valid_colors(self):
        for name in PRESET_THEMES:
            with self.subTest(theme=name):
                swatches = theme_swatch_colors(name)
                self.assertEqual(len(swatches), 4)
                self.assertEqual(len(set(swatches)), 4)
                for color in swatches:
                    self.assertRegex(color, r'^#[0-9a-f]{6}$')

    def test_swatches_are_perceptually_distinct(self):
        for name in PRESET_THEMES:
            with self.subTest(theme=name):
                swatches = theme_swatch_colors(name)
                distances = [
                    _delta_e(swatches[first], swatches[second])
                    for first in range(4)
                    for second in range(first + 1, 4)
                ]
                self.assertGreaterEqual(min(distances), 25)

    def test_unknown_theme_uses_default_swatches(self):
        self.assertEqual(
            theme_swatch_colors('not-a-theme'),
            theme_swatch_colors(DEFAULT_THEME),
        )

    def test_every_theme_defines_swatch_keys(self):
        for name, theme in PRESET_THEMES.items():
            with self.subTest(theme=name):
                keys = THEME_SWATCH_KEYS[name]
                self.assertEqual(len(keys), 4)
                for key in keys:
                    if key != 'deep':
                        self.assertIn(key, theme)

    def test_theme_icons_are_known_kinds(self):
        for name, theme in PRESET_THEMES.items():
            with self.subTest(theme=name):
                self.assertIn(theme['icon'], THEME_ICON_KINDS)


class HexColorParseTests(unittest.TestCase):
    def test_parses_valid_rgb_hex(self):
        self.assertEqual(_parse_hex_color('#aabbcc'), (0xAA, 0xBB, 0xCC))
        self.assertEqual(_parse_hex_color('#000000'), (0, 0, 0))

    def test_rejects_invalid_values(self):
        self.assertIsNone(_parse_hex_color('aabbcc'))
        self.assertIsNone(_parse_hex_color('#abc'))
        self.assertIsNone(_parse_hex_color('#zzzzzz'))


if __name__ == "__main__":
    unittest.main()
