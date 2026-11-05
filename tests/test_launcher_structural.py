import unittest
from types import SimpleNamespace

from core.readiness import LukerState
from launcher_app import LukerLauncher


class FakeManager:
    def __init__(self) -> None:
        self.is_running = True
        self.stop_calls = 0

    def stop(self) -> bool:
        self.stop_calls += 1
        return True


class ReadinessRefreshTests(unittest.TestCase):
    def test_stale_callback_recomputes_current_ready_state(self):
        launcher = object.__new__(LukerLauncher)
        launcher._process = SimpleNamespace(manager=None, busy=False)
        launcher.process_manager = FakeManager()
        launcher._readiness = SimpleNamespace(state=LukerState.READY)
        applied: list[LukerState] = []
        posted: list[object] = []
        launcher._apply_luker_state = applied.append
        launcher._post_ui = lambda callback, key=None: posted.append(callback) or True

        launcher._on_luker_state_change(LukerState.STARTING)
        posted[0]()

        self.assertEqual(applied, [LukerState.READY])


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

        launcher._shutdown()
        launcher._shutdown()

        self.assertEqual(readiness.stop_calls, 1)
        self.assertEqual(dispatcher.stop_calls, 1)
        self.assertEqual(tray.stop_calls, 1)
        self.assertFalse(launcher._running)


if __name__ == "__main__":
    unittest.main()
