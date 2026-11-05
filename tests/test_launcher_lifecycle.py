import tkinter as tk
import unittest
from unittest.mock import Mock, patch

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


class TrayMenuRequestTests(unittest.TestCase):
    def test_reads_foreground_handle_before_posting_ui(self):
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher._show_tray_menu = Mock()
        posted: list[tuple[object, object]] = []
        launcher._post_ui = lambda callback, key=None: posted.append((callback, key)) or True

        with patch.object(launcher_app.win32_api, 'user32') as user32:
            user32.GetForegroundWindow.return_value = 1234
            launcher._on_show_menu(10, 20)

        user32.GetForegroundWindow.assert_called_once_with()
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0][1], launcher_app.UI_KEY_TRAY_MENU)
        posted[0][0]()
        launcher._show_tray_menu.assert_called_once_with(10, 20, 1234)


class TrayFailureCloseTests(unittest.TestCase):
    def test_tray_failure_keeps_confirmation_and_updates_copy(self):
        launcher = object.__new__(LukerLauncher)
        logs: list[str] = []
        started: list[bool] = []
        launcher._on_log = logs.append
        launcher._on_start = lambda: started.append(True)

        class FakeWindow:
            def __init__(self) -> None:
                self.tray_available = True
                self.shown = False
                self.on_hide_callback = 'hide-sentinel'
                self.on_exit_callback = 'exit-sentinel'

            def set_tray_available(self, value: bool) -> None:
                self.tray_available = value

            def show(self) -> None:
                self.shown = True

        window = FakeWindow()
        launcher.log_window = window

        launcher._start_first_run(False)

        self.assertEqual(started, [True])
        self.assertFalse(window.tray_available)
        self.assertTrue(window.shown)
        self.assertEqual(window.on_hide_callback, 'hide-sentinel')
        self.assertEqual(window.on_exit_callback, 'exit-sentinel')
        self.assertIn("询问是否退出", logs[-1])


class ExitTests(unittest.TestCase):
    def test_finish_exit_stops_dispatcher(self):
        launcher = object.__new__(LukerLauncher)
        launcher._ui = FakeDispatcher()
        launcher.log_window = FakeWindow()
        launcher.tray_icon = None
        launcher._readiness = None
        launcher._shutdown_done = False
        launcher._running = True

        launcher._finish_exit()

        self.assertTrue(launcher._ui.stopped)
        self.assertTrue(launcher.log_window.quit_called)


if __name__ == "__main__":
    unittest.main()
