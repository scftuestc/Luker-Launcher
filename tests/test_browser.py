import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import core.browser as browser
import launcher_app
from launcher_app import LukerLauncher

VALID_FAMILY_NAME = "127.0.0.1-test_8wekyb3d8bbwe"


class PwaTimeoutTests(unittest.TestCase):
    def test_is_appx_installed_timeout_returns_false(self):
        timeout = subprocess.TimeoutExpired("powershell", 10)
        with patch.object(browser.subprocess, "run", side_effect=timeout):
            self.assertFalse(browser.is_appx_installed(VALID_FAMILY_NAME))

    def test_discover_luker_appx_timeout_returns_none(self):
        timeout = subprocess.TimeoutExpired("powershell", 10)
        browser._discovered_appx = None
        browser._discovery_checked_at = None
        try:
            with (
                patch.object(browser.time, "monotonic", return_value=1000.0),
                patch.object(browser.subprocess, "run", side_effect=timeout) as run,
            ):
                self.assertIsNone(browser.discover_luker_appx())
            run.assert_called_once()
        finally:
            browser._discovered_appx = None
            browser._discovery_checked_at = None


class AppxFamilyNameTests(unittest.TestCase):
    def test_accepts_valid_family_name(self):
        self.assertTrue(browser.is_valid_appx_family_name(VALID_FAMILY_NAME))

    def test_rejects_quotes_and_wildcards(self):
        self.assertFalse(browser.is_valid_appx_family_name("x'; calc; #_8wekyb3d8bbwe"))
        self.assertFalse(browser.is_valid_appx_family_name("127.0.0.1-*_8wekyb3d8bbwe"))

    def test_is_appx_installed_skips_powershell_for_invalid_name(self):
        with patch.object(browser.subprocess, "run") as run:
            self.assertFalse(browser.is_appx_installed("x'; calc; #"))
        run.assert_not_called()

    def test_is_appx_installed_queries_valid_name(self):
        completed = Mock()
        completed.stdout = "PackageFullName\n"
        with patch.object(browser.subprocess, "run", return_value=completed) as run:
            self.assertTrue(browser.is_appx_installed(VALID_FAMILY_NAME))

        command = run.call_args.args[0]
        self.assertEqual(command[0], "powershell")
        self.assertIn("'127.0.0.1-test'", command[-1])


class PwaDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        browser._discovered_appx = None
        browser._discovery_checked_at = None

    def tearDown(self) -> None:
        browser._discovered_appx = None
        browser._discovery_checked_at = None

    def test_first_call_runs_shortly_after_boot(self):
        completed = Mock()
        completed.stdout = ""
        with (
            patch.object(browser.time, "monotonic", return_value=5.0),
            patch.object(browser.subprocess, "run", return_value=completed) as run,
        ):
            self.assertIsNone(browser.discover_luker_appx())

        run.assert_called_once()

    def test_failed_discovery_backs_off(self):
        completed = Mock()
        completed.stdout = ""
        with (
            patch.object(
                browser.time,
                "monotonic",
                side_effect=[1000.0, 1030.0, 1061.0],
            ),
            patch.object(browser.subprocess, "run", return_value=completed) as run,
        ):
            self.assertIsNone(browser.discover_luker_appx())
            self.assertIsNone(browser.discover_luker_appx())
            self.assertIsNone(browser.discover_luker_appx())

        self.assertEqual(run.call_count, 2)

    def test_success_is_cached(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AppxManifest.xml").write_text(
                "<Package><DisplayName>Luker</DisplayName>"
                '<Application Id="LukerApp" /></Package>',
                encoding="utf-8",
            )
            completed = Mock()
            completed.stdout = json.dumps(
                [
                    {
                        "InstallLocation": str(root),
                        "PackageFamilyName": VALID_FAMILY_NAME,
                    }
                ]
            )

            with patch.object(browser.subprocess, "run", return_value=completed) as run:
                first = browser.discover_luker_appx()
                second = browser.discover_luker_appx()

        self.assertEqual(first, (VALID_FAMILY_NAME, "LukerApp"))
        self.assertEqual(second, first)
        run.assert_called_once()


class AutoOpenRoutingTests(unittest.TestCase):
    def test_auto_open_posts_shared_browser_entry(self):
        launcher = object.__new__(LukerLauncher)
        launcher._running = True
        posted = []
        launcher._post_ui = lambda callback: posted.append(callback)
        launcher._on_log = lambda _line: None
        launcher._open_browser_now = lambda: self.fail("自动打开应复用 _on_open_browser")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class FakeThread:
            def __init__(self, target, daemon):
                self._target = target

            def start(self):
                self._target()

        with (
            patch.object(launcher_app.urllib.request, "urlopen", return_value=FakeResponse()),
            patch.object(launcher_app, "Thread", FakeThread),
        ):
            launcher._schedule_auto_open_browser()

        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0].__self__, launcher)
        self.assertIs(posted[0].__func__, LukerLauncher._on_open_browser)


class BrowserOpenDelegationTests(unittest.TestCase):
    def test_open_browser_now_delegates_pwa_preference(self):
        for prefer_pwa in (True, False):
            with self.subTest(prefer_pwa=prefer_pwa):
                launcher = object.__new__(LukerLauncher)
                fake_config = Mock()
                fake_config.use_pwa_mode = prefer_pwa
                fake_config.get_server_url.return_value = "http://127.0.0.1:8000"

                with (
                    patch.object(launcher_app, "config", fake_config),
                    patch.object(launcher_app, "open_in_browser", return_value=True) as open_mock,
                ):
                    launcher._open_browser_now()

                open_mock.assert_called_once_with("http://127.0.0.1:8000", prefer_pwa=prefer_pwa)


def pwa_config(**overrides) -> SimpleNamespace:
    values = {
        "pwa_appx_family_name": None,
        "pwa_app_id": None,
        "get_server_url": Mock(return_value="http://127.0.0.1:8000"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class OpenAsPwaRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        browser._discovered_appx = None
        browser._discovery_checked_at = None

    def tearDown(self) -> None:
        browser._discovered_appx = None
        browser._discovery_checked_at = None

    def test_configured_appx_wins(self):
        config = pwa_config(pwa_appx_family_name=VALID_FAMILY_NAME)
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "is_appx_installed", return_value=True),
            patch.object(browser, "open_as_appx", return_value=True) as open_appx,
            patch.object(browser, "discover_luker_appx") as discover,
            patch.object(browser, "find_edge_path") as find_edge,
        ):
            self.assertTrue(browser.open_as_pwa("http://127.0.0.1:8000"))

        open_appx.assert_called_once_with(VALID_FAMILY_NAME)
        discover.assert_not_called()
        find_edge.assert_not_called()

    def test_invalid_configured_appx_is_skipped(self):
        config = pwa_config(pwa_appx_family_name="x'; calc; #")
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "is_appx_installed") as installed,
            patch.object(browser, "open_as_appx") as open_appx,
            patch.object(browser, "discover_luker_appx", return_value=None),
            patch.object(browser, "find_edge_path", return_value="C:/Edge/msedge.exe"),
            patch.object(browser.subprocess, "Popen") as popen,
        ):
            self.assertTrue(browser.open_as_pwa("http://127.0.0.1:8000"))

        installed.assert_not_called()
        open_appx.assert_not_called()
        self.assertIn("--app=http://127.0.0.1:8000", popen.call_args.args[0])

    def test_configured_appx_not_installed_falls_through_to_discovery(self):
        config = pwa_config(pwa_appx_family_name=VALID_FAMILY_NAME)
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "is_appx_installed", return_value=False),
            patch.object(browser, "open_as_appx", return_value=True) as open_appx,
            patch.object(
                browser,
                "discover_luker_appx",
                return_value=(VALID_FAMILY_NAME, "LukerApp"),
            ),
            patch.object(browser, "find_edge_path") as find_edge,
        ):
            self.assertTrue(browser.open_as_pwa("http://127.0.0.1:8000"))

        open_appx.assert_called_once_with(VALID_FAMILY_NAME, "LukerApp")
        find_edge.assert_not_called()

    def test_configured_appx_open_failure_falls_through_to_discovery(self):
        config = pwa_config(pwa_appx_family_name=VALID_FAMILY_NAME)
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "is_appx_installed", return_value=True),
            patch.object(browser, "open_as_appx", side_effect=[False, True]) as open_appx,
            patch.object(
                browser,
                "discover_luker_appx",
                return_value=(VALID_FAMILY_NAME, "LukerApp"),
            ),
            patch.object(browser, "find_edge_path") as find_edge,
        ):
            self.assertTrue(browser.open_as_pwa("http://127.0.0.1:8000"))

        self.assertEqual(open_appx.call_count, 2)
        self.assertEqual(open_appx.call_args_list[1].args, (VALID_FAMILY_NAME, "LukerApp"))
        find_edge.assert_not_called()

    def test_edge_app_id_is_used_when_pwa_is_installed(self):
        config = pwa_config(pwa_app_id="test-app-id")
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "discover_luker_appx", return_value=None),
            patch.object(browser, "find_edge_path", return_value="C:/Edge/msedge.exe"),
            patch.object(browser, "is_pwa_installed", return_value=True),
            patch.object(browser.subprocess, "Popen") as popen,
        ):
            self.assertTrue(browser.open_as_pwa("http://127.0.0.1:8000"))

        self.assertEqual(
            popen.call_args.args[0],
            ["C:/Edge/msedge.exe", "--app-id=test-app-id", "--profile-directory=Default"],
        )

    def test_edge_app_url_is_used_when_pwa_is_not_installed(self):
        config = pwa_config(pwa_app_id="test-app-id")
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "discover_luker_appx", return_value=None),
            patch.object(browser, "find_edge_path", return_value="C:/Edge/msedge.exe"),
            patch.object(browser, "is_pwa_installed", return_value=False),
            patch.object(browser.subprocess, "Popen") as popen,
        ):
            self.assertTrue(browser.open_as_pwa("http://127.0.0.1:8000"))

        self.assertEqual(
            popen.call_args.args[0],
            ["C:/Edge/msedge.exe", "--app=http://127.0.0.1:8000", "--profile-directory=Default"],
        )

    def test_no_edge_returns_false_without_starting_process(self):
        config = pwa_config()
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "discover_luker_appx", return_value=None),
            patch.object(browser, "find_edge_path", return_value=None),
            patch.object(browser.subprocess, "Popen") as popen,
        ):
            self.assertFalse(browser.open_as_pwa("http://127.0.0.1:8000"))

        popen.assert_not_called()

    def test_popen_failure_returns_false(self):
        config = pwa_config()
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "discover_luker_appx", return_value=None),
            patch.object(browser, "find_edge_path", return_value="C:/Edge/msedge.exe"),
            patch.object(browser.subprocess, "Popen", side_effect=OSError("boom")),
        ):
            self.assertFalse(browser.open_as_pwa("http://127.0.0.1:8000"))

    def test_edge_process_is_detached_with_devnull_streams(self):
        config = pwa_config()
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "discover_luker_appx", return_value=None),
            patch.object(browser, "find_edge_path", return_value="C:/Edge/msedge.exe"),
            patch.object(browser.subprocess, "Popen") as popen,
        ):
            self.assertTrue(browser.open_as_pwa("http://127.0.0.1:8000"))

        kwargs = popen.call_args.kwargs
        self.assertEqual(
            kwargs["creationflags"],
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)

    def test_default_url_comes_from_config(self):
        config = pwa_config()
        config.get_server_url.return_value = "http://127.0.0.1:8123"
        with (
            patch.object(browser, "config", config),
            patch.object(browser, "discover_luker_appx", return_value=None),
            patch.object(browser, "find_edge_path", return_value="C:/Edge/msedge.exe"),
            patch.object(browser.subprocess, "Popen") as popen,
        ):
            self.assertTrue(browser.open_as_pwa())

        self.assertIn("--app=http://127.0.0.1:8123", popen.call_args.args[0])


class OpenAsAppxTests(unittest.TestCase):
    def test_success_uses_apps_folder_uri(self):
        with patch.object(
            browser.ctypes.windll.shell32, "ShellExecuteW", return_value=33
        ) as execute:
            self.assertTrue(browser.open_as_appx(VALID_FAMILY_NAME, "LukerApp"))

        self.assertEqual(
            execute.call_args.args[2],
            f"shell:AppsFolder\\{VALID_FAMILY_NAME}!LukerApp",
        )

    def test_shell_rejection_returns_false(self):
        with patch.object(browser.ctypes.windll.shell32, "ShellExecuteW", return_value=0):
            self.assertFalse(browser.open_as_appx(VALID_FAMILY_NAME))

    def test_shell_exception_returns_false(self):
        with patch.object(
            browser.ctypes.windll.shell32,
            "ShellExecuteW",
            side_effect=OSError("boom"),
        ):
            self.assertFalse(browser.open_as_appx(VALID_FAMILY_NAME))


class FindEdgePathTests(unittest.TestCase):
    def test_uses_second_candidate_when_first_is_missing(self):
        with patch.object(browser.os.path, "exists", side_effect=[False, True, False]) as exists:
            path = browser.find_edge_path()

        self.assertEqual(path, r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
        self.assertEqual(exists.call_count, 2)

    def test_returns_none_when_all_candidates_are_missing(self):
        with patch.object(browser.os.path, "exists", return_value=False):
            self.assertIsNone(browser.find_edge_path())


class PwaInstalledTests(unittest.TestCase):
    def test_finds_default_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Default" / "Web Applications" / "LukerApp").mkdir(parents=True)
            with patch.object(browser.os.path, "expandvars", return_value=temp):
                self.assertTrue(browser.is_pwa_installed("LukerApp"))

    def test_finds_numbered_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Profile 1" / "Web Applications" / "LukerApp").mkdir(parents=True)
            with patch.object(browser.os.path, "expandvars", return_value=temp):
                self.assertTrue(browser.is_pwa_installed("LukerApp"))

    def test_missing_app_returns_false(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(browser.os.path, "expandvars", return_value=temp),
        ):
            self.assertFalse(browser.is_pwa_installed("LukerApp"))


class OpenInBrowserFallbackTests(unittest.TestCase):
    def test_successful_pwa_does_not_open_default_browser(self):
        with (
            patch.object(browser, "open_as_pwa", return_value=True),
            patch("webbrowser.open") as open_browser,
        ):
            self.assertTrue(browser.open_in_browser("http://127.0.0.1:8000"))

        open_browser.assert_not_called()

    def test_pwa_failure_falls_back_to_default_browser(self):
        with (
            patch.object(browser, "open_as_pwa", return_value=False),
            patch("webbrowser.open", return_value=True) as open_browser,
        ):
            self.assertTrue(browser.open_in_browser("http://127.0.0.1:8000"))

        open_browser.assert_called_once_with("http://127.0.0.1:8000")

    def test_prefer_pwa_false_skips_pwa(self):
        with (
            patch.object(browser, "open_as_pwa") as open_pwa,
            patch("webbrowser.open", return_value=True),
        ):
            self.assertTrue(browser.open_in_browser("http://127.0.0.1:8000", prefer_pwa=False))

        open_pwa.assert_not_called()

    def test_default_browser_exception_returns_false(self):
        with (
            patch.object(browser, "open_as_pwa", return_value=False),
            patch("webbrowser.open", side_effect=OSError("boom")),
        ):
            self.assertFalse(browser.open_in_browser("http://127.0.0.1:8000"))


if __name__ == "__main__":
    unittest.main()
