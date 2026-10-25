import unittest
from types import SimpleNamespace
from unittest.mock import patch

import launcher_app
from core.readiness import LukerState
from launcher_app import LukerLauncher


class FakeManager:
    def __init__(self) -> None:
        self.is_running = True
        self.stop_calls = 0

    def stop(self) -> bool:
        self.stop_calls += 1
        return True


class FakeWindow:
    def __init__(self) -> None:
        self.gcl_states: list[bool] = []

    def set_gcl_enabled(self, enabled: bool) -> None:
        self.gcl_states.append(enabled)


class ReadinessRefreshTests(unittest.TestCase):
    def test_stale_callback_recomputes_current_ready_state(self):
        launcher = object.__new__(LukerLauncher)
        launcher.process_manager = FakeManager()
        launcher._readiness = SimpleNamespace(state=LukerState.READY)
        applied: list[LukerState] = []
        posted: list[object] = []
        launcher._apply_luker_state = applied.append
        launcher._post_ui = lambda callback, key=None: posted.append(callback) or True

        launcher._on_luker_state_change(LukerState.STARTING)
        posted[0]()

        self.assertEqual(applied, [LukerState.READY])


class ExitRaceTests(unittest.TestCase):
    def test_stop_all_managers_rechecks_new_instances(self):
        launcher = object.__new__(LukerLauncher)
        first = FakeManager()
        second = FakeManager()
        launcher.process_manager = first
        launcher.gcl_process_manager = None
        original_stop = first.stop

        def stop_first() -> bool:
            result = original_stop()
            launcher.process_manager = second
            return result

        first.stop = stop_first

        launcher._stop_all_process_managers()

        self.assertEqual(first.stop_calls, 1)
        self.assertEqual(second.stop_calls, 1)

    def test_adopt_is_rejected_during_exit(self):
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = True
        current = FakeManager()
        incoming = FakeManager()
        launcher.process_manager = current
        started: list[object] = []
        launcher._run_async = started.append

        launcher._adopt_process_manager(incoming)

        self.assertIs(launcher.process_manager, current)
        self.assertEqual(len(started), 1)
        started[0]()
        self.assertEqual(incoming.stop_calls, 1)

    def test_adopt_is_applied_when_not_exiting(self):
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher.process_manager = None
        launcher._last_status = LukerState.READY
        incoming = FakeManager()

        launcher._adopt_process_manager(incoming)

        self.assertIs(launcher.process_manager, incoming)
        self.assertIsNone(launcher._last_status)


class ShutdownTests(unittest.TestCase):
    def test_shutdown_is_idempotent(self):
        launcher = object.__new__(LukerLauncher)
        launcher._shutdown_done = False
        launcher._running = True
        readiness = SimpleNamespace(stop_calls=0)

        def stop_readiness() -> None:
            readiness.stop_calls += 1

        readiness.stop = stop_readiness
        dispatcher = SimpleNamespace(stop_calls=0)

        def stop_dispatcher() -> None:
            dispatcher.stop_calls += 1

        dispatcher.stop = stop_dispatcher
        tray = SimpleNamespace(stop_calls=0)

        def stop_tray() -> None:
            tray.stop_calls += 1

        tray.stop = stop_tray
        launcher._readiness = readiness
        launcher._ui = dispatcher
        launcher.tray_icon = tray
        launcher._on_gcl_config_change = lambda enabled, path: None

        with patch.object(launcher_app.config, "remove_gcl_change_callback") as remove:
            launcher._shutdown()
            launcher._shutdown()

        self.assertEqual(readiness.stop_calls, 1)
        self.assertEqual(dispatcher.stop_calls, 1)
        self.assertEqual(tray.stop_calls, 1)
        remove.assert_called_once_with(launcher._on_gcl_config_change)
        self.assertFalse(launcher._running)


class GclUiSyncTests(unittest.TestCase):
    def test_sync_uses_manager_presence_as_single_source(self):
        launcher = object.__new__(LukerLauncher)
        window = FakeWindow()
        launcher.log_window = window
        posted: list[object] = []
        launcher._post_ui = lambda callback, key=None: posted.append(callback) or True

        launcher.gcl_process_manager = None
        launcher._sync_gcl_ui()
        posted.pop()()

        launcher.gcl_process_manager = object()
        launcher._sync_gcl_ui()
        posted.pop()()

        self.assertEqual(window.gcl_states, [False, True])

    def test_sync_without_window_does_not_post(self):
        launcher = object.__new__(LukerLauncher)
        launcher.log_window = None
        launcher._post_ui = lambda callback, key=None: self.fail("不应投递")

        launcher._sync_gcl_ui()


class BusyResetTests(unittest.TestCase):
    def test_process_completion_resets_busy_when_ui_is_inactive(self):
        launcher = object.__new__(LukerLauncher)
        launcher._process_busy = False
        launcher._exiting = False
        launcher._ensure_process_manager = lambda: FakeManager()
        launcher._run_async = lambda func: func()
        launcher._post_ui = lambda callback, key=None, **_kwargs: False
        launcher._on_log = lambda line: None

        launcher._do_process_action(lambda manager: True)

        self.assertFalse(launcher._process_busy)

    def test_browser_completion_resets_busy_when_ui_is_inactive(self):
        launcher = object.__new__(LukerLauncher)
        launcher._browser_busy = False
        launcher._exiting = False
        launcher._run_async = lambda func: func()
        launcher._post_ui = lambda callback, key=None, **_kwargs: False
        launcher._open_browser_now = lambda: None

        launcher._on_open_browser()

        self.assertFalse(launcher._browser_busy)

    def test_process_completion_uses_control_channel(self):
        launcher = object.__new__(LukerLauncher)
        launcher._process_busy = False
        launcher._exiting = False
        launcher._ensure_process_manager = lambda: FakeManager()
        launcher._run_async = lambda func: func()
        calls = []
        launcher._post_ui = lambda callback, key=None, **kwargs: calls.append(kwargs) or True
        launcher._on_log = lambda line: None

        launcher._do_process_action(lambda manager: True)

        self.assertEqual(calls, [{"control": True}])

    def test_browser_completion_uses_control_channel(self):
        launcher = object.__new__(LukerLauncher)
        launcher._browser_busy = False
        launcher._exiting = False
        launcher._run_async = lambda func: func()
        calls = []
        launcher._post_ui = lambda callback, key=None, **kwargs: calls.append(kwargs) or True
        launcher._open_browser_now = lambda: None

        launcher._on_open_browser()

        self.assertEqual(calls, [{"control": True}])


if __name__ == "__main__":
    unittest.main()
