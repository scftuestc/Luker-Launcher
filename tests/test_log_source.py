import unittest

from log_window import LogWindow


class FakeButton:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)


class FakeLabel:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)


class LogSourceUiTests(unittest.TestCase):
    def make_window(self, source: str) -> LogWindow:
        window = object.__new__(LogWindow)
        window._log_source = source
        window.COLORS = {
            'accent': '#111111',
            'warning': '#222222',
            'card_hover': '#333333',
        }
        window._log_source_btn = FakeButton()
        window._title_label = FakeLabel()
        return window

    def test_luker_view(self):
        window = self.make_window('luker')

        window._apply_log_source_ui()

        self.assertEqual(
            window._log_source_btn.options,
            {'text': '📊 Luker 日志', 'fg_color': '#111111', 'hover_color': '#333333'},
        )
        self.assertEqual(window._title_label.options, {'text': 'Luker 日志'})

    def test_gcl_view(self):
        window = self.make_window('gcl')

        window._apply_log_source_ui()

        self.assertEqual(
            window._log_source_btn.options,
            {'text': '🚀 GCL 日志', 'fg_color': '#222222', 'hover_color': '#333333'},
        )
        self.assertEqual(window._title_label.options, {'text': 'GCL 日志'})


if __name__ == '__main__':
    unittest.main()
