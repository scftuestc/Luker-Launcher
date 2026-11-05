import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from application.browser_coordinator import BrowserCoordinator, is_server_ready
from application.lifecycle_state import LifecycleState


class FakeConfig:
    def __init__(self, *, use_pwa_mode: bool = True, port: int = 8000) -> None:
        self.use_pwa_mode = use_pwa_mode
        self.port = port

    def get_server_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


class FakePoster:
    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.posted: list[tuple[object, object]] = []
        self.controls: list[object] = []

    def post(self, callback, coalesce_key=None):
        self.posted.append((callback, coalesce_key))
        return self.accept

    def post_control(self, callback):
        self.controls.append(callback)
        return self.accept


class FakeRunner:
    def __init__(self) -> None:
        self.workers: list[object] = []
        self.started = True

    def run(self, func, *, name=None):
        self.workers.append(func)
        return self.started


class FakeClock:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def make_coordinator(
    *,
    use_pwa_mode: bool = True,
    accept: bool = True,
    probe=None,
    clock=None,
    wait_timeout: float = 30,
) -> tuple[BrowserCoordinator, FakePoster, FakeRunner, list[tuple[str, bool]], list[str]]:
    config = FakeConfig(use_pwa_mode=use_pwa_mode)
    poster = FakePoster(accept=accept)
    runner = FakeRunner()
    opens: list[tuple[str, bool]] = []
    logs: list[str] = []
    coordinator = BrowserCoordinator(
        config=config,
        task_runner=runner,
        post_ui=poster,
        log=logs.append,
        open_browser=lambda url, prefer_pwa: opens.append((url, prefer_pwa)) or True,
        lifecycle=LifecycleState(),
        is_running=lambda: True,
        probe=probe or (lambda _url: True),
        clock=clock or (lambda: 0.0),
        sleep=lambda _seconds: None,
        wait_timeout=wait_timeout,
    )
    return coordinator, poster, runner, opens, logs


class BrowserCoordinatorTests(unittest.TestCase):
    def test_manual_open_uses_config_url_and_pwa_preference(self):
        coordinator, poster, runner, opens, _ = make_coordinator(use_pwa_mode=True)

        coordinator.open()

        self.assertEqual(len(runner.workers), 1)
        self.assertTrue(coordinator.busy)
        runner.workers[0]()

        self.assertEqual(opens, [("http://127.0.0.1:8000", True)])
        self.assertEqual(poster.posted, [])
        self.assertEqual(len(poster.controls), 1)
        poster.controls[0]()
        self.assertFalse(coordinator.busy)

    def test_manual_open_cancels_pending_auto(self):
        coordinator, _, runner, opens, _ = make_coordinator()
        coordinator.schedule_auto_open_if_needed()

        self.assertTrue(coordinator.auto_pending)
        coordinator.open()

        self.assertFalse(coordinator.auto_pending)
        self.assertEqual(len(runner.workers), 2)
        runner.workers[1]()
        self.assertEqual(opens, [("http://127.0.0.1:8000", True)])

        coordinator.open(automatic=True)
        self.assertEqual(len(runner.workers), 2)

    def test_automatic_open_runs_only_once(self):
        coordinator, poster, runner, _, _ = make_coordinator()
        coordinator.schedule_auto_open_if_needed()

        coordinator.open(automatic=True)
        self.assertFalse(coordinator.auto_pending)
        self.assertEqual(len(runner.workers), 2)

        runner.workers[1]()
        poster.controls[0]()
        self.assertFalse(coordinator.busy)
        coordinator.open(automatic=True)
        self.assertEqual(len(runner.workers), 2)

    def test_automatic_open_is_ignored_without_pending_request(self):
        coordinator, _, runner, _, _ = make_coordinator()

        coordinator.open(automatic=True)

        self.assertEqual(runner.workers, [])
        self.assertFalse(coordinator.busy)

    def test_exiting_rejects_open_and_clears_pending(self):
        coordinator, _, runner, _, _ = make_coordinator()
        coordinator.schedule_auto_open_if_needed()
        coordinator.lifecycle.exiting = True

        coordinator.open(automatic=True)

        self.assertFalse(coordinator.auto_pending)
        self.assertEqual(len(runner.workers), 1)

    def test_busy_rejects_second_open(self):
        coordinator, _, runner, _, _ = make_coordinator()
        coordinator.open()

        coordinator.open()

        self.assertEqual(len(runner.workers), 1)

    def test_finish_resets_busy_when_ui_pump_is_inactive(self):
        coordinator, _, runner, _, _ = make_coordinator(accept=False)

        coordinator.open()
        runner.workers[0]()

        self.assertFalse(coordinator.busy)

    def test_thread_failure_resets_busy(self):
        coordinator, _, runner, _, _ = make_coordinator()
        runner.started = False

        with self.assertLogs("application.browser_coordinator", level="ERROR"):
            coordinator.open()

        self.assertFalse(coordinator.busy)

    def test_schedule_marks_pending_only_in_pwa_mode(self):
        coordinator, _, runner, _, _ = make_coordinator(use_pwa_mode=True)

        coordinator.schedule_auto_open_if_needed()

        self.assertTrue(coordinator.auto_pending)
        self.assertEqual(len(runner.workers), 1)

        coordinator, _, runner, _, _ = make_coordinator(use_pwa_mode=False)
        coordinator.schedule_auto_open_if_needed()

        self.assertFalse(coordinator.auto_pending)
        self.assertEqual(runner.workers, [])

    def test_auto_wait_opens_after_server_is_ready(self):
        coordinator, poster, runner, opens, logs = make_coordinator()
        coordinator.schedule_auto_open_if_needed()

        runner.workers[0]()

        self.assertIn("检测到 Luker 已启动", logs[0])
        self.assertEqual(len(poster.posted), 1)
        poster.posted[0][0]()
        self.assertFalse(coordinator.auto_pending)
        runner.workers[1]()
        self.assertEqual(opens, [("http://127.0.0.1:8000", True)])

    def test_auto_wait_logs_timeout_and_clears_pending(self):
        coordinator, _, runner, opens, logs = make_coordinator(
            probe=lambda _url: False,
            clock=FakeClock([0.0, 0.0, 2.0]),
            wait_timeout=1.0,
        )
        coordinator.schedule_auto_open_if_needed()

        runner.workers[0]()

        self.assertFalse(coordinator.auto_pending)
        self.assertEqual(opens, [])
        self.assertIn("等待 Luker 启动超时", logs[0])


class ServerReadyTests(unittest.TestCase):
    def test_successful_response_is_ready(self):
        response = MagicMock()
        response.__enter__.return_value = response

        with patch(
            "application.browser_coordinator.urllib.request.urlopen",
            return_value=response,
        ):
            self.assertTrue(is_server_ready("http://127.0.0.1:8000"))

    def test_http_error_still_means_server_is_ready(self):
        error = urllib.error.HTTPError(
            "http://127.0.0.1:8000",
            500,
            "server error",
            None,
            None,
        )

        with patch(
            "application.browser_coordinator.urllib.request.urlopen",
            side_effect=error,
        ):
            self.assertTrue(is_server_ready("http://127.0.0.1:8000"))

    def test_connection_error_is_not_ready(self):
        with patch(
            "application.browser_coordinator.urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            self.assertFalse(is_server_ready("http://127.0.0.1:8000"))


if __name__ == "__main__":
    unittest.main()
