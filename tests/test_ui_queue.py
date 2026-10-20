import queue
import unittest
from threading import Lock
from unittest.mock import patch

import main
from main import LukerLauncher


def make_launcher() -> LukerLauncher:
    launcher = object.__new__(LukerLauncher)
    launcher._ui_active = True
    launcher._ui_queue = queue.Queue(maxsize=main.UI_QUEUE_MAXSIZE)
    launcher._ui_state = {}
    launcher._ui_lock = Lock()
    launcher.log_window = None
    return launcher


class UiQueueTests(unittest.TestCase):
    def test_coalesced_key_keeps_latest_callback(self):
        launcher = make_launcher()
        calls = []

        launcher._post_ui(lambda: calls.append("first"), main.UI_KEY_VISIBILITY)
        launcher._post_ui(lambda: calls.append("second"), main.UI_KEY_VISIBILITY)
        launcher._pump_ui_queue()

        self.assertEqual(calls, ["second"])

    def test_plain_events_keep_fifo_order(self):
        launcher = make_launcher()
        calls = []

        for index in range(3):
            launcher._post_ui(lambda i=index: calls.append(i))
        launcher._pump_ui_queue()

        self.assertEqual(calls, [0, 1, 2])

    def test_pump_limits_events_per_tick(self):
        launcher = make_launcher()
        calls = []

        for index in range(5):
            launcher._post_ui(lambda i=index: calls.append(i))

        with patch.object(main, "UI_EVENTS_PER_TICK", 2):
            launcher._pump_ui_queue()
            self.assertEqual(calls, [0, 1])
            launcher._pump_ui_queue()
            self.assertEqual(calls, [0, 1, 2, 3])

        launcher._pump_ui_queue()
        self.assertEqual(calls, [0, 1, 2, 3, 4])

    def test_full_queue_drops_oldest_event(self):
        launcher = make_launcher()
        launcher._ui_queue = queue.Queue(maxsize=2)
        calls = []

        for index in range(3):
            launcher._post_ui(lambda i=index: calls.append(i))

        self.assertEqual(launcher._ui_queue.qsize(), 2)
        launcher._pump_ui_queue()
        self.assertEqual(calls, [1, 2])

    def test_post_ignored_after_shutdown(self):
        launcher = make_launcher()
        launcher._ui_active = False
        calls = []

        launcher._post_ui(lambda: calls.append("event"))
        launcher._post_ui(lambda: calls.append("state"), main.UI_KEY_SETTINGS)

        self.assertTrue(launcher._ui_queue.empty())
        self.assertEqual(launcher._ui_state, {})
        self.assertEqual(calls, [])

    def test_state_callbacks_run_before_events(self):
        launcher = make_launcher()
        calls = []

        launcher._post_ui(lambda: calls.append("event"))
        launcher._post_ui(lambda: calls.append("state"), main.UI_KEY_SETTINGS)
        launcher._pump_ui_queue()

        self.assertEqual(calls, ["state", "event"])

    def test_exit_state_survives_full_queue(self):
        launcher = make_launcher()
        launcher._ui_queue = queue.Queue(maxsize=1)
        calls = []

        launcher._post_ui(lambda: calls.append("event"), main.UI_KEY_EXIT)
        launcher._post_ui(lambda: calls.append("queued-1"))
        launcher._post_ui(lambda: calls.append("queued-2"))
        launcher._pump_ui_queue()

        self.assertEqual(calls, ["event", "queued-2"])

    def test_shutdown_stops_remaining_events(self):
        launcher = make_launcher()
        calls = []

        def stop() -> None:
            calls.append("stop")
            launcher._ui_active = False

        launcher._post_ui(stop, main.UI_KEY_EXIT)
        launcher._post_ui(lambda: calls.append("after-exit"))
        launcher._pump_ui_queue()

        self.assertEqual(calls, ["stop"])


if __name__ == "__main__":
    unittest.main()
