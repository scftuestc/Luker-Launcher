import unittest
from unittest.mock import MagicMock, patch

import launcher_app
import main
from launcher_app import LukerLauncher


class MainStartupTests(unittest.TestCase):
    def test_second_instance_shows_message_and_skips_launcher(self):
        order: list[str] = []

        with (
            patch.object(main.logging_setup, 'setup_logging') as setup_mock,
            patch.object(main, 'setup_dpi_awareness') as dpi_mock,
            patch.object(main.ctk, 'set_appearance_mode') as appearance_mock,
            patch.object(main.ctk, 'set_default_color_theme') as theme_mock,
            patch.object(
                main.single_instance,
                'acquire',
                side_effect=lambda: order.append('acquire') or False,
            ),
            patch.object(
                main.single_instance,
                'release',
                side_effect=lambda: order.append('release'),
            ) as release_mock,
            patch.object(main, 'LukerLauncher') as launcher_cls,
            patch.object(main.win32_api, 'user32') as user32,
        ):
            setup_mock.side_effect = lambda: order.append('logging')
            main.main()

        self.assertEqual(order, ['logging', 'acquire'])
        setup_mock.assert_called_once_with()
        dpi_mock.assert_called_once_with()
        appearance_mock.assert_called_once_with('dark')
        theme_mock.assert_called_once_with('dark-blue')
        launcher_cls.assert_not_called()
        release_mock.assert_not_called()
        message = user32.MessageBoxW.call_args.args[1]
        self.assertIn("已在运行", message)

    def test_normal_startup_runs_launcher_and_releases_mutex(self):
        order: list[str] = []
        launcher = MagicMock()

        with (
            patch.object(main.logging_setup, 'setup_logging') as setup_mock,
            patch.object(main, 'setup_dpi_awareness'),
            patch.object(main.ctk, 'set_appearance_mode'),
            patch.object(main.ctk, 'set_default_color_theme'),
            patch.object(
                main.single_instance,
                'acquire',
                side_effect=lambda: order.append('acquire') or True,
            ),
            patch.object(
                main.single_instance,
                'release',
                side_effect=lambda: order.append('release'),
            ) as release_mock,
            patch.object(main, 'LukerLauncher', return_value=launcher),
            patch.object(main, 'windll'),
        ):
            setup_mock.side_effect = lambda: order.append('logging')
            launcher.run.side_effect = lambda: order.append('run')
            main.main()

        launcher.run.assert_called_once_with()
        release_mock.assert_called_once_with()
        self.assertEqual(order, ['logging', 'acquire', 'run', 'release'])

    def test_launcher_failure_still_releases_mutex(self):
        launcher = MagicMock()
        launcher.run.side_effect = RuntimeError("boom")

        with (
            patch.object(main.logging_setup, 'setup_logging'),
            patch.object(main, 'setup_dpi_awareness'),
            patch.object(main.ctk, 'set_appearance_mode'),
            patch.object(main.ctk, 'set_default_color_theme'),
            patch.object(main.single_instance, 'acquire', return_value=True),
            patch.object(main.single_instance, 'release') as release_mock,
            patch.object(main, 'LukerLauncher', return_value=launcher),
            patch.object(main, 'windll'),
            self.assertRaises(RuntimeError),
        ):
            main.main()

        release_mock.assert_called_once_with()


class ConfigErrorReportingTests(unittest.TestCase):
    def test_reports_load_error_after_logging_setup(self):
        order: list[str] = []

        with (
            patch.object(main.logging_setup, 'setup_logging') as setup_mock,
            patch.object(main, 'setup_dpi_awareness'),
            patch.object(main.ctk, 'set_appearance_mode'),
            patch.object(main.ctk, 'set_default_color_theme'),
            patch.object(main.config, 'report_load_error') as report_mock,
            patch.object(main.single_instance, 'acquire', return_value=False),
            patch.object(main.win32_api, 'user32') as user32,
        ):
            setup_mock.side_effect = lambda: order.append('logging')
            report_mock.side_effect = lambda: order.append('report') or False
            main.main()

        self.assertEqual(order, ['logging', 'report'])
        report_mock.assert_called_once_with()
        user32.MessageBoxW.assert_called_once()


class DpiAwarenessTests(unittest.TestCase):
    def test_prefers_per_monitor_v2_context(self):
        with (
            patch.object(main, 'windll') as windll_mock,
            patch.object(main, 'get_process_dpi_awareness', return_value=2),
            self.assertLogs('main', level='INFO') as logs,
        ):
            main.setup_dpi_awareness()

        windll_mock.user32.SetProcessDpiAwarenessContext.assert_called_once()
        windll_mock.shcore.SetProcessDpiAwareness.assert_not_called()
        self.assertIn("Per-Monitor", logs.output[0])

    def test_falls_back_to_shcore_when_context_is_missing(self):
        with (
            patch.object(main, 'windll') as windll_mock,
            patch.object(main, 'get_process_dpi_awareness', return_value=2),
            patch.object(main, 'logger'),
        ):
            windll_mock.user32.SetProcessDpiAwarenessContext.side_effect = AttributeError
            windll_mock.shcore.SetProcessDpiAwareness.return_value = 0
            main.setup_dpi_awareness()

        windll_mock.shcore.SetProcessDpiAwareness.assert_called_once_with(2)
        windll_mock.user32.SetProcessDPIAware.assert_not_called()

    def test_falls_back_to_system_dpi_awareness(self):
        with (
            patch.object(main, 'windll') as windll_mock,
            patch.object(main, 'get_process_dpi_awareness', return_value=1),
            patch.object(main, 'logger'),
        ):
            windll_mock.user32.SetProcessDpiAwarenessContext.side_effect = OSError
            windll_mock.shcore.SetProcessDpiAwareness.side_effect = OSError
            main.setup_dpi_awareness()

        windll_mock.user32.SetProcessDPIAware.assert_called_once_with()

    def test_reports_unknown_awareness(self):
        with (
            patch.object(main, 'get_process_dpi_awareness', return_value=None),
            self.assertLogs('main', level='WARNING') as logs,
        ):
            main._log_dpi_awareness()

        self.assertIn("无法读取 DPI 感知模式", logs.output[0])


class FirstRunCancelTests(unittest.TestCase):
    def test_unconfigured_path_returns_without_creating_window(self):
        launcher = object.__new__(LukerLauncher)

        with (
            patch.object(
                launcher_app,
                'ensure_luker_path_configured',
                return_value=False,
            ),
            patch.object(launcher_app.messagebox, 'showinfo') as showinfo,
            self.assertLogs('launcher_app', level='ERROR') as logs,
        ):
            launcher.run()

        self.assertIn("未配置 Luker 路径", logs.output[0])
        showinfo.assert_called_once()
        self.assertIn("程序将退出", showinfo.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
