import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import launcher_app
from core.version import (
    LocalVersion,
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

    def test_check_is_rejected_when_busy_or_exiting(self):
        launcher, _, _, _ = self.make_launcher()
        launcher._version_checking = True
        self.assertFalse(launcher._request_luker_version_check())
        launcher._version_checking = False
        launcher._exiting = True
        self.assertFalse(launcher._request_luker_version_check())

    def test_check_is_rejected_without_settings_window(self):
        launcher, _, _, _ = self.make_launcher()
        launcher.settings_window = None
        self.assertFalse(launcher._request_luker_version_check())

    def test_update_stops_applies_and_restarts(self):
        launcher, manager, window, logs = self.make_launcher()
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
        self.assertTrue(any("Luker 已重启" in line for line in logs))

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
            self.assertFalse(launcher._apply_luker_update(TARGET))
            launcher._ui.pump()

        self.assertEqual(manager.events, [])
        self.assertIn("未提交", window.progress[-1].message)

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
