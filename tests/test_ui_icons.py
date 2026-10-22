import unittest

from ui_icons import (
    menu_icon,
    render_menu_icon,
    render_theme_icon,
    render_toolbar_icon,
    render_transport_icon,
    theme_icon,
    toolbar_icon,
    transport_icon,
)


class TransportIconTests(unittest.TestCase):
    def test_play_icon_is_transparent_rgba(self):
        image = render_transport_icon('play', '#ffffff', size=64)

        self.assertEqual(image.size, (64, 64))
        self.assertEqual(image.mode, 'RGBA')
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertGreater(image.getchannel('A').getextrema()[1], 0)

    def test_stop_icon_is_transparent_rgba(self):
        image = render_transport_icon('stop', '#ffffff', size=64)

        self.assertEqual(image.size, (64, 64))
        self.assertEqual(image.mode, 'RGBA')
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertGreater(image.getchannel('A').getextrema()[1], 0)

    def test_play_and_stop_shapes_differ(self):
        play = render_transport_icon('play', '#ffffff', size=64)
        stop = render_transport_icon('stop', '#ffffff', size=64)

        self.assertNotEqual(play.tobytes(), stop.tobytes())

    def test_icon_uses_requested_color(self):
        image = render_transport_icon('play', '#ff0000', size=64)
        palette = image.getcolors(maxcolors=64 * 64) or []
        colors = {color[:3] for _, color in palette if color[3] > 0}

        self.assertIn((255, 0, 0), colors)

    def test_transport_icon_uses_logical_size(self):
        icon = transport_icon('play', '#ffffff')

        self.assertEqual(icon.cget('size'), (16, 16))


class MenuIconTests(unittest.TestCase):
    KINDS = ('window', 'play', 'stop', 'refresh', 'globe', 'gcl', 'settings', 'power')

    def test_all_icons_are_transparent_rgba(self):
        for kind in self.KINDS:
            with self.subTest(kind=kind):
                image = render_menu_icon(kind, '#ffffff', size=64)

                self.assertEqual(image.size, (64, 64))
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertGreater(image.getchannel('A').getextrema()[1], 0)

    def test_icons_have_distinct_shapes(self):
        window = render_menu_icon('window', '#ffffff', size=64)
        power = render_menu_icon('power', '#ffffff', size=64)
        play = render_menu_icon('play', '#ffffff', size=64)
        stop = render_menu_icon('stop', '#ffffff', size=64)

        self.assertNotEqual(window.tobytes(), power.tobytes())
        self.assertNotEqual(play.tobytes(), stop.tobytes())

    def test_color_is_applied(self):
        image = render_menu_icon('globe', '#ff0000', size=64)
        palette = image.getcolors(maxcolors=64 * 64) or []
        colors = {color[:3] for _, color in palette if color[3] > 0}

        self.assertIn((255, 0, 0), colors)

    def test_menu_icon_uses_eighteen_pixel_logical_size(self):
        icon = menu_icon('play', '#ffffff')

        self.assertEqual(icon.cget('size'), (18, 18))


class ThemeIconTests(unittest.TestCase):
    KINDS = ('sun', 'moon', 'tree', 'cloud', 'wave', 'rose')

    def test_all_theme_icons_are_transparent_rgba(self):
        for kind in self.KINDS:
            with self.subTest(kind=kind):
                image = render_theme_icon(kind, '#ffffff', size=64)

                self.assertEqual(image.size, (64, 64))
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertGreater(image.getchannel('A').getextrema()[1], 0)

    def test_theme_icons_have_distinct_shapes(self):
        images = [render_theme_icon(kind, '#ffffff', size=64) for kind in self.KINDS]

        for first in range(len(images)):
            for second in range(first + 1, len(images)):
                self.assertNotEqual(images[first].tobytes(), images[second].tobytes())

    def test_theme_icon_uses_requested_color(self):
        image = render_theme_icon('sun', '#ff0000', size=64)
        palette = image.getcolors(maxcolors=64 * 64) or []
        colors = {color[:3] for _, color in palette if color[3] > 0}

        self.assertIn((255, 0, 0), colors)

    def test_theme_icon_uses_eighteen_pixel_size(self):
        icon = theme_icon('sun', '#ffffff')

        self.assertEqual(icon.cget('size'), (18, 18))


class ToolbarIconTests(unittest.TestCase):
    KINDS = ('search', 'trash', 'scroll', 'pause')

    def test_all_toolbar_icons_are_transparent_rgba(self):
        for kind in self.KINDS:
            with self.subTest(kind=kind):
                image = render_toolbar_icon(kind, '#ffffff', size=64)

                self.assertEqual(image.size, (64, 64))
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertGreater(image.getchannel('A').getextrema()[1], 0)

    def test_toolbar_icons_have_distinct_shapes(self):
        images = [render_toolbar_icon(kind, '#ffffff', size=64) for kind in self.KINDS]

        for first in range(len(images)):
            for second in range(first + 1, len(images)):
                self.assertNotEqual(images[first].tobytes(), images[second].tobytes())

    def test_toolbar_icon_uses_requested_color(self):
        image = render_toolbar_icon('search', '#ff0000', size=64)
        palette = image.getcolors(maxcolors=64 * 64) or []
        colors = {color[:3] for _, color in palette if color[3] > 0}

        self.assertIn((255, 0, 0), colors)

    def test_toolbar_icon_uses_sixteen_pixel_size(self):
        icon = toolbar_icon('search', '#ffffff')

        self.assertEqual(icon.cget('size'), (16, 16))


if __name__ == '__main__':
    unittest.main()
