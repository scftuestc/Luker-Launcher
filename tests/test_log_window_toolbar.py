import unittest
from unittest.mock import patch

from log_window import LogWindow, auto_scroll_button_colors


class FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class AutoScrollTests(unittest.TestCase):
    def make_window(self, enabled: bool) -> LogWindow:
        window = object.__new__(LogWindow)
        window.COLORS = {
            'text': '#111111',
            'warning': '#222222',
            'text_muted': '#333333',
            'accent': '#444444',
            'card': '#555555',
            'border': '#666666',
            'text_dim': '#777777',
        }
        window._auto_scroll = enabled
        window.scroll_btn = FakeWidget()
        window._clear_btn = FakeWidget()
        return window

    def test_enabled_uses_scroll_icon_and_accent_colors(self):
        window = self.make_window(True)
        expected = auto_scroll_button_colors(window.COLORS, True)
        expected.update(text='自动滚动', image='scroll:#444444:16')

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._apply_auto_scroll_ui()

        self.assertEqual(window.scroll_btn.options, expected)

    def test_paused_uses_pause_icon_and_warning_colors(self):
        window = self.make_window(False)
        expected = auto_scroll_button_colors(window.COLORS, False)
        expected.update(text='已暂停', image='pause:#222222:16')

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._apply_auto_scroll_ui()

        self.assertEqual(window.scroll_btn.options, expected)

    def test_enabled_and_paused_colors_differ(self):
        window = self.make_window(True)

        enabled = auto_scroll_button_colors(window.COLORS, True)
        paused = auto_scroll_button_colors(window.COLORS, False)

        self.assertNotEqual(enabled['text_color'], paused['text_color'])
        self.assertNotEqual(enabled['border_color'], paused['border_color'])
        self.assertNotEqual(enabled['hover_color'], paused['hover_color'])

    def test_toggle_switches_between_the_two_states(self):
        window = self.make_window(True)

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._toggle_scroll()
            self.assertEqual(window.scroll_btn.options['text'], '已暂停')
            window._toggle_scroll()

        self.assertEqual(window.scroll_btn.options['text'], '自动滚动')
        self.assertTrue(window._auto_scroll)

    def test_refresh_rebuilds_remaining_toolbar_icons(self):
        window = self.make_window(True)

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._refresh_toolbar_icons()

        self.assertEqual(window._clear_btn.options['image'], 'trash:#111111:16')
        self.assertEqual(window.scroll_btn.options['image'], 'scroll:#444444:16')

    def test_refresh_keeps_paused_warning_state(self):
        window = self.make_window(False)

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._refresh_toolbar_icons()

        self.assertEqual(window.scroll_btn.options['text'], '已暂停')
        self.assertEqual(window.scroll_btn.options['text_color'], '#222222')
        self.assertEqual(window.scroll_btn.options['image'], 'pause:#222222:16')


if __name__ == '__main__':
    unittest.main()
