import unittest
from types import SimpleNamespace
from unittest.mock import patch

from log_window import LogWindow


class FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class FakeHint:
    def __init__(self) -> None:
        self.place_calls: list[dict[str, object]] = []
        self.hidden = 0

    def place(self, **options: object) -> None:
        self.place_calls.append(options)

    def place_forget(self) -> None:
        self.hidden += 1


class FakeVar:
    def __init__(self, value: str = '') -> None:
        self.value = value

    def get(self) -> str:
        return self.value


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
        window._search_icon = FakeWidget()
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

    def test_refresh_rebuilds_all_toolbar_icons(self):
        window = self.make_window(True)

        with patch(
            'log_window.toolbar_icon',
            side_effect=lambda kind, color, size=16: f'{kind}:{color}:{size}',
        ):
            window._refresh_toolbar_icons()

        self.assertEqual(window._clear_btn.options['image'], 'trash:#111111:16')
        self.assertEqual(window._search_icon.options['image'], 'search:#333333:16')
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


class SearchHintTests(unittest.TestCase):
    def make_window(self, value: str = '', focused: bool = False) -> LogWindow:
        window = object.__new__(LogWindow)
        window._search_focused = focused
        window._search_var = FakeVar(value)
        window._search_entry = object()
        window._search_hint = FakeHint()
        window._get_widget_scaling = lambda: 1.0
        return window

    def test_empty_and_unfocused_shows_hint_over_entry(self):
        window = self.make_window()

        window._update_search_hint()

        self.assertEqual(window._search_hint.hidden, 0)
        self.assertEqual(
            window._search_hint.place_calls,
            [
                {
                    'in_': window._search_entry,
                    'x': 6,
                    'rely': 0.5,
                    'anchor': 'w',
                }
            ],
        )
        self.assertEqual(window._search_var.get(), '')

    def test_non_empty_text_hides_hint(self):
        window = self.make_window('luker')

        window._update_search_hint()

        self.assertEqual(window._search_hint.place_calls, [])
        self.assertEqual(window._search_hint.hidden, 1)

    def test_focused_entry_hides_hint(self):
        window = self.make_window(focused=True)

        window._update_search_hint()

        self.assertEqual(window._search_hint.place_calls, [])
        self.assertEqual(window._search_hint.hidden, 1)

    def test_focus_handlers_toggle_hint(self):
        window = self.make_window()

        window._on_search_focus_in()
        self.assertTrue(window._search_focused)
        self.assertEqual(window._search_hint.hidden, 1)

        window._on_search_focus_out()
        self.assertFalse(window._search_focused)
        self.assertEqual(len(window._search_hint.place_calls), 1)


class SearchClearTests(unittest.TestCase):
    def test_clear_search_clears_state_once(self):
        window = object.__new__(LogWindow)
        calls: list[str] = []
        var = SimpleNamespace(value='luker')
        var.get = lambda: var.value
        var.set = lambda value: setattr(var, 'value', value)
        window._search_job = None
        window._search_clearing = False
        window._search_var = var
        window._search = SimpleNamespace(clear_state=lambda: calls.append('clear'))
        window._search_entry = SimpleNamespace(focus_set=lambda: calls.append('focus'))
        window._update_search_hint = lambda: calls.append('hint')

        window._clear_search()

        self.assertEqual(calls, ['clear', 'hint', 'focus'])
        self.assertEqual(var.value, '')


if __name__ == '__main__':
    unittest.main()
