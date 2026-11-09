import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import customtkinter as ctk

from luker_launcher.services.readiness import LukerState
from luker_launcher.ui import log_window
from luker_launcher.ui.log_window import LogWindow


class WindowIconTests(unittest.TestCase):
    def test_icon_is_loaded_from_bundle_resource_path(self):
        window = object.__new__(LogWindow)
        window.iconbitmap = Mock()
        window.iconphoto = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            icon = Path(temp_dir) / "icon.ico"
            icon.write_bytes(b"")
            with patch.object(log_window, "resource_path", return_value=icon) as resource:
                window._set_window_icon()

        resource.assert_called_once_with("icon.ico")
        window.iconbitmap.assert_called_once_with(str(icon))
        window.iconphoto.assert_not_called()


class WindowStatePollTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(log_window.win32_api, 'user32')
        self.user32 = patcher.start()
        self.addCleanup(patcher.stop)
        self.user32.GetParent.return_value = 0
        self.user32.IsIconic.return_value = 0

    def make_window(self) -> tuple[LogWindow, list[tuple[int, object]]]:
        window = object.__new__(LogWindow)
        window._was_minimized = False
        window.winfo_id = lambda: 0
        calls: list[tuple[int, object]] = []

        def schedule(delay: int, callback: object) -> str:
            calls.append((delay, callback))
            return 'job'

        window.after = schedule
        return window, calls

    def test_hidden_window_polls_once_per_second(self):
        window, calls = self.make_window()
        window.winfo_viewable = lambda: False

        window._check_window_state()

        self.assertEqual(calls, [(1000, window._check_window_state)])

    def test_destroyed_window_stops_polling(self):
        window, calls = self.make_window()

        def destroyed() -> bool:
            raise tk.TclError('destroyed')

        window.winfo_viewable = destroyed

        window._check_window_state()

        self.assertEqual(calls, [])


class NativeWindowStateTests(unittest.TestCase):
    def make_window(self) -> tuple[LogWindow, list[tuple[int, object]]]:
        window = object.__new__(LogWindow)
        window._was_minimized = True
        window.winfo_id = lambda: 10
        window.winfo_viewable = lambda: True
        window._restore_window = Mock()
        calls: list[tuple[int, object]] = []

        def schedule(delay: int, callback: object) -> str:
            calls.append((delay, callback))
            return 'job'

        window.after = schedule
        return window, calls

    def test_check_window_state_restores_after_minimize(self):
        window, calls = self.make_window()

        with patch.object(log_window.win32_api, 'user32') as user32:
            user32.GetParent.return_value = 20
            user32.IsIconic.return_value = 0
            window._check_window_state()

        user32.GetParent.assert_called_once_with(10)
        user32.IsIconic.assert_called_once_with(20)
        self.assertFalse(window._was_minimized)
        self.assertEqual(calls[0], (50, window._restore_window))
        self.assertEqual(calls[1][0], 300)

    def test_check_window_state_records_minimized(self):
        window, calls = self.make_window()
        window._was_minimized = False

        with patch.object(log_window.win32_api, 'user32') as user32:
            user32.GetParent.return_value = 20
            user32.IsIconic.return_value = 1
            window._check_window_state()

        self.assertTrue(window._was_minimized)
        self.assertEqual(calls, [(300, window._check_window_state)])

    def test_restore_window_shows_and_focuses(self):
        window = object.__new__(LogWindow)
        window.winfo_id = lambda: 10
        window.lift = Mock()
        window.focus_force = Mock()

        with patch.object(log_window.win32_api, 'user32') as user32:
            user32.GetParent.return_value = 20
            window._restore_window()

        user32.ShowWindow.assert_called_once_with(20, 9)
        window.lift.assert_called_once_with()
        window.focus_force.assert_called_once_with()

    def test_restore_window_logs_failure(self):
        window = object.__new__(LogWindow)
        window.winfo_id = lambda: 10

        with (
            patch.object(log_window.win32_api, 'user32') as user32,
            self.assertLogs('luker_launcher.ui.log_window', level='WARNING') as logs,
        ):
            user32.GetParent.side_effect = OSError("boom")
            window._restore_window()

        self.assertIn("恢复窗口失败", logs.output[0])


class AnimationJobTests(unittest.TestCase):
    def make_window(self) -> tuple[LogWindow, list[object]]:
        window = object.__new__(LogWindow)
        window._luker_state = LukerState.STOPPED
        window._pulse_phase = 0.0
        window._pulse_job = None
        window._glow_job = None
        window.winfo_viewable = lambda: True
        window.after = lambda _delay, _callback: 'job'
        canceled: list[object] = []
        window.after_cancel = canceled.append
        window.search = SimpleNamespace(cancel_pending=lambda: canceled.append('search'))
        return window, canceled

    def test_pulse_animation_tracks_its_job(self):
        window, _canceled = self.make_window()

        window._animate_status_pulse()

        self.assertEqual(window._pulse_job, 'job')

    def test_cancel_animation_jobs_clears_all_timers(self):
        window, canceled = self.make_window()
        window._glow_job = 'glow'
        window._pulse_job = 'pulse'

        window._cancel_animation_jobs()

        self.assertEqual(canceled, ['glow', 'pulse', 'search'])
        self.assertIsNone(window._glow_job)
        self.assertIsNone(window._pulse_job)

    def test_cancel_animation_jobs_cancels_character_fit(self):
        window, canceled = self.make_window()
        window._character_fit_job = 'fit'

        window._cancel_animation_jobs()

        self.assertIn('fit', canceled)
        self.assertIsNone(window._character_fit_job)

    def test_destroy_cancels_jobs_stops_logs_and_unregisters_callbacks(self):
        window, canceled = self.make_window()
        window._glow_job = 'glow'
        window._pulse_job = 'pulse'
        stopped: list[bool] = []
        window._logs = SimpleNamespace(stop=lambda: stopped.append(True))

        with (
            patch.object(ctk.CTk, 'destroy') as destroy,
            patch.object(log_window.config, 'remove_theme_change_callback') as remove_theme,
            patch.object(log_window.config, 'remove_blur_change_callback') as remove_blur,
        ):
            window.destroy()

        self.assertEqual(canceled, ['glow', 'pulse', 'search'])
        self.assertEqual(stopped, [True])
        remove_theme.assert_called_once_with(window._on_theme_change)
        remove_blur.assert_called_once_with(window._on_blur_change)
        destroy.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
