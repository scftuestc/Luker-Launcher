import unittest
from pathlib import Path

from application.lifecycle_state import LifecycleState
from application.update_coordinator import UpdateCoordinator
from core.version import (
    CommitInfo,
    LocalVersion,
    TargetInfo,
    VersionCheck,
)


class FakeConfig:
    def __init__(self, luker_path: str | None = "C:/Luker") -> None:
        self.luker_path = luker_path


class FakeManager:
    def __init__(self, path: str = "C:/Luker", running: bool = True) -> None:
        self.luker_path = Path(path)
        self.is_running = running


class FakeProcess:
    def __init__(self, manager=None) -> None:
        self.manager = manager


class FakeStatus:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1


class FakeSettingsWindow:
    def __init__(self) -> None:
        self.alive = True
        self.check: VersionCheck | None = None

    def is_alive(self) -> bool:
        return self.alive

    def set_version_check(self, check: VersionCheck) -> None:
        self.check = check


class FakePoster:
    def __init__(self) -> None:
        self.controls: list[object] = []

    def post(self, callback, coalesce_key=None):
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


if __name__ == "__main__":
    unittest.main()
