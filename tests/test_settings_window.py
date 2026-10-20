import unittest
from typing import ClassVar
from unittest.mock import patch

import main
from main import LukerLauncher
from settings_window import _SCROLL_BINDING_SEQUENCES, clear_scroll_bindings


class FakeTkInterpreter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def call(self, *args: str) -> None:
        self.calls.append(args)


class FakeWidget:
    def __init__(self) -> None:
        self.tk = FakeTkInterpreter()


class FakeSettingsWindow:
    instances: ClassVar[list["FakeSettingsWindow"]] = []

    def __init__(
        self,
        parent: object,
        anchor_point: tuple[int, int] | None = None,
        on_close: object = None,
    ) -> None:
        self.parent = parent
        self.anchor_point = anchor_point
        self.on_close = on_close
        self.focused = 0
        self.alive = True
        type(self).instances.append(self)

    def focus_force(self) -> None:
        self.focused += 1

    def is_alive(self) -> bool:
        return self.alive


class FakeTrayMenu:
    def __init__(self) -> None:
        self.state: tuple[bool, bool, bool, bool] | None = None
        self.point: tuple[int, int] | None = None

    def update_state(self, *args: bool) -> None:
        self.state = args

    def show_at(self, x: int, y: int) -> None:
        self.point = (x, y)


class FakeLogWindow:
    def is_visible(self) -> bool:
        return False


class ScrollBindingTests(unittest.TestCase):
    def test_clears_all_known_global_sequences(self):
        widget = FakeWidget()

        clear_scroll_bindings(widget)

        self.assertEqual(
            [call[2] for call in widget.tk.calls],
            list(_SCROLL_BINDING_SEQUENCES),
        )
        self.assertTrue(all(call[:2] == ("bind", "all") for call in widget.tk.calls))
        self.assertTrue(all(call[3] == "" for call in widget.tk.calls))


class SettingsWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSettingsWindow.instances.clear()

    @staticmethod
    def _make_launcher() -> LukerLauncher:
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher.log_window = object()
        launcher.settings_window = None
        launcher._tray_anchor = (100, 200)
        return launcher

    def test_open_uses_tray_anchor_and_reuses_alive_window(self):
        launcher = self._make_launcher()

        with patch.object(main, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()
            launcher._open_settings_window()

        self.assertEqual(len(FakeSettingsWindow.instances), 1)
        window = FakeSettingsWindow.instances[0]
        self.assertIs(window.parent, launcher.log_window)
        self.assertEqual(window.anchor_point, (100, 200))
        self.assertEqual(window.focused, 2)
        self.assertEqual(window.on_close, launcher._on_settings_closed)

    def test_closed_window_is_recreated(self):
        launcher = self._make_launcher()

        with patch.object(main, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()
            FakeSettingsWindow.instances[0].alive = False
            launcher._tray_anchor = (300, 400)
            launcher._open_settings_window()

        self.assertEqual(len(FakeSettingsWindow.instances), 2)
        self.assertEqual(FakeSettingsWindow.instances[1].anchor_point, (300, 400))

    def test_close_callback_clears_reference(self):
        launcher = self._make_launcher()
        window = object()
        launcher.settings_window = window

        launcher._on_settings_closed()

        self.assertIsNone(launcher.settings_window)

    def test_exiting_does_not_open_window(self):
        launcher = self._make_launcher()
        launcher._exiting = True

        with patch.object(main, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()

        self.assertEqual(FakeSettingsWindow.instances, [])

    def test_show_tray_menu_stores_anchor(self):
        launcher = self._make_launcher()
        launcher.tray_menu = FakeTrayMenu()
        launcher.log_window = FakeLogWindow()
        launcher.process_manager = None
        launcher.gcl_process_manager = None

        launcher._show_tray_menu(12, 34)

        self.assertEqual(launcher._tray_anchor, (12, 34))
        self.assertEqual(launcher.tray_menu.point, (12, 34))


if __name__ == "__main__":
    unittest.main()
