import unittest
from unittest.mock import patch

import launcher_app
from launcher_app import LukerLauncher
from luker_readiness import LukerState


class FakeLogWindow:
    def __init__(self) -> None:
        self.hidden = 0
        self.focused = 0
        self.states: list[LukerState] = []

    def hide(self) -> None:
        self.hidden += 1

    def focus_force(self) -> None:
        self.focused += 1

    def update_status(self, state: LukerState) -> None:
        self.states.append(state)


class FakeTrayMenu:
    def __init__(self) -> None:
        self.states: list[LukerState] = []

    def set_luker_state(self, state: LukerState) -> None:
        self.states.append(state)


class FakeProcessManager:
    def __init__(self, running: bool = True) -> None:
        self.is_running = running


class FakeReadiness:
    def __init__(self, state: LukerState = LukerState.READY) -> None:
        self.state = state
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1


class ExitRequestTests(unittest.TestCase):
    def make_launcher(self) -> tuple[LukerLauncher, FakeLogWindow, list[str]]:
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher._exit_dialog_open = False
        launcher._last_status = None
        launcher.log_window = FakeLogWindow()
        launcher.tray_menu = FakeTrayMenu()
        launcher.process_manager = FakeProcessManager()
        launcher._readiness = FakeReadiness()
        exits: list[str] = []
        launcher._on_exit = lambda: exits.append('exit')
        return launcher, launcher.log_window, exits

    def test_confirm_hides_window_and_exits(self):
        launcher, window, exits = self.make_launcher()
        captured: dict[str, object] = {}

        def fake_show(parent, state, on_confirm, on_cancel):
            captured.update(parent=parent, state=state, confirm=on_confirm, cancel=on_cancel)

        with patch.object(launcher_app, 'show_exit_confirmation', fake_show):
            launcher._on_request_exit()

        self.assertIs(captured['parent'], window)
        self.assertIs(captured['state'], LukerState.READY)
        self.assertTrue(launcher._exit_dialog_open)

        captured['confirm']()

        self.assertEqual(window.hidden, 1)
        self.assertEqual(exits, ['exit'])
        self.assertFalse(launcher._exit_dialog_open)

    def test_cancel_keeps_window_and_focuses_it(self):
        launcher, window, exits = self.make_launcher()
        captured: dict[str, object] = {}

        def fake_show(parent, state, on_confirm, on_cancel):
            captured.update(confirm=on_confirm, cancel=on_cancel)

        with patch.object(launcher_app, 'show_exit_confirmation', fake_show):
            launcher._on_request_exit()

        captured['cancel']()

        self.assertEqual(window.hidden, 0)
        self.assertEqual(window.focused, 1)
        self.assertEqual(exits, [])
        self.assertFalse(launcher._exit_dialog_open)

    def test_ignores_when_already_exiting(self):
        launcher, _, exits = self.make_launcher()
        launcher._exiting = True

        with patch.object(launcher_app, 'show_exit_confirmation') as show:
            launcher._on_request_exit()

        show.assert_not_called()
        self.assertEqual(exits, [])

    def test_ignores_when_dialog_already_open(self):
        launcher, _, _ = self.make_launcher()
        launcher._exit_dialog_open = True

        with patch.object(launcher_app, 'show_exit_confirmation') as show:
            launcher._on_request_exit()

        show.assert_not_called()


class LukerStateTests(unittest.TestCase):
    def test_state_is_stopped_without_running_process(self):
        launcher = object.__new__(LukerLauncher)
        launcher.process_manager = FakeProcessManager(running=False)
        launcher._readiness = FakeReadiness(LukerState.READY)

        self.assertIs(launcher._current_luker_state(), LukerState.STOPPED)

    def test_state_is_starting_when_only_process_is_alive(self):
        launcher = object.__new__(LukerLauncher)
        launcher.process_manager = FakeProcessManager()
        launcher._readiness = FakeReadiness(LukerState.STARTING)

        self.assertIs(launcher._current_luker_state(), LukerState.STARTING)

    def test_state_is_ready_when_service_is_ready(self):
        launcher = object.__new__(LukerLauncher)
        launcher.process_manager = FakeProcessManager()
        launcher._readiness = FakeReadiness(LukerState.READY)

        self.assertIs(launcher._current_luker_state(), LukerState.READY)

    def test_apply_state_is_deduplicated(self):
        launcher = object.__new__(LukerLauncher)
        launcher._last_status = None
        window = FakeLogWindow()
        menu = FakeTrayMenu()
        launcher.log_window = window
        launcher.tray_menu = menu

        launcher._apply_luker_state(LukerState.STARTING)
        launcher._apply_luker_state(LukerState.STARTING)
        launcher._apply_luker_state(LukerState.READY)

        self.assertEqual(window.states, [LukerState.STARTING, LukerState.READY])
        self.assertEqual(menu.states, [LukerState.STARTING, LukerState.READY])

    def test_reset_clears_last_status_and_readiness(self):
        launcher = object.__new__(LukerLauncher)
        launcher._last_status = LukerState.READY
        readiness = FakeReadiness()
        launcher._readiness = readiness

        launcher._reset_luker_readiness()

        self.assertIsNone(launcher._last_status)
        self.assertEqual(readiness.reset_calls, 1)


if __name__ == '__main__':
    unittest.main()
