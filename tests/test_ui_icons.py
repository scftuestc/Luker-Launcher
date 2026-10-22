import unittest

from ui_icons import render_menu_icon, render_transport_icon, transport_icon


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


if __name__ == '__main__':
    unittest.main()
