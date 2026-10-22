import unittest

from log_window import LogWindow
from ui_style import button_colors

COLORS = {
    'bg': '#000001',
    'card': '#000002',
    'card_hover': '#000003',
    'border': '#000004',
    'text': '#000005',
    'text_dim': '#000006',
    'text_muted': '#000007',
    'accent': '#000008',
    'on_accent': '#00000d',
    'success': '#000009',
    'error': '#00000a',
    'warning': '#00000b',
    'info': '#00000c',
}


class FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class BrokenWidget:
    def configure(self, **options: object) -> None:
        raise RuntimeError("控件已销毁")


class FakeTextbox:
    def __init__(self) -> None:
        self.tags: dict[str, dict[str, object]] = {}

    def tag_configure(self, tag: str, **options: object) -> None:
        self.tags[tag] = options


class FakeSearch:
    def __init__(self) -> None:
        self.refresh_count = 0

    def refresh_colors(self) -> None:
        self.refresh_count += 1


class ThemeBindingTests(unittest.TestCase):
    def make_window(self) -> tuple[LogWindow, FakeWidget, FakeTextbox, FakeSearch, list[str]]:
        window = object.__new__(LogWindow)
        root = FakeWidget()
        textbox = FakeTextbox()
        search = FakeSearch()
        calls: list[str] = []

        def configure(**options: object) -> None:
            root.configure(**options)

        def setup_blur() -> None:
            calls.append('blur')

        def apply_log_source_ui() -> None:
            calls.append('source')

        def update_status(is_running: bool) -> None:
            calls.append(f'status:{is_running}')

        def get_textbox() -> FakeTextbox:
            return textbox

        window.configure = configure
        window._setup_blur = setup_blur
        window._apply_log_source_ui = apply_log_source_ui
        window.update_status = update_status
        window._get_textbox = get_textbox
        window._search = search
        window._is_running = False
        window.COLORS = COLORS.copy()
        window._theme_bindings = []
        window._styled_buttons = []
        window._ui_ready = True
        return window, root, textbox, search, calls

    def test_bind_theme_records_widget_and_keys(self):
        window, _, _, _, _ = self.make_window()
        widget = FakeWidget()

        window._bind_theme(widget, fg_color='card', text_color='accent')

        self.assertEqual(
            window._theme_bindings,
            [(widget, {'fg_color': 'card', 'text_color': 'accent'})],
        )

    def test_apply_theme_resolves_every_binding(self):
        window, root, _, _, _ = self.make_window()
        widget = FakeWidget()
        window._bind_theme(
            widget,
            fg_color='card',
            hover_color='card_hover',
            text_color='text',
        )

        window._apply_theme()

        self.assertEqual(root.options, {'fg_color': COLORS['bg']})
        self.assertEqual(
            widget.options,
            {
                'fg_color': COLORS['card'],
                'hover_color': COLORS['card_hover'],
                'text_color': COLORS['text'],
            },
        )

    def test_apply_theme_uses_new_colors_on_next_change(self):
        window, _, _, _, _ = self.make_window()
        widget = FakeWidget()
        window._bind_theme(widget, fg_color='card')
        window._apply_theme()

        window.COLORS = {**COLORS, 'card': '#abcdef'}
        window._apply_theme()

        self.assertEqual(widget.options, {'fg_color': '#abcdef'})

    def test_apply_theme_does_nothing_before_ui_is_ready(self):
        window, root, _, _, calls = self.make_window()
        widget = FakeWidget()
        window._bind_theme(widget, fg_color='card')
        window._ui_ready = False

        window._apply_theme()

        self.assertEqual(root.options, {})
        self.assertEqual(widget.options, {})
        self.assertEqual(calls, [])

    def test_apply_theme_refreshes_dynamic_state_after_bindings(self):
        window, _, textbox, search, calls = self.make_window()
        window._is_running = True
        window._bind_theme(FakeWidget(), fg_color='card')

        window._apply_theme()

        self.assertEqual(calls, ['blur', 'source', 'status:True'])
        self.assertEqual(search.refresh_count, 1)
        self.assertEqual(textbox.tags['error']['foreground'], COLORS['error'])
        self.assertEqual(textbox.tags['separator']['foreground'], COLORS['accent'])

    def test_apply_theme_reapplies_button_roles(self):
        window, _, _, _, _ = self.make_window()
        primary = FakeWidget()
        secondary = FakeWidget()
        window._styled_buttons = [(primary, 'primary'), (secondary, 'secondary')]

        window._apply_theme()

        self.assertEqual(primary.options, button_colors('primary', COLORS))
        self.assertEqual(secondary.options, button_colors('secondary', COLORS))

    def test_apply_theme_logs_widget_failures(self):
        window, _, _, _, _ = self.make_window()
        window._bind_theme(BrokenWidget(), fg_color='card')

        with self.assertLogs('log_window', level='ERROR'):
            window._apply_theme()

    def test_blur_change_reruns_setup(self):
        window = object.__new__(LogWindow)
        calls = []
        window._setup_blur = lambda: calls.append('blur')

        window._on_blur_change(False)

        self.assertEqual(calls, ['blur'])


if __name__ == '__main__':
    unittest.main()
