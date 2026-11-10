import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

from luker_launcher.ui.character_art import (
    left_fade_mask,
    render_character,
    render_character_with_motto,
    resolve_motto_font_file,
    smoothstep,
    split_motto_lines,
)


class SmoothstepTests(unittest.TestCase):
    def test_endpoints_and_midpoint(self):
        self.assertEqual(smoothstep(-1), 0)
        self.assertEqual(smoothstep(0), 0)
        self.assertAlmostEqual(smoothstep(0.5), 0.5)
        self.assertEqual(smoothstep(1), 1)
        self.assertEqual(smoothstep(2), 1)


class LeftFadeMaskTests(unittest.TestCase):
    def test_left_is_transparent_and_right_is_opaque(self):
        mask = left_fade_mask((20, 10), 0.2)

        self.assertEqual(mask.getpixel((0, 5)), 0)
        self.assertEqual(mask.getpixel((3, 5)), 215)
        self.assertEqual(mask.getpixel((4, 5)), 255)
        self.assertEqual(mask.getpixel((19, 5)), 255)

    def test_zero_ratio_keeps_everything_opaque(self):
        mask = left_fade_mask((10, 4), 0)

        self.assertEqual(mask.getpixel((0, 0)), 255)


class RenderCharacterTests(unittest.TestCase):
    def test_uses_physical_size_and_fades_left(self):
        source = Image.new("RGBA", (20, 10), (10, 20, 30, 255))

        rendered = render_character(source, (10, 5), 2.0, fade_ratio=0.2)

        self.assertEqual(rendered.size, (20, 10))
        alpha = rendered.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 5)), 0)
        self.assertGreater(alpha.getpixel((2, 5)), 0)
        self.assertEqual(alpha.getpixel((19, 5)), 255)

    def test_does_not_modify_the_shared_source(self):
        source = Image.new("RGBA", (20, 10), (10, 20, 30, 255))

        render_character(source, (20, 10), 1.0, fade_ratio=0.2)

        self.assertEqual(source.getchannel("A").getpixel((0, 5)), 255)

    def test_preserves_transparent_rounded_corner(self):
        source = Image.new("RGBA", (20, 20), (10, 20, 30, 255))
        mask = Image.new("L", (20, 20), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 19, 19), radius=6, fill=255)
        source.putalpha(mask)

        rendered = render_character(source, (20, 20), 1.0)

        self.assertEqual(rendered.getchannel("A").getpixel((19, 0)), 0)
        self.assertEqual(rendered.getchannel("A").getpixel((19, 10)), 255)


class MottoFontTests(unittest.TestCase):
    def test_missing_font_returns_none(self):
        with patch(
            "luker_launcher.ui.character_art.ImageFont.truetype",
            side_effect=OSError("missing"),
        ):
            self.assertIsNone(resolve_motto_font_file("华文行楷"))

    def test_known_family_resolves_when_installed(self):
        font = resolve_motto_font_file("华文行楷")
        if font is None:
            self.skipTest("当前系统没有华文行楷")
        self.assertTrue(font)


class MottoLayoutTests(unittest.TestCase):
    def _font(self) -> ImageFont.FreeTypeFont:
        file = resolve_motto_font_file("Microsoft YaHei")
        if file is None:
            self.skipTest("当前系统没有可用的中文字体")
        return ImageFont.truetype(file, 15)

    def test_split_motto_lines_balances_two_lines(self):
        font = self._font()
        draw = ImageDraw.Draw(Image.new("RGBA", (300, 100)))
        text = "我有点笨拙，却愿意一遍遍陪你改到顺眼为止。"

        lines = split_motto_lines(text, draw, font, 200)

        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertLessEqual(draw.textlength(line, font=font), 200)

    def test_overlay_adds_scrim_and_keeps_left_fade(self):
        font_file = resolve_motto_font_file("Microsoft YaHei")
        if font_file is None:
            self.skipTest("当前系统没有可用的中文字体")
        source = Image.new("RGBA", (240, 300), (20, 30, 40, 255))

        plain = render_character(source, (240, 300), 1.0)
        rendered = render_character_with_motto(
            source,
            (240, 300),
            1.0,
            "我有点笨拙，却愿意一遍遍陪你改到顺眼为止。",
            font_file,
            "#eaf4ff",
            font_size=15,
        )

        self.assertEqual(rendered.size, (240, 300))
        self.assertEqual(rendered.getchannel("A").getpixel((0, 150)), 0)
        self.assertLess(
            sum(rendered.getpixel((120, 290))[:3]),
            sum(plain.getpixel((120, 290))[:3]),
        )
        self.assertEqual(rendered.getpixel((120, 20)), plain.getpixel((120, 20)))


if __name__ == "__main__":
    unittest.main()
