import unittest
from unittest.mock import Mock, patch

from luker_launcher.application import launcher as launcher_app
from luker_launcher.application.launcher import LukerLauncher


class LauncherCompositionTests(unittest.TestCase):
    def test_coordinators_share_the_same_runtime_objects(self):
        launcher = LukerLauncher()

        self.assertIs(launcher._process.task_runner, launcher._task_runner)
        self.assertIs(launcher._process.lifecycle, launcher._lifecycle)
        self.assertIs(launcher._status.process, launcher._process)
        self.assertIs(launcher._browser.lifecycle, launcher._lifecycle)
        self.assertIs(launcher._update.process, launcher._process)
        self.assertIs(launcher._update.status, launcher._status)
        self.assertIs(launcher._lifecycle_coordinator.process, launcher._process)
        self.assertIs(launcher._lifecycle_coordinator.status, launcher._status)
        self.assertIs(launcher._lifecycle_coordinator.ui, launcher._ui)

    def test_providers_read_current_launcher_windows(self):
        launcher = LukerLauncher()

        self.assertIsNone(launcher._update.settings_provider())
        self.assertIsNone(launcher._lifecycle_coordinator.window_provider())
        self.assertIsNone(launcher._lifecycle_coordinator.tray_icon_provider())

        window = object()
        launcher.log_window = window
        launcher.settings_window = window

        self.assertIs(launcher._update.settings_provider(), window)
        self.assertIs(launcher._lifecycle_coordinator.window_provider(), window)

    def test_launcher_has_no_business_logic_wrappers(self):
        launcher = LukerLauncher()

        for name in (
            "process_manager",
            "_on_start",
            "_on_stop",
            "_on_restart",
            "_apply_luker_update",
            "_start_process_worker",
            "_ensure_process_manager",
            "_update_status",
            "_schedule_status_poll",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(launcher, name))

    def test_log_window_receives_coordinator_callbacks(self):
        launcher = object.__new__(LukerLauncher)
        launcher._process = Mock()
        launcher._lifecycle_coordinator = Mock()
        launcher._on_log = Mock()

        with (
            patch.object(launcher_app, "LogWindow") as log_window_cls,
            patch.object(launcher_app.logging_setup, "add_ui_log_sink") as add_sink,
        ):
            launcher._create_log_window()

        kwargs = log_window_cls.call_args.kwargs
        self.assertIs(kwargs["on_start"], launcher._process.start)
        self.assertIs(kwargs["on_stop"], launcher._process.stop)
        self.assertIs(kwargs["on_exit"], launcher._lifecycle_coordinator.request_exit)
        add_sink.assert_called_once_with(launcher._on_log)

    def test_tray_menu_receives_coordinator_callbacks(self):
        launcher = object.__new__(LukerLauncher)
        launcher.log_window = object()
        launcher._process = Mock()
        launcher._browser = Mock()
        launcher._lifecycle_coordinator = Mock()
        launcher._on_show_window = Mock()
        launcher._on_hide_window = Mock()
        launcher._on_settings = Mock()

        with patch.object(launcher_app, "TrayMenu") as tray_menu_cls:
            launcher._create_tray_menu()

        callbacks = tray_menu_cls.call_args.args[1]
        self.assertIs(callbacks["show_window"], launcher._on_show_window)
        self.assertIs(callbacks["hide_window"], launcher._on_hide_window)
        self.assertIs(callbacks["start"], launcher._process.start)
        self.assertIs(callbacks["stop"], launcher._process.stop)
        self.assertIs(callbacks["restart"], launcher._process.restart)
        self.assertIs(callbacks["settings"], launcher._on_settings)
        self.assertIs(callbacks["open_browser"], launcher._browser.open)
        self.assertIs(callbacks["exit"], launcher._lifecycle_coordinator.exit)


if __name__ == "__main__":
    unittest.main()
