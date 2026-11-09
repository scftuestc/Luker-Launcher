import unittest

from PIL import Image, ImageDraw

from luker_launcher.ui.character_art import left_fade_mask, render_character, smoothstep


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


if __name__ == "__main__":
    unittest.main()
