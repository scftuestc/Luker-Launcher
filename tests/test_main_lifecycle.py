import tkinter as tk
import unittest
from unittest.mock import patch

import launcher_app
from launcher_app import LukerLauncher


class FakeWindow:
    def __init__(self, exists: bool = True, raises: bool = False) -> None:
        self.exists = exists
        self.raises = raises
        self.calls: list[tuple[int, object]] = []
        self.quit_called = False

    def winfo_exists(self) -> bool:
        if self.raises:
            raise tk.TclError("destroyed")
        return self.exists

    def after(self, delay: int, callback: object) -> str:
        self.calls.append((delay, callback))
        return "job"

    def quit(self) -> None:
        self.quit_called = True


class FakeDispatcher:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class UiScheduleTests(unittest.TestCase):
    @staticmethod
    def make_launcher(window: FakeWindow | None) -> LukerLauncher:
        launcher = object.__new__(LukerLauncher)
        launcher.log_window = window
        return launcher

    def test_schedules_on_existing_window(self):
        window = FakeWindow()
        launcher = self.make_launcher(window)

        def callback() -> None:
            pass

        launcher._schedule_ui(50, callback)

        self.assertEqual(window.calls, [(50, callback)])

    def test_skips_missing_window(self):
        launcher = self.make_launcher(None)

        launcher._schedule_ui(50, lambda: None)

        self.assertIsNone(launcher.log_window)

    def test_skips_destroyed_window(self):
        window = FakeWindow(exists=False)
        launcher = self.make_launcher(window)

        launcher._schedule_ui(50, lambda: None)

        self.assertEqual(window.calls, [])

    def test_tcl_error_is_ignored(self):
        window = FakeWindow(raises=True)
        launcher = self.make_launcher(window)

        launcher._schedule_ui(50, lambda: None)

        self.assertEqual(window.calls, [])


class ExitTests(unittest.TestCase):
    def test_finish_exit_stops_dispatcher_and_unregisters_callback(self):
        launcher = object.__new__(LukerLauncher)
        launcher._ui = FakeDispatcher()
        launcher.log_window = FakeWindow()
        launcher.tray_icon = None
        launcher._readiness = None

        def callback(enabled: bool, path: str | None) -> None:
            pass

        launcher._on_gcl_config_change = callback

        with patch.object(launcher_app.config, "remove_gcl_change_callback") as remove:
            launcher._finish_exit()

        remove.assert_called_once_with(callback)
        self.assertTrue(launcher._ui.stopped)
        self.assertTrue(launcher.log_window.quit_called)


if __name__ == "__main__":
    unittest.main()
