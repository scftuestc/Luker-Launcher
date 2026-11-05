import unittest
from types import SimpleNamespace

from launcher_app import LukerLauncher


class ShutdownTests(unittest.TestCase):
    def test_shutdown_is_idempotent(self):
        launcher = object.__new__(LukerLauncher)
        launcher._shutdown_done = False
        launcher._running = True
        status = SimpleNamespace(stop_calls=0)

        def stop_status() -> None:
            status.stop_calls += 1

        status.stop = stop_status
        dispatcher = SimpleNamespace(stop_calls=0)

        def stop_dispatcher() -> None:
            dispatcher.stop_calls += 1

        dispatcher.stop = stop_dispatcher
        tray = SimpleNamespace(stop_calls=0)

        def stop_tray() -> None:
            tray.stop_calls += 1

        tray.stop = stop_tray
        launcher._status = status
        launcher._ui = dispatcher
        launcher.tray_icon = tray

        launcher._shutdown()
        launcher._shutdown()

        self.assertEqual(status.stop_calls, 1)
        self.assertEqual(dispatcher.stop_calls, 1)
        self.assertEqual(tray.stop_calls, 1)
        self.assertFalse(launcher._running)


if __name__ == "__main__":
    unittest.main()
