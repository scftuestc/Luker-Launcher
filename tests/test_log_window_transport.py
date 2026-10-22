import unittest
from unittest.mock import patch

from log_window import LogWindow
from theme import shade_color

COLORS = {
    'bg': '#111111',
    'success': '#22aa44',
    'error': '#cc3344',
}


class FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class TransportButtonTests(unittest.TestCase):
    def make_window(self) -> LogWindow:
        window = object.__new__(LogWindow)
        window.COLORS = dict(COLORS)
        window._is_running = False
        window._play_icon = None
        window.play_btn = FakeWidget()
        window.status_dot = FakeWidget()
        window.status_text = FakeWidget()
        return window

    def test_running_switches_to_stop_icon_and_error_color(self):
        window = self.make_window()

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(True)

        self.assertEqual(window.play_btn.options['image'], 'stop:#111111')
        self.assertEqual(window.play_btn.options['fg_color'], COLORS['error'])
        self.assertEqual(
            window.play_btn.options['hover_color'],
            shade_color(COLORS['error'], 0.85),
        )
        self.assertEqual(
            window.status_text.options,
            {'text': '运行中', 'text_color': COLORS['success']},
        )
        self.assertEqual(
            window.status_dot.options,
            {'text_color': COLORS['success']},
        )

    def test_stopped_switches_to_play_icon_and_success_color(self):
        window = self.make_window()
        window._is_running = True

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(False)

        self.assertEqual(window.play_btn.options['image'], 'play:#111111')
        self.assertEqual(window.play_btn.options['fg_color'], COLORS['success'])
        self.assertEqual(
            window.status_text.options,
            {'text': '已停止', 'text_color': COLORS['error']},
        )

    def test_icon_color_follows_theme_background(self):
        window = self.make_window()
        window.COLORS = {**COLORS, 'bg': '#abcdef'}

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(False)

        self.assertEqual(window.play_btn.options['image'], 'play:#abcdef')


if __name__ == '__main__':
    unittest.main()
