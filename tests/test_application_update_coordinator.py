import unittest
from pathlib import Path

from application.lifecycle_state import LifecycleState
from application.update_coordinator import UpdateCoordinator
from core.version import (
    CommitInfo,
    LocalVersion,
    TargetInfo,
    UpdateProgress,
    UpdateResult,
    UpdateTarget,
    VersionCheck,
)

TARGET = UpdateTarget(
    kind="release",
    label="v2.8.0",
    sha="b" * 40,
    tag="v2.8.0",
)


class FakeConfig:
    def __init__(self, luker_path: str | None = "C:/Luker") -> None:
        self.luker_path = luker_path


class FakeManager:
    def __init__(
        self,
        path: str = "C:/Luker",
        running: bool = True,
        stop_result: bool = True,
        start_result: bool = True,
    ) -> None:
        self.luker_path = Path(path)
        self.is_running = running
        self.stop_result = stop_result
        self.start_result = start_result
        self.events: list[str] = []

    def stop(self) -> bool:
        self.events.append("stop")
        if self.stop_result:
            self.is_running = False
        return self.stop_result

    def start(self) -> bool:
        self.events.append("start")
        if self.start_result:
            self.is_running = True
        return self.start_result


class FakeProcess:
    def __init__(self, manager=None) -> None:
        self.manager = manager
        self.busy = False
        self.workers: list[object] = []
        self.finish_calls = 0
        self.start_failure = False

    def ensure_manager(self):
        return self.manager

    def start_worker(self, worker, *, on_failure=None, context="进程操作"):
        self.busy = True
        self.workers.append(worker)
        if self.start_failure:
            self.busy = False
            if on_failure is not None:
                on_failure()
            return False
        return True

    def finish_action(self) -> None:
        self.finish_calls += 1
        self.busy = False


class FakeStatus:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1


class FakeSettingsWindow:
    def __init__(self) -> None:
        self.alive = True
        self.check: VersionCheck | None = None
        self.progress: list[UpdateProgress] = []

    def is_alive(self) -> bool:
        return self.alive

    def set_version_check(self, check: VersionCheck) -> None:
        self.check = check

    def set_update_progress(self, progress: UpdateProgress) -> None:
        self.progress.append(progress)


class FakePoster:
    def __init__(self) -> None:
        self.posted: list[tuple[object, object]] = []
        self.controls: list[object] = []

    def post(self, callback, coalesce_key=None):
        self.posted.append((callback, coalesce_key))
        return True

    def post_control(self, callback):
        self.controls.append(callback)
        return True

    def run_controls(self) -> None:
        while self.controls:
            self.controls.pop(0)()


class FakeRunner:
    def __init__(self, *, started: bool = True) -> None:
        self.started = started
        self.workers: list[object] = []

    def run(self, func, *, name=None):
        self.workers.append(func)
        return self.started


def local_version(**overrides) -> LocalVersion:
    base = LocalVersion(
        repo_path="C:/Luker",
        git_available=True,
        npm_available=True,
        is_git_repo=True,
        describe="v2.8.0-75-g755925947",
        branch="release",
        head="a" * 40,
        short_head="aaaaaaa",
        date="2026-10-26",
        subject="local subject",
        dirty=False,
        path_matches=True,
    )
    return base if not overrides else LocalVersion(**{**base.__dict__, **overrides})


def remote_targets() -> tuple[TargetInfo, TargetInfo]:
    release = TargetInfo(
        kind="release",
        label="v2.8.0",
        tag="v2.8.0",
        branch=None,
        published_at="2026-10-01",
        commit=CommitInfo(
            sha="b" * 40,
            short_sha="bbbbbbb",
            date="2026-10-01",
            subject="release commit",
        ),
        relation="behind",
        ahead=0,
        behind=3,
        actionable=True,
        downgrade=False,
        status="有新发行版",
    )
    commit = TargetInfo(
        kind="commit",
        label="最新提交 ccccccc",
        tag=None,
        branch="release",
        published_at="",
        commit=CommitInfo(
            sha="c" * 40,
            short_sha="ccccccc",
            date="2026-10-26",
            subject="latest commit",
        ),
        relation="behind",
        ahead=0,
        behind=2,
        actionable=True,
        downgrade=False,
        status="有新提交",
    )
    return release, commit


class UpdateCoordinatorTests(unittest.TestCase):
    def make_coordinator(self):
        self.window = FakeSettingsWindow()
        self.poster = FakePoster()
        self.runner = FakeRunner()
        self.status = FakeStatus()
        self.logs: list[str] = []
        self.checks: list[tuple[str | None, str | None]] = []
        self.local_reads: list[tuple[str | None, str | None]] = []
        self.process = FakeProcess(FakeManager())
        self.config = FakeConfig()
        self.lifecycle = LifecycleState()

        def check_versions(repo_path, *, running_path=None):
            self.checks.append((repo_path, running_path))
            return VersionCheck(
                repo_path="C:/Luker",
                local=local_version(),
                release=None,
                commit=None,
            )

        def read_local(repo_path, *, running_path=None):
            self.local_reads.append((repo_path, running_path))
            return local_version(repo_path=repo_path or "C:/Luker")

        self.coordinator = UpdateCoordinator(
            config=self.config,
            process=self.process,
            status=self.status,
            task_runner=self.runner,
            post_ui=self.poster,
            log=self.logs.append,
            lifecycle=self.lifecycle,
            settings_provider=lambda: self.window,
            check_versions=check_versions,
            read_local=read_local,
        )
        return self.coordinator

    def test_check_runs_worker_and_delivers_result(self):
        coordinator = self.make_coordinator()
        result = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
        )

        def check_versions(repo_path, *, running_path=None):
            self.checks.append((repo_path, running_path))
            return result

        coordinator.check_versions = check_versions

        self.assertTrue(coordinator.request_check())
        self.assertTrue(coordinator.checking)
        self.assertEqual(self.checks, [])
        self.runner.workers[0]()

        self.assertEqual(self.checks, [("C:/Luker", str(Path("C:/Luker")))])
        self.assertFalse(coordinator.checking)
        self.assertEqual(len(self.poster.controls), 1)
        self.poster.run_controls()

        self.assertIs(self.window.check, result)

    def test_check_without_settings_window_returns_false(self):
        coordinator = self.make_coordinator()
        self.window = None

        self.assertFalse(coordinator.request_check())

    def test_check_rejected_when_busy_updating_or_exiting(self):
        coordinator = self.make_coordinator()
        coordinator.checking = True
        self.assertFalse(coordinator.request_check())

        coordinator.checking = False
        coordinator.updating = True
        self.assertFalse(coordinator.request_check())

        coordinator.updating = False
        self.lifecycle.exiting = True
        self.assertFalse(coordinator.request_check())

    def test_check_exception_becomes_error_result(self):
        coordinator = self.make_coordinator()

        def failing(*args, **kwargs):
            raise RuntimeError("boom")

        coordinator.check_versions = failing

        self.assertTrue(coordinator.request_check())
        with self.assertLogs("application.update_coordinator", level="ERROR"):
            self.runner.workers[0]()
        self.poster.run_controls()

        self.assertEqual(self.local_reads, [("C:/Luker", str(Path("C:/Luker")))])
        self.assertIsNotNone(self.window.check)
        self.assertIn("检查版本失败", self.window.check.error)
        self.assertFalse(coordinator.checking)

    def test_check_logs_release_and_commit_summary(self):
        coordinator = self.make_coordinator()
        release, commit = remote_targets()
        coordinator.check_versions = lambda *args, **kwargs: VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )

        coordinator.request_check()
        self.runner.workers[0]()

        joined = "\n".join(self.logs)
        self.assertIn("正在检查 Luker 版本", joined)
        self.assertIn(f"当前版本：提交 {'a' * 40} · 2026-10-26", joined)
        self.assertIn(f"最新发行版：v2.8.0 · 发布于 2026-10-01 · 提交 {'b' * 40}", joined)
        self.assertIn(f"最新提交：2026-10-26 · {'c' * 40}", joined)

    def test_check_logs_error_without_targets(self):
        coordinator = self.make_coordinator()
        coordinator.check_versions = lambda *args, **kwargs: VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
            error="api failed",
        )

        coordinator.request_check()
        self.runner.workers[0]()

        self.assertIn("[错误] api failed", self.logs)

    def test_check_logs_warning_when_fetch_fails_with_targets(self):
        coordinator = self.make_coordinator()
        release, commit = remote_targets()
        coordinator.check_versions = lambda *args, **kwargs: VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
            error="fetch failed",
        )

        coordinator.request_check()
        self.runner.workers[0]()

        self.assertIn("[警告] fetch failed", self.logs)

    def test_successful_check_is_cached(self):
        coordinator = self.make_coordinator()
        release, commit = remote_targets()
        result = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        coordinator.check_versions = lambda *args, **kwargs: result

        coordinator.request_check()
        self.runner.workers[0]()
        self.poster.run_controls()

        self.assertIs(coordinator.version_check_cache, result)

    def test_error_without_targets_is_not_cached(self):
        coordinator = self.make_coordinator()
        result = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
            error="api failed",
        )
        coordinator.version_check_seq = 1

        coordinator.deliver_check(result, 1)

        self.assertIsNone(coordinator.version_check_cache)
        self.assertIs(self.window.check, result)

    def test_closed_window_still_caches_result(self):
        coordinator = self.make_coordinator()
        release, commit = remote_targets()
        result = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        self.window = None
        coordinator.version_check_seq = 1

        coordinator.deliver_check(result, 1)

        self.assertIs(coordinator.version_check_cache, result)

    def test_stale_result_is_ignored(self):
        coordinator = self.make_coordinator()
        release, commit = remote_targets()
        result = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        coordinator.version_check_seq = 2

        coordinator.deliver_check(result, 1)

        self.assertIsNone(coordinator.version_check_cache)
        self.assertIsNone(self.window.check)

    def test_result_for_other_path_is_ignored(self):
        coordinator = self.make_coordinator()
        self.config.luker_path = "D:/Other"
        release, commit = remote_targets()
        result = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        coordinator.version_check_seq = 1

        coordinator.deliver_check(result, 1)

        self.assertIsNone(coordinator.version_check_cache)
        self.assertIsNone(self.window.check)

    def test_path_change_invalidates_cache_and_check(self):
        coordinator = self.make_coordinator()
        coordinator.checking = True
        coordinator.version_check_cache = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
        )
        coordinator.version_check_seq = 1

        coordinator.path_changed()

        self.assertFalse(coordinator.checking)
        self.assertIsNone(coordinator.version_check_cache)
        self.assertEqual(coordinator.version_check_seq, 2)

    def test_thread_failure_resets_checking(self):
        coordinator = self.make_coordinator()
        self.runner.started = False

        with self.assertLogs("application.update_coordinator", level="ERROR"):
            self.assertFalse(coordinator.request_check())

        self.assertFalse(coordinator.checking)


class UpdateExecutionTests(unittest.TestCase):
    def make_coordinator(
        self,
        *,
        running: bool = True,
        manager_path: str = "C:/Luker",
        local=None,
        result: UpdateResult | None = None,
    ) -> UpdateCoordinator:
        self.window = FakeSettingsWindow()
        self.poster = FakePoster()
        self.runner = FakeRunner()
        self.status = FakeStatus()
        self.logs: list[str] = []
        self.reads: list[str] = []
        self.applies: list[tuple[str, UpdateTarget]] = []
        self.manager = FakeManager(path=manager_path, running=running)
        self.process = FakeProcess(self.manager)
        self.config = FakeConfig()
        self.lifecycle = LifecycleState()
        self.local = local or local_version()
        self.result = result or UpdateResult(True, False, "updated", True)

        def read_local(path, **_kwargs):
            self.reads.append(path)
            return self.local

        def apply_update(path, target, on_stage=None):
            self.applies.append((path, target))
            if on_stage is not None:
                on_stage("installing", "installing")
            return self.result

        self.coordinator = UpdateCoordinator(
            config=self.config,
            process=self.process,
            status=self.status,
            task_runner=self.runner,
            post_ui=self.poster,
            log=self.logs.append,
            lifecycle=self.lifecycle,
            settings_provider=lambda: self.window,
            read_local=read_local,
            apply_update=apply_update,
        )
        return self.coordinator

    def run_worker(self) -> None:
        self.process.workers[0]()
        self.poster.run_controls()

    def test_update_stops_applies_and_restarts(self):
        coordinator = self.make_coordinator()

        self.assertTrue(coordinator.apply_update_target(TARGET))

        self.assertEqual(self.reads, [])
        self.run_worker()

        self.assertEqual(self.manager.events, ["stop", "start"])
        self.assertEqual(self.applies, [(str(self.manager.luker_path), TARGET)])
        self.assertFalse(coordinator.updating)
        self.assertFalse(self.process.busy)
        self.assertEqual(self.window.progress[-1].stage, "done")
        self.assertFalse(self.window.progress[-1].busy)
        self.assertIsNone(coordinator.version_check_cache)
        self.assertTrue(any("Luker 已重启" in line for line in self.logs))
        self.assertEqual(self.status.reset_calls, 1)
        self.assertEqual(self.poster.posted, [])

    def test_start_exception_after_update_reports_manual_start(self):
        coordinator = self.make_coordinator()

        def failing_start() -> bool:
            self.manager.events.append("start")
            raise OSError("boom")

        self.manager.start = failing_start

        with self.assertLogs("application.update_coordinator", level="ERROR"):
            coordinator.apply_update_target(TARGET)
            self.run_worker()

        self.assertEqual(self.manager.events, ["stop", "start"])
        self.assertEqual(self.window.progress[-1].level, "error")
        self.assertIn("Luker 启动异常", self.window.progress[-1].message)
        self.assertIn("请手动启动", self.window.progress[-1].message)
        self.assertFalse(coordinator.updating)

    def test_rollback_start_exception_reports_manual_start(self):
        coordinator = self.make_coordinator(result=UpdateResult(False, True, "failed", True))

        def failing_start() -> bool:
            self.manager.events.append("start")
            raise OSError("boom")

        self.manager.start = failing_start

        with self.assertLogs("application.update_coordinator", level="ERROR"):
            coordinator.apply_update_target(TARGET)
            self.run_worker()

        self.assertEqual(self.manager.events, ["stop", "start"])
        self.assertEqual(self.window.progress[-1].level, "error")
        self.assertIn("原版本启动异常", self.window.progress[-1].message)
        self.assertFalse(coordinator.updating)

    def test_stop_failure_cancels_update(self):
        coordinator = self.make_coordinator()
        self.manager.stop_result = False

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, ["stop"])
        self.assertEqual(self.applies, [])
        self.assertEqual(self.window.progress[-1].level, "error")
        self.assertIn("未能完全停止", self.window.progress[-1].message)
        self.assertFalse(coordinator.updating)

    def test_stopped_luker_is_not_started_after_update(self):
        coordinator = self.make_coordinator(running=False)

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, [])
        self.assertIn("未自动启动", self.window.progress[-1].message)
        self.assertEqual(self.window.progress[-1].level, "success")

    def test_rolled_back_update_restarts_old_version(self):
        coordinator = self.make_coordinator(result=UpdateResult(False, True, "failed", True))

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, ["stop", "start"])
        self.assertEqual(self.window.progress[-1].level, "error")
        self.assertIn("failed", self.window.progress[-1].message)

    def test_failed_rollback_does_not_start_half_updated_luker(self):
        coordinator = self.make_coordinator(result=UpdateResult(False, False, "failed", True))

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, ["stop"])
        self.assertIn("未自动启动", self.window.progress[-1].message)

    def test_update_failure_before_code_change_restarts_old_version(self):
        coordinator = self.make_coordinator(
            result=UpdateResult(False, False, "fetch failed", False)
        )

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, ["stop", "start"])
        self.assertIn("fetch failed", self.window.progress[-1].message)

    def test_update_is_rejected_when_process_is_busy(self):
        coordinator = self.make_coordinator()
        self.process.busy = True

        self.assertFalse(coordinator.apply_update_target(TARGET))
        self.assertEqual(self.process.workers, [])

    def test_update_is_rejected_while_checking_or_updating(self):
        coordinator = self.make_coordinator()
        coordinator.checking = True
        self.assertFalse(coordinator.apply_update_target(TARGET))

        coordinator.checking = False
        coordinator.updating = True
        self.assertFalse(coordinator.apply_update_target(TARGET))

        coordinator.updating = False
        self.lifecycle.exiting = True
        self.assertFalse(coordinator.apply_update_target(TARGET))

    def test_update_is_rejected_when_path_changed_while_running(self):
        coordinator = self.make_coordinator(manager_path="C:/Old")

        self.assertFalse(coordinator.apply_update_target(TARGET))
        self.poster.run_controls()

        self.assertEqual(self.manager.events, [])
        self.assertIn("路径已更改", self.window.progress[-1].message)

    def test_preflight_git_checks_run_in_worker(self):
        coordinator = self.make_coordinator(local=local_version(dirty=True))

        self.assertTrue(coordinator.apply_update_target(TARGET))
        self.assertEqual(self.reads, [])
        self.assertEqual(self.manager.events, [])

        self.run_worker()

        self.assertTrue(self.reads)
        self.assertEqual(self.manager.events, [])
        self.assertIn("未提交", self.window.progress[-1].message)
        self.assertFalse(coordinator.updating)

    def test_dirty_worktree_is_rejected_before_stopping(self):
        coordinator = self.make_coordinator(local=local_version(dirty=True))

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, [])
        self.assertIn("未提交", self.window.progress[-1].message)
        self.assertFalse(coordinator.updating)

    def test_missing_npm_is_rejected_before_stopping(self):
        coordinator = self.make_coordinator(local=local_version(npm_available=False))

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, [])
        self.assertIn("未找到 npm", self.window.progress[-1].message)

    def test_local_version_error_is_reported(self):
        coordinator = self.make_coordinator(local=local_version(error="git failed"))

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, [])
        self.assertIn("git failed", self.window.progress[-1].message)

    def test_closed_settings_window_does_not_break_update(self):
        coordinator = self.make_coordinator()
        self.window.alive = False

        coordinator.apply_update_target(TARGET)
        self.run_worker()

        self.assertEqual(self.manager.events, ["stop", "start"])
        self.assertFalse(coordinator.updating)

    def test_update_thread_failure_reports_error(self):
        coordinator = self.make_coordinator()
        self.process.start_failure = True

        self.assertFalse(coordinator.apply_update_target(TARGET))
        self.poster.run_controls()

        self.assertEqual(self.window.progress[-1].level, "error")
        self.assertIn("无法启动更新线程", self.window.progress[-1].message)
        self.assertFalse(coordinator.updating)

    def test_update_without_settings_window_returns_false(self):
        coordinator = self.make_coordinator()
        self.window = None

        self.assertFalse(coordinator.apply_update_target(TARGET))
        self.assertEqual(self.process.workers, [])

    def test_update_without_manager_reports_error(self):
        coordinator = self.make_coordinator()
        self.process.manager = None

        self.assertFalse(coordinator.apply_update_target(TARGET))
        self.poster.run_controls()

        self.assertEqual(self.window.progress[-1].level, "error")
        self.assertIn("未配置 Luker 路径", self.window.progress[-1].message)


if __name__ == "__main__":
    unittest.main()
