import json
import subprocess
import tempfile
import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
