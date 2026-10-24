import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

from launcher_app import LukerLauncher
from ui_dispatch import UiDispatcher


class FakeGCLManager:
    """只实现配置切换用到的管理器接口。"""

    def __init__(self, bat_path: Path, stop_result: bool = True) -> None:
        self.bat_path = bat_path
        self.stop_result = stop_result
        self.stop_calls = 0

    def stop(self) -> bool:
        self.stop_calls += 1
        return self.stop_result

    def add_log_callback(self, _callback: Callable[[str], None]) -> None:
        pass


class GCLConfigTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.old_bat = self.root / "old.bat"
        self.new_bat = self.root / "new.bat"
        self.old_bat.write_text("", encoding="utf-8")
        self.new_bat.write_text("", encoding="utf-8")
        self.logs: list[str] = []

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _make_launcher(self) -> LukerLauncher:
        # 绕过 __init__，避免注册全局配置回调；只装配本测试需要的状态
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher._process_busy = False
        launcher._pending_gcl_config = None
        launcher._ui = UiDispatcher(lambda _delay, _callback: None)
        launcher._ui.start()
        launcher.gcl_process_manager = None
        launcher.process_manager = None
        launcher.log_window = None
        launcher.tray_icon = None
        launcher._last_status = None

        def run_sync(func: Callable[[], None]) -> None:
            func()

        launcher._run_async = run_sync
        launcher._on_log = self.logs.append
        return launcher

    def test_change_during_start_waits_for_action_to_finish(self):
        launcher = self._make_launcher()
        old = FakeGCLManager(self.old_bat)
        launcher.gcl_process_manager = old
        launcher._process_busy = True

        launcher._on_gcl_config_change(False, None)

        self.assertEqual(old.stop_calls, 0)
        self.assertIs(launcher.gcl_process_manager, old)
        self.assertEqual(launcher._pending_gcl_config, (False, None))

        launcher._finish_process_action()
        launcher._ui.pump()

        self.assertEqual(old.stop_calls, 1)
        self.assertIsNone(launcher.gcl_process_manager)
        self.assertFalse(launcher._process_busy)
        self.assertIn("[启动器] GCL 功能已禁用", self.logs)

    def test_path_change_replaces_manager_after_old_one_stops(self):
        launcher = self._make_launcher()
        old = FakeGCLManager(self.old_bat)
        launcher.gcl_process_manager = old

        launcher._on_gcl_config_change(True, str(self.new_bat))
        launcher._ui.pump()

        self.assertEqual(old.stop_calls, 1)
        self.assertIsNot(launcher.gcl_process_manager, old)
        self.assertEqual(Path(launcher.gcl_process_manager.bat_path), self.new_bat)
        self.assertFalse(launcher._process_busy)

    def test_stop_failure_keeps_old_manager(self):
        launcher = self._make_launcher()
        old = FakeGCLManager(self.old_bat, stop_result=False)
        launcher.gcl_process_manager = old

        launcher._on_gcl_config_change(False, None)
        launcher._ui.pump()

        self.assertIs(launcher.gcl_process_manager, old)
        self.assertFalse(launcher._process_busy)
        self.assertTrue(any("未停止" in line for line in self.logs))

    def test_same_path_does_not_stop_manager(self):
        launcher = self._make_launcher()
        old = FakeGCLManager(self.old_bat)
        launcher.gcl_process_manager = old

        launcher._on_gcl_config_change(True, str(self.old_bat))

        self.assertEqual(old.stop_calls, 0)
        self.assertIs(launcher.gcl_process_manager, old)
        self.assertFalse(launcher._process_busy)

    def test_latest_config_wins_while_busy(self):
        launcher = self._make_launcher()
        old = FakeGCLManager(self.old_bat)
        launcher.gcl_process_manager = old
        launcher._process_busy = True

        launcher._on_gcl_config_change(False, None)
        launcher._on_gcl_config_change(True, str(self.new_bat))

        self.assertEqual(launcher._pending_gcl_config, (True, str(self.new_bat)))

        launcher._finish_process_action()
        launcher._ui.pump()

        self.assertEqual(old.stop_calls, 1)
        self.assertEqual(Path(launcher.gcl_process_manager.bat_path), self.new_bat)
        self.assertFalse(launcher._process_busy)

    def test_finish_resets_busy_and_applies_pending_config(self):
        launcher = self._make_launcher()
        old = FakeGCLManager(self.old_bat)
        launcher.gcl_process_manager = old
        launcher._process_busy = True
        launcher._pending_gcl_config = (False, None)

        launcher._finish_process_action()
        launcher._ui.pump()

        self.assertFalse(launcher._process_busy)
        self.assertIsNone(launcher.gcl_process_manager)
        self.assertEqual(old.stop_calls, 1)
        self.assertIn("[启动器] GCL 功能已禁用", self.logs)


if __name__ == "__main__":
    unittest.main()
