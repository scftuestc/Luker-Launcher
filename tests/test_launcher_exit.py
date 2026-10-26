import unittest
from types import SimpleNamespace
from unittest.mock import patch

import launcher_app
from core.readiness import LukerState
from launcher_app import LukerLauncher


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


class FakeTrayIcon:
    def __init__(self) -> None:
        self.visible: list[bool] = []

    def set_window_visible(self, visible: bool) -> None:
        self.visible.append(visible)


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
    def make_launcher(
        self,
    ) -> tuple[LukerLauncher, FakeLogWindow, FakeTrayIcon, list[str]]:
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher._exit_dialog_open = False
        launcher._tray_ready = True
        launcher._last_status = None
        launcher.log_window = FakeLogWindow()
        launcher.tray_menu = FakeTrayMenu()
        launcher.tray_icon = FakeTrayIcon()
        launcher.process_manager = FakeProcessManager()
        launcher._readiness = FakeReadiness()
        exits: list[str] = []
        launcher._on_exit = lambda: exits.append('exit')
        return launcher, launcher.log_window, launcher.tray_icon, exits

    @staticmethod
    def make_dialog():
        captured: dict[str, object] = {}

        def fake_show(parent, state, *, allow_hide, on_hide, on_exit, on_cancel):
            captured.update(
                parent=parent,
                state=state,
                allow_hide=allow_hide,
                hide=on_hide,
                exit=on_exit,
                cancel=on_cancel,
            )

        return captured, fake_show

    def test_ask_hide_without_remember_hides_and_keeps_setting(self):
        launcher, window, tray, exits = self.make_launcher()
        captured, fake_show = self.make_dialog()
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice', fake_show),
        ):
            launcher._on_request_exit()
            self.assertTrue(launcher._exit_dialog_open)
            self.assertTrue(captured['allow_hide'])
            captured['hide'](False)

        self.assertEqual(window.hidden, 1)
        self.assertEqual(tray.visible, [False])
        self.assertEqual(exits, [])
        self.assertEqual(fake_config.close_behavior, 'ask')
        self.assertFalse(launcher._exit_dialog_open)

    def test_ask_hide_with_remember_saves_tray_behavior(self):
        launcher, window, tray, exits = self.make_launcher()
        captured, fake_show = self.make_dialog()
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice', fake_show),
        ):
            launcher._on_request_exit()
            captured['hide'](True)

        self.assertEqual(window.hidden, 1)
        self.assertEqual(tray.visible, [False])
        self.assertEqual(exits, [])
        self.assertEqual(fake_config.close_behavior, 'tray')

    def test_ask_exit_with_remember_saves_exit_behavior(self):
        launcher, window, _, exits = self.make_launcher()
        captured, fake_show = self.make_dialog()
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice', fake_show),
        ):
            launcher._on_request_exit()
            captured['exit'](True)

        self.assertEqual(window.hidden, 1)
        self.assertEqual(exits, ['exit'])
        self.assertEqual(fake_config.close_behavior, 'exit')
        self.assertFalse(launcher._exit_dialog_open)

    def test_cancel_keeps_window_and_setting(self):
        launcher, window, tray, exits = self.make_launcher()
        captured, fake_show = self.make_dialog()
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice', fake_show),
        ):
            launcher._on_request_exit()
            captured['cancel']()

        self.assertEqual(window.hidden, 0)
        self.assertEqual(window.focused, 1)
        self.assertEqual(tray.visible, [])
        self.assertEqual(exits, [])
        self.assertEqual(fake_config.close_behavior, 'ask')
        self.assertFalse(launcher._exit_dialog_open)

    def test_remembered_tray_hides_without_dialog(self):
        launcher, window, tray, exits = self.make_launcher()
        fake_config = SimpleNamespace(close_behavior='tray')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice') as show,
        ):
            launcher._on_request_exit()

        show.assert_not_called()
        self.assertEqual(window.hidden, 1)
        self.assertEqual(tray.visible, [False])
        self.assertEqual(exits, [])

    def test_remembered_tray_falls_back_to_dialog_without_tray(self):
        launcher, window, _, exits = self.make_launcher()
        launcher._tray_ready = False
        captured, fake_show = self.make_dialog()
        fake_config = SimpleNamespace(close_behavior='tray')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice', fake_show),
        ):
            launcher._on_request_exit()
            self.assertFalse(captured['allow_hide'])
            captured['cancel']()

        self.assertEqual(window.hidden, 0)
        self.assertEqual(exits, [])
        self.assertEqual(fake_config.close_behavior, 'tray')
        self.assertFalse(launcher._exit_dialog_open)

    def test_remembered_exit_exits_without_dialog(self):
        launcher, window, _, exits = self.make_launcher()
        fake_config = SimpleNamespace(close_behavior='exit')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice') as show,
        ):
            launcher._on_request_exit()

        show.assert_not_called()
        self.assertEqual(window.hidden, 1)
        self.assertEqual(exits, ['exit'])

    def test_ignores_when_already_exiting(self):
        launcher, _, _, exits = self.make_launcher()
        launcher._exiting = True
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice') as show,
        ):
            launcher._on_request_exit()

        show.assert_not_called()
        self.assertEqual(exits, [])

    def test_ignores_when_dialog_already_open(self):
        launcher, _, _, _ = self.make_launcher()
        launcher._exit_dialog_open = True
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(launcher_app, 'show_close_choice') as show,
        ):
            launcher._on_request_exit()

        show.assert_not_called()

    def test_dialog_failure_falls_back_to_hide_or_exit_prompt(self):
        launcher, window, tray, exits = self.make_launcher()
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(
                launcher_app,
                'show_close_choice',
                side_effect=RuntimeError('boom'),
            ),
            patch.object(
                launcher_app.messagebox,
                'askyesnocancel',
                return_value=True,
            ) as ask,
        ):
            launcher._on_request_exit()

        ask.assert_called_once()
        self.assertEqual(window.hidden, 1)
        self.assertEqual(tray.visible, [False])
        self.assertEqual(exits, [])
        self.assertFalse(launcher._exit_dialog_open)

    def test_dialog_failure_without_tray_falls_back_to_exit_prompt(self):
        launcher, window, _, exits = self.make_launcher()
        launcher._tray_ready = False
        fake_config = SimpleNamespace(close_behavior='ask')

        with (
            patch.object(launcher_app, 'config', fake_config),
            patch.object(
                launcher_app,
                'show_close_choice',
                side_effect=RuntimeError('boom'),
            ),
            patch.object(
                launcher_app.messagebox,
                'askyesno',
                return_value=True,
            ) as ask,
        ):
            launcher._on_request_exit()

        ask.assert_called_once()
        self.assertEqual(window.hidden, 1)
        self.assertEqual(exits, ['exit'])
        self.assertFalse(launcher._exit_dialog_open)


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
