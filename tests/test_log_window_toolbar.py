import unittest
from unittest.mock import patch

from log_window import LogWindow


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
        }
        window._auto_scroll = enabled
        window.scroll_btn = FakeWidget()
        window._clear_btn = FakeWidget()
        return window

    def test_enabled_uses_scroll_icon_and_normal_text(self):
        window = self.make_window(True)

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._apply_auto_scroll_ui()

        self.assertEqual(
            window.scroll_btn.options,
            {
                'text': '自动滚动',
                'text_color': '#111111',
                'image': 'scroll:#111111:16',
            },
        )

    def test_paused_uses_pause_icon_and_warning_text(self):
        window = self.make_window(False)

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._apply_auto_scroll_ui()

        self.assertEqual(
            window.scroll_btn.options,
            {
                'text': '已暂停',
                'text_color': '#222222',
                'image': 'pause:#222222:16',
            },
        )

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
        self.assertEqual(window.scroll_btn.options['image'], 'scroll:#111111:16')

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
