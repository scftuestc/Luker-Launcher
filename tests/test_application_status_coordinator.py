import unittest

from luker_launcher.application.status_coordinator import StatusCoordinator
from luker_launcher.services.readiness import LukerState


class FakeManager:
    def __init__(self, *, running: bool = True) -> None:
        self.is_running = running


class FakeProcess:
    def __init__(self, manager=None) -> None:
        self.manager = manager


class FakeConfig:
    def get_server_url(self) -> str:
        return "http://127.0.0.1:8000"


class FakePoster:
    def __init__(self) -> None:
        self.posted: list[tuple[object, object]] = []

    def post(self, callback, coalesce_key=None):
        self.posted.append((callback, coalesce_key))
        return True

    def post_control(self, callback):
        return True


class FakeReadiness:
    def __init__(self, is_running, get_url, on_change) -> None:
        self.is_running = is_running
        self.get_url = get_url
        self.on_change = on_change
        self.state = LukerState.STOPPED
        self.started = False
        self.reset_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.started = True

    def reset(self) -> None:
        self.reset_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


class FakeReadinessFactory:
    def __init__(self) -> None:
        self.instances: list[FakeReadiness] = []

    def __call__(self, is_running, get_url, on_change):
        readiness = FakeReadiness(is_running, get_url, on_change)
        self.instances.append(readiness)
        return readiness


class StatusCoordinatorTests(unittest.TestCase):
    def make_coordinator(
        self,
        *,
        manager=None,
        running: bool = True,
    ) -> tuple[StatusCoordinator, FakeProcess, FakePoster, FakeReadinessFactory]:
        self.process = FakeProcess(manager)
        self.poster = FakePoster()
        self.factory = FakeReadinessFactory()
        self.app_running = running
        self.applied: list[LukerState] = []
        self.tray: list[bool] = []
        self.scheduled: list[tuple[int, object]] = []
        self.logs: list[str] = []
        self.coordinator = StatusCoordinator(
            process=self.process,
            config=FakeConfig(),
            post_ui=self.poster,
            log=self.logs.append,
            apply_state=self.applied.append,
            update_tray_status=self.tray.append,
            schedule=lambda delay, callback: self.scheduled.append((delay, callback)),
            is_running=lambda: self.app_running,
            readiness_factory=self.factory,
            poll_interval_ms=2000,
        )
        self.coordinator.start()
        return self.coordinator, self.process, self.poster, self.factory

    def readiness(self) -> FakeReadiness:
        return self.factory.instances[0]

    def test_start_creates_and_starts_readiness(self):
        manager = FakeManager()
        coordinator, process, _, _ = self.make_coordinator(manager=manager)

        readiness = self.readiness()

        self.assertTrue(readiness.started)
        self.assertIs(readiness.get_url.__self__, coordinator.config)
        self.assertTrue(readiness.is_running())
        self.assertEqual(readiness.get_url(), "http://127.0.0.1:8000")
        process.manager = None
        self.assertFalse(readiness.is_running())

    def test_stopped_without_running_manager(self):
        coordinator, process, _, _ = self.make_coordinator(manager=None)

        self.assertIs(coordinator.current_state(), LukerState.STOPPED)

        process.manager = FakeManager(running=False)
        self.assertIs(coordinator.current_state(), LukerState.STOPPED)

    def test_starting_when_process_alive_but_service_not_ready(self):
        self.make_coordinator(manager=FakeManager())

        self.readiness().state = LukerState.STARTING

        self.assertIs(self.coordinator.current_state(), LukerState.STARTING)

    def test_ready_when_service_is_ready(self):
        self.make_coordinator(manager=FakeManager())

        self.readiness().state = LukerState.READY

        self.assertIs(self.coordinator.current_state(), LukerState.READY)

    def test_stale_callback_recomputes_current_ready_state(self):
        self.make_coordinator(manager=FakeManager())
        self.readiness().state = LukerState.READY

        self.coordinator.on_luker_state_change(LukerState.STARTING)

        self.assertEqual(len(self.poster.posted), 1)
        callback, key = self.poster.posted[0]
        self.assertEqual(key, "luker_state")
        callback()
        self.assertEqual(self.applied, [LukerState.READY])

    def test_apply_state_is_deduplicated(self):
        coordinator, _, _, _ = self.make_coordinator()

        coordinator.apply_state(LukerState.STARTING)
        coordinator.apply_state(LukerState.STARTING)
        coordinator.apply_state(LukerState.READY)

        self.assertEqual(self.applied, [LukerState.STARTING, LukerState.READY])

    def test_reset_clears_state_and_readiness(self):
        coordinator, _, _, _ = self.make_coordinator()
        coordinator.apply_state(LukerState.READY)

        coordinator.reset()
        coordinator.apply_state(LukerState.READY)

        self.assertEqual(self.readiness().reset_calls, 1)
        self.assertEqual(self.applied, [LukerState.READY, LukerState.READY])

    def test_clear_last_state_does_not_reset_readiness(self):
        coordinator, _, _, _ = self.make_coordinator()
        coordinator.apply_state(LukerState.READY)

        coordinator.clear_last_state()
        coordinator.apply_state(LukerState.READY)

        self.assertEqual(self.readiness().reset_calls, 0)
        self.assertEqual(self.applied, [LukerState.READY, LukerState.READY])

    def test_update_without_manager_does_not_touch_tray(self):
        coordinator, _, _, _ = self.make_coordinator(manager=None)

        coordinator.update()

        self.assertEqual(self.tray, [])
        self.assertEqual(self.applied, [])

    def test_update_reports_tray_and_current_state(self):
        self.make_coordinator(manager=FakeManager(running=True))
        self.readiness().state = LukerState.READY

        self.coordinator.update()

        self.assertEqual(self.tray, [True])
        self.assertEqual(self.applied, [LukerState.READY])

    def test_schedule_poll_updates_and_requeues(self):
        self.make_coordinator(manager=FakeManager(running=True))

        self.coordinator.schedule_poll()

        self.assertEqual(len(self.scheduled), 1)
        self.assertEqual(self.scheduled[0][0], 2000)
        self.assertEqual(self.scheduled[0][1], self.coordinator.schedule_poll)

    def test_schedule_poll_logs_failure_and_requeues(self):
        self.make_coordinator(manager=FakeManager(running=True))
        coordinator = self.coordinator
        coordinator.update = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

        with self.assertLogs("luker_launcher.application.status_coordinator", level="ERROR"):
            coordinator.schedule_poll()

        self.assertEqual(len(self.scheduled), 1)

    def test_schedule_poll_stops_when_app_is_not_running(self):
        self.make_coordinator(manager=FakeManager(running=True), running=False)

        self.coordinator.schedule_poll()

        self.assertEqual(self.scheduled, [])

    def test_stop_stops_readiness(self):
        coordinator, _, _, _ = self.make_coordinator()

        coordinator.stop()

        self.assertEqual(self.readiness().stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
