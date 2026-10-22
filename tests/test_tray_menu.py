import unittest
from types import SimpleNamespace
from unittest.mock import patch

import tray_menu
from tray_menu import TrayMenu


class BlurChangeTests(unittest.TestCase):
    def test_blur_change_applies_when_window_exists(self):
        window = object.__new__(TrayMenu)
        window.winfo_exists = lambda: True
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(False)

        self.assertEqual(calls, [True])

    def test_blur_change_ignored_when_window_destroyed(self):
        window = object.__new__(TrayMenu)
        window.winfo_exists = lambda: False
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(False)

        self.assertEqual(calls, [])

    def test_setup_blur_reads_config(self):
        window = object.__new__(TrayMenu)
        window.COLORS = {'bg': '#112233'}
        fake_config = SimpleNamespace(blur_enabled=False)

        with (
            patch.object(tray_menu, 'config', fake_config),
            patch.object(tray_menu, 'sync_window_blur') as sync_mock,
        ):
            window._setup_blur()

        sync_mock.assert_called_once_with(
            window,
            '#112233',
            enabled=False,
            window_alpha=0.95,
            tint_alpha=0xEE,
            context='托盘菜单',
        )


if __name__ == '__main__':
    unittest.main()
