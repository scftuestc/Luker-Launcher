import time
import unittest
import urllib.error
from unittest.mock import patch

from core.readiness import LukerReadinessMonitor, LukerState


def wait_for(predicate, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


class ReadinessMonitorTests(unittest.TestCase):
    def make_monitor(
        self,
        running,
        changes: list[LukerState],
        *,
        required_successes: int = 2,
    ) -> LukerReadinessMonitor:
        return LukerReadinessMonitor(
            running,
            lambda: 'http://127.0.0.1:8000',
            changes.append,
            interval=0.01,
            timeout=0.05,
            required_successes=required_successes,
        )

    def test_reaches_ready_after_required_successes(self):
        changes: list[LukerState] = []
        monitor = self.make_monitor(lambda: True, changes)
        monitor._probe = lambda: True

        monitor.start()
        try:
            self.assertTrue(wait_for(lambda: monitor.state is LukerState.READY))
        finally:
            monitor.stop()

        self.assertEqual(changes, [LukerState.STARTING, LukerState.READY])

    def test_stays_starting_when_probe_fails(self):
        changes: list[LukerState] = []
        monitor = self.make_monitor(lambda: True, changes)
        monitor._probe = lambda: False

        monitor.start()
        try:
            self.assertTrue(wait_for(lambda: LukerState.STARTING in changes))
            time.sleep(0.05)
            self.assertIs(monitor.state, LukerState.STARTING)
        finally:
            monitor.stop()

        self.assertEqual(changes, [LukerState.STARTING])

    def test_process_stop_returns_to_stopped(self):
        running = [True]
        changes: list[LukerState] = []
        monitor = self.make_monitor(lambda: running[0], changes, required_successes=1)
        monitor._probe = lambda: True

        monitor.start()
        try:
            self.assertTrue(wait_for(lambda: monitor.state is LukerState.READY))
            running[0] = False
            self.assertTrue(wait_for(lambda: monitor.state is LukerState.STOPPED))
        finally:
            monitor.stop()

        self.assertIn(LukerState.STOPPED, changes)

    def test_reset_downgrades_ready(self):
        changes: list[LukerState] = []
        monitor = self.make_monitor(lambda: True, changes, required_successes=1)
        monitor._probe = lambda: True

        monitor.start()
        try:
            self.assertTrue(wait_for(lambda: monitor.state is LukerState.READY))
            monitor.reset()
            self.assertIs(monitor.state, LukerState.STARTING)
        finally:
            monitor.stop()

    def test_http_error_counts_as_ready(self):
        monitor = self.make_monitor(lambda: True, [])
        error = urllib.error.HTTPError('http://x', 503, 'unavailable', None, None)

        with patch('core.readiness.urllib.request.urlopen', side_effect=error):
            self.assertTrue(monitor._probe())

    def test_connection_error_is_not_ready(self):
        monitor = self.make_monitor(lambda: True, [])

        with patch(
            'core.readiness.urllib.request.urlopen',
            side_effect=urllib.error.URLError('refused'),
        ):
            self.assertFalse(monitor._probe())

    def test_stop_terminates_thread(self):
        monitor = self.make_monitor(lambda: True, [])
        monitor._probe = lambda: False

        monitor.start()
        monitor.stop()

        self.assertIsNone(monitor._thread)


if __name__ == '__main__':
    unittest.main()
