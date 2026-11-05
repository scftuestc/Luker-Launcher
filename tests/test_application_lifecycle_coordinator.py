import unittest

from application.lifecycle_coordinator import LifecycleCoordinator
from application.lifecycle_state import LifecycleState
from core.readiness import LukerState


class FakeWindow:
    def __init__(self) -> None:
        self.hidden = 0
        self.focused = 0
        self.quit_called = False

    def hide(self) -> None:
        self.hidden += 1

    def focus_force(self) -> None:
        self.focused += 1

    def quit(self) -> None:
        self.quit_called = True


class FakeTrayIcon:
    def __init__(self) -> None:
        self.visible: list[bool] = []
        self.stop_calls = 0

    def set_window_visible(self, visible: bool) -> None:
        self.visible.append(visible)

    def stop(self) -> None:
        self.stop_calls += 1


class FakeProcess:
    def __init__(self) -> None:
        self.stop_all_calls = 0

    def stop_all(self) -> None:
        self.stop_all_calls += 1


class FakeStatus:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


class FakeUi:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


class FakeConfig:
    def __init__(self, close_behavior: str = "ask") -> None:
        self.close_behavior = close_behavior


class FakePoster:
    def __init__(self) -> None:
        self.posted: list[tuple[object, object]] = []

    def post(self, callback, coalesce_key=None):
        self.posted.append((callback, coalesce_key))
        return True

    def post_control(self, callback):
        return True


class FakeRunner:
    def __init__(self, *, started: bool = True) -> None:
        self.started = started
        self.workers: list[object] = []

    def run(self, func, *, name=None):
        self.workers.append(func)
        return self.started


class FakeMessageBox:
    def __init__(self, *, yesnocancel=None, yesno=True) -> None:
        self.yesnocancel = yesnocancel
        self.yesno = yesno
        self.calls: list[str] = []

    def askyesnocancel(self, _title, _message, **_kwargs):
        self.calls.append("yesnocancel")
        return self.yesnocancel

    def askyesno(self, _title, _message, **_kwargs):
        self.calls.append("yesno")
        return self.yesno


class LifecycleCoordinatorTests(unittest.TestCase):
    def make_coordinator(
        self,
        *,
        close_behavior: str = "ask",
        tray_ready: bool = True,
        updating: bool = False,
        runner_started: bool = True,
        messagebox_api=None,
    ):
        self.window = FakeWindow()
        self.tray = FakeTrayIcon()
        self.process = FakeProcess()
        self.status = FakeStatus()
        self.ui = FakeUi()
        self.config = FakeConfig(close_behavior)
        self.lifecycle = LifecycleState()
        self.poster = FakePoster()
        self.runner = FakeRunner(started=runner_started)
        self.logs: list[str] = []
        self.running = True
        self.updating = updating
        self.tray_ready = tray_ready
        self.messagebox = messagebox_api or FakeMessageBox()

        def hide_window() -> None:
            self.window.hide()
            self.tray.set_window_visible(False)

        self.coordinator = LifecycleCoordinator(
            config=self.config,
            process=self.process,
            status=self.status,
            ui=self.ui,
            task_runner=self.runner,
            post_ui=self.poster,
            log=self.logs.append,
            lifecycle=self.lifecycle,
            window_provider=lambda: self.window,
            tray_icon_provider=lambda: self.tray,
            tray_ready=lambda: self.tray_ready,
            hide_window=hide_window,
            current_state=lambda: LukerState.READY,
            is_updating=lambda: self.updating,
            set_running=self.set_running,
            close_dialog=self.fake_show,
            messagebox_api=self.messagebox,
            exit_key="exit",
        )
        return self.coordinator

    def set_running(self, value: bool) -> None:
        self.running = value

    def fake_show(self, parent, state, *, allow_hide, on_hide, on_exit, on_cancel):
        self.dialog = {
            "parent": parent,
            "state": state,
            "allow_hide": allow_hide,
            "hide": on_hide,
            "exit": on_exit,
            "cancel": on_cancel,
        }

    def run_posted(self) -> None:
        while self.poster.posted:
            self.poster.posted.pop(0)[0]()

    def test_ask_hide_without_remember_hides_and_keeps_setting(self):
        coordinator = self.make_coordinator()

        coordinator.request_exit()
        self.assertTrue(coordinator.exit_dialog_open)
        self.assertTrue(self.dialog["allow_hide"])
        self.dialog["hide"](False)

        self.assertEqual(self.window.hidden, 1)
        self.assertEqual(self.tray.visible, [False])
        self.assertFalse(self.lifecycle.exiting)
        self.assertEqual(self.config.close_behavior, "ask")
        self.assertFalse(coordinator.exit_dialog_open)

    def test_ask_hide_with_remember_saves_tray_behavior(self):
        coordinator = self.make_coordinator()

        coordinator.request_exit()
        self.dialog["hide"](True)

        self.assertEqual(self.window.hidden, 1)
        self.assertEqual(self.config.close_behavior, "tray")

    def test_ask_exit_with_remember_saves_exit_behavior(self):
        coordinator = self.make_coordinator()

        coordinator.request_exit()
        self.dialog["exit"](True)

        self.assertEqual(self.window.hidden, 1)
        self.assertEqual(self.config.close_behavior, "exit")
        self.assertTrue(self.lifecycle.exiting)
        self.assertFalse(self.running)
        self.assertEqual(len(self.runner.workers), 1)

        self.runner.workers[0]()
        self.run_posted()

        # 退出线程和随后的幂等 shutdown 各停一次就绪探测
        self.assertEqual(self.status.stop_calls, 2)
        self.assertEqual(self.process.stop_all_calls, 1)
        self.assertEqual(self.ui.stop_calls, 1)
        self.assertEqual(self.tray.stop_calls, 1)
        self.assertTrue(self.window.quit_called)

    def test_cancel_keeps_window_and_setting(self):
        coordinator = self.make_coordinator()

        coordinator.request_exit()
        self.dialog["cancel"]()

        self.assertEqual(self.window.hidden, 0)
        self.assertEqual(self.window.focused, 1)
        self.assertEqual(self.config.close_behavior, "ask")
        self.assertFalse(coordinator.exit_dialog_open)

    def test_remembered_tray_hides_without_dialog(self):
        coordinator = self.make_coordinator(close_behavior="tray")

        coordinator.request_exit()

        self.assertEqual(self.window.hidden, 1)
        self.assertFalse(self.lifecycle.exiting)

    def test_remembered_tray_falls_back_to_dialog_without_tray(self):
        coordinator = self.make_coordinator(close_behavior="tray", tray_ready=False)

        coordinator.request_exit()

        self.assertFalse(self.dialog["allow_hide"])
        self.dialog["cancel"]()
        self.assertEqual(self.window.hidden, 0)

    def test_remembered_exit_exits_without_dialog(self):
        coordinator = self.make_coordinator(close_behavior="exit")

        coordinator.request_exit()

        self.assertEqual(self.window.hidden, 1)
        self.assertTrue(self.lifecycle.exiting)
        self.assertEqual(len(self.runner.workers), 1)

    def test_ignores_when_already_exiting(self):
        coordinator = self.make_coordinator()
        self.lifecycle.exiting = True

        coordinator.request_exit()

        self.assertFalse(hasattr(self, "dialog"))

    def test_ignores_when_dialog_already_open(self):
        coordinator = self.make_coordinator()
        coordinator.request_exit()
        del self.dialog

        coordinator.request_exit()

        self.assertFalse(hasattr(self, "dialog"))

    def test_update_in_progress_blocks_close_request(self):
        coordinator = self.make_coordinator(updating=True)

        coordinator.request_exit()

        self.assertFalse(hasattr(self, "dialog"))
        self.assertFalse(self.lifecycle.exiting)
        self.assertTrue(any("正在更新" in line for line in self.logs))

    def test_update_in_progress_blocks_exit(self):
        coordinator = self.make_coordinator(updating=True)

        coordinator.exit()

        self.assertFalse(self.lifecycle.exiting)
        self.assertEqual(self.runner.workers, [])
        self.assertTrue(any("正在更新" in line for line in self.logs))

    def test_dialog_failure_falls_back_to_hide_prompt(self):
        coordinator = self.make_coordinator(messagebox_api=FakeMessageBox(yesnocancel=True))
        coordinator.close_dialog = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("boom")
        )

        with self.assertLogs("application.lifecycle_coordinator", level="ERROR"):
            coordinator.request_exit()

        self.assertEqual(self.messagebox.calls, ["yesnocancel"])
        self.assertEqual(self.window.hidden, 1)
        self.assertFalse(self.lifecycle.exiting)

    def test_dialog_failure_without_tray_falls_back_to_exit_prompt(self):
        coordinator = self.make_coordinator(
            tray_ready=False,
            messagebox_api=FakeMessageBox(yesno=True),
        )
        coordinator.close_dialog = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("boom")
        )

        with self.assertLogs("application.lifecycle_coordinator", level="ERROR"):
            coordinator.request_exit()

        self.assertEqual(self.messagebox.calls, ["yesno"])
        self.assertEqual(self.window.hidden, 1)
        self.assertTrue(self.lifecycle.exiting)

    def test_exit_runs_worker_and_posts_finish_on_normal_channel(self):
        coordinator = self.make_coordinator()

        coordinator.exit()

        self.assertTrue(self.lifecycle.exiting)
        self.assertFalse(self.running)
        self.assertEqual(len(self.runner.workers), 1)

        self.runner.workers[0]()

        self.assertEqual(len(self.poster.posted), 1)
        self.assertEqual(self.poster.posted[0][1], "exit")

    def test_exit_thread_failure_finishes_immediately(self):
        coordinator = self.make_coordinator(runner_started=False)

        with self.assertLogs("application.lifecycle_coordinator", level="ERROR"):
            coordinator.exit()

        self.assertTrue(self.lifecycle.exiting)
        self.assertTrue(self.window.quit_called)
        self.assertEqual(self.status.stop_calls, 1)

    def test_exit_is_ignored_when_already_exiting(self):
        coordinator = self.make_coordinator()
        self.lifecycle.exiting = True

        coordinator.exit()

        self.assertEqual(self.runner.workers, [])

    def test_shutdown_is_idempotent(self):
        coordinator = self.make_coordinator()

        coordinator.shutdown()
        coordinator.shutdown()

        self.assertEqual(self.status.stop_calls, 1)
        self.assertEqual(self.ui.stop_calls, 1)
        self.assertEqual(self.tray.stop_calls, 1)
        self.assertFalse(self.running)

    def test_finish_exit_quits_window_after_shutdown(self):
        coordinator = self.make_coordinator()

        coordinator.finish_exit()

        self.assertEqual(self.ui.stop_calls, 1)
        self.assertTrue(self.window.quit_called)


if __name__ == "__main__":
    unittest.main()
