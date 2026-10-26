import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import launcher_app
from core.version import (
    CommitInfo,
    LocalVersion,
    TargetInfo,
    UpdateProgress,
    UpdateResult,
    UpdateTarget,
    VersionCheck,
)
from launcher_app import LukerLauncher
from ui.dispatch import UiDispatcher


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


class FakeManager:
    def __init__(self, running: bool = True, path: str = "C:/Luker") -> None:
        self.luker_path = Path(path)
        self.is_running = running
        self.events: list[str] = []
        self.stop_result = True
        self.start_result = True

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


TARGET = UpdateTarget(
    kind="release",
    label="v2.8.0",
    sha="b" * 40,
    tag="v2.8.0",
)


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


class LauncherUpdateTests(unittest.TestCase):
    def make_launcher(
        self,
        *,
        running: bool = True,
        manager_path: str = "C:/Luker",
    ) -> tuple[LukerLauncher, FakeManager, FakeSettingsWindow, list[str]]:
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher._process_busy = False
        launcher._version_checking = False
        launcher._updating = False
        launcher._version_check_cache = None
        launcher._version_check_seq = 0
        launcher._ui = UiDispatcher(lambda _delay, _callback: None)
        launcher._ui.start()
        self.addCleanup(launcher._ui.stop)
        launcher._run_async = lambda func: func()
        launcher.settings_window = FakeSettingsWindow()
        manager = FakeManager(running=running, path=manager_path)
        launcher.process_manager = manager
        launcher._ensure_process_manager = lambda: manager
        launcher._reset_luker_readiness = lambda: None
        logs: list[str] = []
        launcher._on_log = lambda line: logs.append(line)
        launcher._finish_process_action = lambda: setattr(launcher, "_process_busy", False)
        return launcher, manager, launcher.settings_window, logs

    def test_check_runs_in_background_and_delivers_result(self):
        launcher, manager, window, _ = self.make_launcher()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
        )
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(
                launcher_app, "check_luker_versions", return_value=check
            ) as check_versions,
        ):
            self.assertTrue(launcher._request_luker_version_check())
            launcher._ui.pump()

        check_versions.assert_called_once_with(
            "C:/Luker",
            running_path=str(manager.luker_path),
        )
        self.assertIs(window.check, check)
        self.assertFalse(launcher._version_checking)

    def test_check_exception_becomes_error_result(self):
        launcher, _, window, _ = self.make_launcher()
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(
                launcher_app,
                "check_luker_versions",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(
                launcher_app,
                "read_local_version",
                return_value=local_version(),
            ),
        ):
            self.assertTrue(launcher._request_luker_version_check())
            launcher._ui.pump()

        self.assertIsNotNone(window.check)
        self.assertIn("检查版本失败", window.check.error)
        self.assertFalse(launcher._version_checking)

    def test_check_logs_release_and_commit_summary(self):
        launcher, _, _, logs = self.make_launcher()
        release, commit = remote_targets()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "check_luker_versions", return_value=check),
        ):
            self.assertTrue(launcher._request_luker_version_check())
            launcher._ui.pump()

        joined = "\n".join(logs)
        self.assertIn("正在检查 Luker 版本", joined)
        self.assertIn(f"当前版本：提交 {'a' * 40} · 2026-10-26", joined)
        self.assertIn(f"最新发行版：v2.8.0 · 发布于 2026-10-01 · 提交 {'b' * 40}", joined)
        self.assertIn(f"最新提交：2026-10-26 · {'c' * 40}", joined)

    def test_check_logs_error_when_no_targets(self):
        launcher, _, _, logs = self.make_launcher()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
            error="api failed",
        )
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "check_luker_versions", return_value=check),
        ):
            self.assertTrue(launcher._request_luker_version_check())
            launcher._ui.pump()

        self.assertIn("[错误] api failed", logs)

    def test_check_logs_warning_when_fetch_fails(self):
        launcher, _, _, logs = self.make_launcher()
        release, commit = remote_targets()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
            error="fetch failed",
        )
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "check_luker_versions", return_value=check),
        ):
            self.assertTrue(launcher._request_luker_version_check())
            launcher._ui.pump()

        self.assertIn("[警告] fetch failed", logs)

    def test_check_is_rejected_when_busy_or_exiting(self):
        launcher, _, _, _ = self.make_launcher()
        launcher._version_checking = True
        self.assertFalse(launcher._request_luker_version_check())
        launcher._version_checking = False
        launcher._exiting = True
        self.assertFalse(launcher._request_luker_version_check())
        launcher._exiting = False
        launcher._updating = True
        self.assertFalse(launcher._request_luker_version_check())

    def test_check_is_rejected_without_settings_window(self):
        launcher, _, _, _ = self.make_launcher()
        launcher.settings_window = None
        self.assertFalse(launcher._request_luker_version_check())

    def test_successful_check_is_cached(self):
        launcher, _, _, _ = self.make_launcher()
        release, commit = remote_targets()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "check_luker_versions", return_value=check),
        ):
            self.assertTrue(launcher._request_luker_version_check())
            launcher._ui.pump()

        self.assertIs(launcher._version_check_cache, check)

    def test_error_without_targets_is_not_cached(self):
        launcher, _, window, _ = self.make_launcher()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
            error="api failed",
        )
        launcher._version_check_seq = 1
        with patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")):
            launcher._deliver_version_check(check, 1)

        self.assertIsNone(launcher._version_check_cache)
        self.assertIs(window.check, check)

    def test_closed_window_still_caches_result(self):
        launcher, _, _, _ = self.make_launcher()
        release, commit = remote_targets()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        launcher.settings_window = None
        launcher._version_check_seq = 1
        with patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")):
            launcher._deliver_version_check(check, 1)

        self.assertIs(launcher._version_check_cache, check)

    def test_stale_check_result_is_ignored(self):
        launcher, _, window, _ = self.make_launcher()
        release, commit = remote_targets()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        launcher._version_check_seq = 2
        with patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")):
            launcher._deliver_version_check(check, 1)

        self.assertIsNone(launcher._version_check_cache)
        self.assertIsNone(window.check)

    def test_result_for_other_path_is_ignored(self):
        launcher, _, window, _ = self.make_launcher()
        release, commit = remote_targets()
        check = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        launcher._version_check_seq = 1
        with patch.object(launcher_app, "config", SimpleNamespace(luker_path="D:/Other")):
            launcher._deliver_version_check(check, 1)

        self.assertIsNone(launcher._version_check_cache)
        self.assertIsNone(window.check)

    def test_path_change_clears_cache_and_invalidates_check(self):
        launcher, _, _, _ = self.make_launcher()
        launcher._version_checking = True
        launcher._version_check_cache = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=None,
            commit=None,
        )
        launcher._version_check_seq = 1

        launcher._on_luker_path_changed()

        self.assertFalse(launcher._version_checking)
        self.assertIsNone(launcher._version_check_cache)
        self.assertEqual(launcher._version_check_seq, 2)

    def test_update_stops_applies_and_restarts(self):
        launcher, manager, window, logs = self.make_launcher()
        release, commit = remote_targets()
        launcher._version_check_cache = VersionCheck(
            repo_path="C:/Luker",
            local=local_version(),
            release=release,
            commit=commit,
        )
        events = []

        def fake_apply(path, target, on_stage=None):
            events.append(("apply", path, target.sha))
            self.assertEqual(manager.events, ["stop"])
            if on_stage is not None:
                on_stage("installing", "installing")
            return UpdateResult(True, False, "updated", True)

        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(launcher_app, "apply_luker_update", side_effect=fake_apply),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, ["stop", "start"])
        self.assertEqual(events, [("apply", str(manager.luker_path), TARGET.sha)])
        self.assertFalse(launcher._updating)
        self.assertFalse(launcher._process_busy)
        self.assertEqual(window.progress[-1].stage, "done")
        self.assertFalse(window.progress[-1].busy)
        self.assertIsNone(launcher._version_check_cache)
        self.assertTrue(any("Luker 已重启" in line for line in logs))

    def test_start_exception_after_update_reports_manual_start(self):
        launcher, manager, window, logs = self.make_launcher()

        def failing_start() -> bool:
            manager.events.append("start")
            raise OSError("boom")

        manager.start = failing_start
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(
                launcher_app,
                "apply_luker_update",
                return_value=UpdateResult(True, False, "updated", True),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, ["stop", "start"])
        self.assertEqual(window.progress[-1].level, "error")
        self.assertIn("Luker 启动异常", window.progress[-1].message)
        self.assertIn("请手动启动", window.progress[-1].message)
        self.assertTrue(any("启动异常" in line for line in logs))
        self.assertFalse(launcher._updating)

    def test_rollback_start_exception_reports_manual_start(self):
        launcher, manager, window, _ = self.make_launcher()

        def failing_start() -> bool:
            manager.events.append("start")
            raise OSError("boom")

        manager.start = failing_start
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(
                launcher_app,
                "apply_luker_update",
                return_value=UpdateResult(False, True, "failed", True),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, ["stop", "start"])
        self.assertEqual(window.progress[-1].level, "error")
        self.assertIn("原版本启动异常", window.progress[-1].message)
        self.assertIn("请手动启动", window.progress[-1].message)
        self.assertFalse(launcher._updating)

    def test_stop_failure_cancels_update(self):
        launcher, manager, window, _ = self.make_launcher()
        manager.stop_result = False
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(launcher_app, "apply_luker_update") as apply,
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        apply.assert_not_called()
        self.assertEqual(manager.events, ["stop"])
        self.assertEqual(window.progress[-1].level, "error")
        self.assertIn("未能完全停止", window.progress[-1].message)
        self.assertFalse(launcher._updating)

    def test_stopped_luker_is_not_started_after_update(self):
        launcher, manager, window, _ = self.make_launcher(running=False)
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(
                launcher_app,
                "apply_luker_update",
                return_value=UpdateResult(True, False, "updated", True),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, [])
        self.assertIn("未自动启动", window.progress[-1].message)
        self.assertEqual(window.progress[-1].level, "success")

    def test_rolled_back_update_restarts_old_version(self):
        launcher, manager, window, _ = self.make_launcher()
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(
                launcher_app,
                "apply_luker_update",
                return_value=UpdateResult(False, True, "failed", True),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, ["stop", "start"])
        self.assertEqual(window.progress[-1].level, "error")
        self.assertIn("failed", window.progress[-1].message)

    def test_failed_rollback_does_not_start_half_updated_luker(self):
        launcher, manager, window, _ = self.make_launcher()
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(
                launcher_app,
                "apply_luker_update",
                return_value=UpdateResult(False, False, "failed", True),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, ["stop"])
        self.assertIn("未自动启动", window.progress[-1].message)

    def test_update_failure_before_code_change_restarts_old_version(self):
        launcher, manager, window, _ = self.make_launcher()
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(
                launcher_app,
                "apply_luker_update",
                return_value=UpdateResult(False, False, "fetch failed", False),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, ["stop", "start"])
        self.assertIn("fetch failed", window.progress[-1].message)

    def test_update_is_rejected_when_process_is_busy(self):
        launcher, manager, _, _ = self.make_launcher()
        launcher._process_busy = True
        with patch.object(
            launcher_app,
            "config",
            SimpleNamespace(luker_path="C:/Luker"),
        ):
            self.assertFalse(launcher._apply_luker_update(TARGET))
        self.assertEqual(manager.events, [])

    def test_update_is_rejected_while_checking_versions(self):
        launcher, manager, _, _ = self.make_launcher()
        launcher._version_checking = True
        with patch.object(
            launcher_app,
            "config",
            SimpleNamespace(luker_path="C:/Luker"),
        ):
            self.assertFalse(launcher._apply_luker_update(TARGET))
        self.assertEqual(manager.events, [])

    def test_update_is_rejected_when_path_changed_while_running(self):
        launcher, manager, window, _ = self.make_launcher(manager_path="C:/Old")
        with patch.object(
            launcher_app,
            "config",
            SimpleNamespace(luker_path="C:/Luker"),
        ):
            self.assertFalse(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, [])
        self.assertIn("路径已更改", window.progress[-1].message)

    def test_preflight_git_checks_run_in_worker(self):
        launcher, manager, window, _ = self.make_launcher()
        pending = []
        launcher._run_async = pending.append

        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(
                launcher_app,
                "read_local_version",
                return_value=local_version(dirty=True),
            ) as read,
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            read.assert_not_called()
            self.assertEqual(manager.events, [])

            pending[0]()
            launcher._ui.pump()

        self.assertTrue(read.called)
        self.assertEqual(manager.events, [])
        self.assertIn("未提交", window.progress[-1].message)
        self.assertFalse(launcher._updating)

    def test_dirty_worktree_is_rejected_before_stopping(self):
        launcher, manager, window, _ = self.make_launcher()
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(
                launcher_app,
                "read_local_version",
                return_value=local_version(dirty=True),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, [])
        self.assertIn("未提交", window.progress[-1].message)
        self.assertFalse(launcher._updating)

    def test_closed_settings_window_does_not_break_update(self):
        launcher, manager, window, _ = self.make_launcher()
        window.alive = False
        with (
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
            patch.object(launcher_app, "read_local_version", return_value=local_version()),
            patch.object(
                launcher_app,
                "apply_luker_update",
                return_value=UpdateResult(True, False, "updated", True),
            ),
        ):
            self.assertTrue(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, ["stop", "start"])
        self.assertFalse(launcher._updating)


if __name__ == "__main__":
    unittest.main()
