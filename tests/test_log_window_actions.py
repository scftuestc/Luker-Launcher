import unittest
from types import SimpleNamespace

from log_window import LogWindow


class LogWindowActionTests(unittest.TestCase):
    def make_window(self, *, tray_available: bool = True) -> tuple[LogWindow, list[str]]:
        window = object.__new__(LogWindow)
        window._tray_available = tray_available
        calls: list[str] = []
        window.hide = lambda: calls.append('hide')
        window.on_hide_callback = lambda: calls.append('hide_callback')
        window.on_exit_callback = None
        return window, calls

    def test_minimize_hides_to_tray(self):
        window, calls = self.make_window()

        window._on_minimize()

        self.assertEqual(calls, ['hide', 'hide_callback'])

    def test_minimize_is_ignored_without_tray(self):
        window, calls = self.make_window(tray_available=False)

        window._on_minimize()

        self.assertEqual(calls, [])

    def test_close_calls_exit_callback_instead_of_hiding(self):
        window, calls = self.make_window()
        window.on_exit_callback = lambda: calls.append('exit')

        window._on_close()

        self.assertEqual(calls, ['exit'])

    def test_close_without_exit_callback_hides_when_tray_available(self):
        window, calls = self.make_window()

        window._on_close()

        self.assertEqual(calls, ['hide', 'hide_callback'])

    def test_close_without_exit_callback_uses_hide_callback_without_tray(self):
        window, calls = self.make_window(tray_available=False)

        window._on_close()

        self.assertEqual(calls, ['hide_callback'])

    def test_show_resets_minimized_flag(self):
        window = object.__new__(LogWindow)
        window._was_minimized = True
        window._logs = SimpleNamespace(on_show=lambda: None)
        for method in ('deiconify', 'lift', 'focus_force'):
            setattr(window, method, lambda: None)

        window.show()

        self.assertFalse(window._was_minimized)


if __name__ == '__main__':
    unittest.main()
