import unittest
from pathlib import Path

from application.lifecycle_state import LifecycleState
from application.process_coordinator import ProcessCoordinator


class FakeConfig:
    def __init__(
        self,
        *,
        luker_path: str | None = "C:/Luker",
        use_pwa_mode: bool = False,
        port: int = 8000,
    ) -> None:
        self.luker_path = luker_path
        self.use_pwa_mode = use_pwa_mode
        self.port = port

    def get_server_port(self) -> int:
        return self.port


class FakeManager:
    def __init__(
        self,
        *,
        path: str = "C:/Luker",
        running: bool = False,
        stop_result: bool = True,
        start_result: bool = True,
        restart_result: bool = True,
    ) -> None:
        self.luker_path = Path(path)
        self.is_running = running
        self.stop_result = stop_result
        self.start_result = start_result
        self.restart_result = restart_result
        self.events: list[str] = []
        self.log_callbacks: list[object] = []
        self.let_luker_open_browser = True
        self.server_port = None

    def add_log_callback(self, callback) -> None:
        self.log_callbacks.append(callback)

    def start(self) -> bool:
        self.events.append("start")
        if self.start_result:
            self.is_running = True
        return self.start_result

    def stop(self) -> bool:
        self.events.append("stop")
        if self.stop_result:
            self.is_running = False
        return self.stop_result

    def restart(self) -> bool:
        self.events.append("restart")
        if self.restart_result:
            self.is_running = True
        return self.restart_result


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

    def run_controls(self) -> None:
        while self.controls:
            self.controls.pop(0)()


class RecordingRunner:
    def __init__(self, *, started: bool = True) -> None:
        self.started = started
        self.workers: list[object] = []

    def run(self, func, *, name=None):
        self.workers.append(func)
        return self.started


class ImmediateRunner:
    def run(self, func, *, name=None):
        func()
        return True


class FakeManagerFactory:
    def __init__(self, *managers: FakeManager) -> None:
        self.managers = list(managers)
        self.calls: list[tuple[str, bool, int]] = []

    def __call__(self, path, *, let_luker_open_browser, server_port):
        self.calls.append((str(path), let_luker_open_browser, server_port))
        return self.managers.pop(0)


class ProcessCoordinatorTests(unittest.TestCase):
    def make_coordinator(
        self,
        *,
        config: FakeConfig | None = None,
        manager: FakeManager | None = None,
        runner=None,
        poster: FakePoster | None = None,
        factory: FakeManagerFactory | None = None,
        lifecycle: LifecycleState | None = None,
    ) -> tuple[ProcessCoordinator, FakePoster, RecordingRunner, list[str], list[str]]:
        self.config = config or FakeConfig()
        self.poster = poster or FakePoster()
        self.runner = runner or RecordingRunner()
        self.logs: list[str] = []
        self.calls: list[str] = []
        self.lifecycle = lifecycle or LifecycleState()
        self.coordinator = ProcessCoordinator(
            config=self.config,
            task_runner=self.runner,
            post_ui=self.poster,
            log=self.logs.append,
            lifecycle=self.lifecycle,
            manager_factory=factory or FakeManagerFactory(manager or FakeManager()),
            on_status_reset=lambda: self.calls.append("reset"),
            on_manager_replaced=lambda: self.calls.append("replaced"),
            on_finished=lambda: self.calls.append("finished"),
        )
        if manager is not None:
            self.coordinator.manager = manager
        return self.coordinator, self.poster, self.runner, self.logs, self.calls

    def test_ensure_manager_creates_and_configures(self):
        manager = FakeManager()
        factory = FakeManagerFactory(manager)
        coordinator, _, _, _, calls = self.make_coordinator(factory=factory)

        result = coordinator.ensure_manager()

        self.assertIs(result, manager)
        self.assertIs(coordinator.manager, manager)
        self.assertEqual(factory.calls, [("C:/Luker", True, 8000)])
        self.assertEqual(manager.log_callbacks, [coordinator.log])
        self.assertEqual(calls, ["replaced"])

    def test_ensure_manager_reuses_case_insensitive_path(self):
        manager = FakeManager(path="C:/Luker")
        factory = FakeManagerFactory()
        coordinator, _, _, _, calls = self.make_coordinator(
            config=FakeConfig(luker_path="c:\\luker", use_pwa_mode=True, port=9000),
            factory=factory,
        )
        coordinator.manager = manager

        result = coordinator.ensure_manager()

        self.assertIs(result, manager)
        self.assertEqual(factory.calls, [])
        self.assertFalse(manager.let_luker_open_browser)
        self.assertEqual(manager.server_port, 9000)
        self.assertEqual(calls, [])

    def test_ensure_manager_returns_none_without_configured_path(self):
        coordinator, _, _, _, _ = self.make_coordinator(config=FakeConfig(luker_path=None))

        self.assertIsNone(coordinator.ensure_manager())

    def test_ensure_manager_keeps_running_manager_for_other_path(self):
        manager = FakeManager(path="C:/Old", running=True)
        factory = FakeManagerFactory()
        coordinator, _, _, _, _ = self.make_coordinator(
            config=FakeConfig(luker_path="C:/New"),
            factory=factory,
        )
        coordinator.manager = manager

        self.assertIs(coordinator.ensure_manager(), manager)
        self.assertEqual(factory.calls, [])

    def test_start_resets_status_and_finishes_on_control_channel(self):
        manager = FakeManager()
        coordinator, poster, runner, _, calls = self.make_coordinator(manager=manager)

        coordinator.start()

        self.assertEqual(calls, ["reset"])
        self.assertTrue(coordinator.busy)
        self.assertEqual(len(runner.workers), 1)
        runner.workers[0]()
        self.assertEqual(manager.events, ["start"])
        self.assertEqual(len(poster.controls), 1)
        poster.run_controls()

        self.assertFalse(coordinator.busy)
        self.assertIn("finished", calls)

    def test_start_rejected_while_busy_or_exiting(self):
        manager = FakeManager()
        coordinator, _, runner, _, calls = self.make_coordinator(manager=manager)
        coordinator.busy = True

        coordinator.start()
        self.assertEqual(runner.workers, [])
        self.assertEqual(calls, [])

        coordinator.busy = False
        self.lifecycle.exiting = True
        coordinator.start()
        self.assertEqual(runner.workers, [])
        self.assertEqual(calls, [])

    def test_stop_does_not_reset_status(self):
        manager = FakeManager(running=True)
        coordinator, _, runner, _, calls = self.make_coordinator(manager=manager)

        coordinator.stop()

        self.assertEqual(calls, [])
        runner.workers[0]()
        self.assertEqual(manager.events, ["stop"])

    def test_restart_uses_restart_for_same_path(self):
        manager = FakeManager(running=True)
        coordinator, _, runner, _, calls = self.make_coordinator(manager=manager)

        coordinator.restart()

        self.assertEqual(calls, ["reset"])
        runner.workers[0]()
        self.assertEqual(manager.events, ["restart"])

    def test_restart_switches_path_and_adopts_new_manager(self):
        old = FakeManager(path="C:/Old", running=True)
        new = FakeManager(path="C:/New")
        factory = FakeManagerFactory(new)
        coordinator, poster, runner, _, calls = self.make_coordinator(
            config=FakeConfig(luker_path="C:/New"),
            factory=factory,
        )
        coordinator.manager = old

        coordinator.restart()

        # 与原实现一致：restart 和路径切换各自重置一次就绪状态
        self.assertEqual(calls, ["reset", "reset"])
        runner.workers[0]()

        self.assertEqual(old.events, ["stop"])
        self.assertEqual(new.events, ["start"])
        self.assertEqual(factory.calls, [("C:/New", True, 8000)])
        self.assertEqual(len(poster.controls), 2)
        self.assertIs(coordinator.manager, old)

        poster.run_controls()
        self.assertIs(coordinator.manager, new)
        self.assertIn("replaced", calls)
        self.assertFalse(coordinator.busy)

    def test_restart_path_stop_failure_cancels_switch(self):
        old = FakeManager(path="C:/Old", running=True, stop_result=False)
        factory = FakeManagerFactory()
        coordinator, poster, runner, logs, _ = self.make_coordinator(
            config=FakeConfig(luker_path="C:/New"),
            factory=factory,
        )
        coordinator.manager = old

        coordinator.restart()
        runner.workers[0]()

        self.assertEqual(old.events, ["stop"])
        self.assertEqual(factory.calls, [])
        self.assertIn("旧 Luker 进程未停止", logs[-1])
        self.assertEqual(len(poster.controls), 1)
        poster.run_controls()
        self.assertFalse(coordinator.busy)

    def test_restart_path_does_not_start_when_exiting_after_stop(self):
        old = FakeManager(path="C:/Old", running=True)
        new = FakeManager(path="C:/New")
        factory = FakeManagerFactory(new)
        coordinator, _, runner, _, _ = self.make_coordinator(
            config=FakeConfig(luker_path="C:/New"),
            factory=factory,
        )
        coordinator.manager = old

        coordinator.restart()
        self.lifecycle.exiting = True
        runner.workers[0]()

        self.assertEqual(old.events, ["stop"])
        self.assertEqual(new.events, [])
        self.assertIs(coordinator.manager, old)

    def test_adopt_is_rejected_during_exit(self):
        current = FakeManager()
        incoming = FakeManager()
        coordinator, _, runner, _, _ = self.make_coordinator()
        coordinator.manager = current
        self.lifecycle.exiting = True

        coordinator.adopt_manager(incoming)

        self.assertIs(coordinator.manager, current)
        self.assertEqual(len(runner.workers), 1)
        runner.workers[0]()
        self.assertEqual(incoming.events, ["stop"])

    def test_adopt_is_applied_when_not_exiting(self):
        incoming = FakeManager()
        coordinator, _, _, _, calls = self.make_coordinator()

        coordinator.adopt_manager(incoming)

        self.assertIs(coordinator.manager, incoming)
        self.assertEqual(calls, ["replaced"])

    def test_stop_all_rechecks_new_instances(self):
        first = FakeManager()
        second = FakeManager()
        coordinator, _, _, _, _ = self.make_coordinator()
        coordinator.manager = first
        original_stop = first.stop

        def stop_first() -> bool:
            result = original_stop()
            coordinator.manager = second
            return result

        first.stop = stop_first

        coordinator.stop_all()

        self.assertEqual(first.events, ["stop"])
        self.assertEqual(second.events, ["stop"])

    def test_action_failure_is_logged_and_finishes(self):
        manager = FakeManager()
        coordinator, poster, runner, logs, _ = self.make_coordinator(manager=manager)

        def action(_manager):
            raise RuntimeError("boom")

        with self.assertLogs("application.process_coordinator", level="ERROR"):
            coordinator.run_action(action)
            runner.workers[0]()

        self.assertIn("[错误] 进程操作失败，请查看日志", logs)
        poster.run_controls()
        self.assertFalse(coordinator.busy)

    def test_thread_start_failure_resets_busy_and_calls_failure_callback(self):
        coordinator, _, _, _, _ = self.make_coordinator()
        failures: list[str] = []
        self.runner.started = False

        with self.assertLogs("application.process_coordinator", level="ERROR"):
            started = coordinator.start_worker(
                lambda: None,
                on_failure=lambda: failures.append("failed"),
                context="测试",
            )

        self.assertFalse(started)
        self.assertFalse(coordinator.busy)
        self.assertEqual(failures, ["failed"])

    def test_success_keeps_busy_until_finish(self):
        coordinator, _, runner, _, _ = self.make_coordinator()

        self.assertTrue(coordinator.start_worker(lambda: None))

        self.assertTrue(coordinator.busy)
        self.assertEqual(len(runner.workers), 1)
        coordinator.finish_action()
        self.assertFalse(coordinator.busy)

    def test_busy_resets_when_ui_pump_is_inactive(self):
        manager = FakeManager()
        coordinator, _, runner, _, _ = self.make_coordinator(
            manager=manager,
            poster=FakePoster(accept=False),
        )

        coordinator.run_action(lambda _manager: True)
        runner.workers[0]()

        self.assertFalse(coordinator.busy)

    def test_action_uses_control_channel(self):
        manager = FakeManager()
        coordinator, poster, runner, _, _ = self.make_coordinator(manager=manager)

        coordinator.run_action(lambda _manager: True)
        runner.workers[0]()

        self.assertEqual(len(poster.controls), 1)

    def test_update_style_worker_clears_busy_with_immediate_runner(self):
        manager = FakeManager()
        coordinator, _, _, _, _ = self.make_coordinator(
            manager=manager,
            runner=ImmediateRunner(),
        )

        self.assertTrue(coordinator.start_worker(lambda: None))
        self.assertTrue(coordinator.busy)
        coordinator.finish_action()
        self.assertFalse(coordinator.busy)


if __name__ == "__main__":
    unittest.main()
