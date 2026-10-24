import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import customtkinter as ctk

from log_window import LogWindow
from luker_readiness import LukerState


class WindowStatePollTests(unittest.TestCase):
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

    def test_destroy_cancels_jobs_before_teardown(self):
        window, canceled = self.make_window()
        window._glow_job = 'glow'
        window._pulse_job = 'pulse'

        with patch.object(ctk.CTk, 'destroy') as destroy:
            window.destroy()

        self.assertEqual(canceled, ['glow', 'pulse', 'search'])
        destroy.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
