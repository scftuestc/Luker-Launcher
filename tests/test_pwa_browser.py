import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import main
import pwa_browser
from main import LukerLauncher

VALID_FAMILY_NAME = "127.0.0.1-test_8wekyb3d8bbwe"


class PwaTimeoutTests(unittest.TestCase):
    def test_is_appx_installed_timeout_returns_false(self):
        timeout = subprocess.TimeoutExpired("powershell", 10)
        with patch.object(pwa_browser.subprocess, "run", side_effect=timeout):
            self.assertFalse(pwa_browser.is_appx_installed(VALID_FAMILY_NAME))

    def test_discover_luker_appx_timeout_returns_none(self):
        timeout = subprocess.TimeoutExpired("powershell", 10)
        pwa_browser._discovered_appx = None
        pwa_browser._discovery_checked_at = None
        try:
            with (
                patch.object(pwa_browser.time, "monotonic", return_value=1000.0),
                patch.object(pwa_browser.subprocess, "run", side_effect=timeout) as run,
            ):
                self.assertIsNone(pwa_browser.discover_luker_appx())
            run.assert_called_once()
        finally:
            pwa_browser._discovered_appx = None
            pwa_browser._discovery_checked_at = None


class AppxFamilyNameTests(unittest.TestCase):
    def test_accepts_valid_family_name(self):
        self.assertTrue(pwa_browser.is_valid_appx_family_name(VALID_FAMILY_NAME))

    def test_rejects_quotes_and_wildcards(self):
        self.assertFalse(pwa_browser.is_valid_appx_family_name("x'; calc; #_8wekyb3d8bbwe"))
        self.assertFalse(pwa_browser.is_valid_appx_family_name("127.0.0.1-*_8wekyb3d8bbwe"))

    def test_is_appx_installed_skips_powershell_for_invalid_name(self):
        with patch.object(pwa_browser.subprocess, "run") as run:
            self.assertFalse(pwa_browser.is_appx_installed("x'; calc; #"))
        run.assert_not_called()

    def test_is_appx_installed_queries_valid_name(self):
        completed = Mock()
        completed.stdout = "PackageFullName\n"
        with patch.object(pwa_browser.subprocess, "run", return_value=completed) as run:
            self.assertTrue(pwa_browser.is_appx_installed(VALID_FAMILY_NAME))

        command = run.call_args.args[0]
        self.assertEqual(command[0], "powershell")
        self.assertIn("'127.0.0.1-test'", command[-1])


class PwaDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        pwa_browser._discovered_appx = None
        pwa_browser._discovery_checked_at = None

    def tearDown(self) -> None:
        pwa_browser._discovered_appx = None
        pwa_browser._discovery_checked_at = None

    def test_first_call_runs_shortly_after_boot(self):
        completed = Mock()
        completed.stdout = ""
        with (
            patch.object(pwa_browser.time, "monotonic", return_value=5.0),
            patch.object(pwa_browser.subprocess, "run", return_value=completed) as run,
        ):
            self.assertIsNone(pwa_browser.discover_luker_appx())

        run.assert_called_once()

    def test_failed_discovery_backs_off(self):
        completed = Mock()
        completed.stdout = ""
        with (
            patch.object(
                pwa_browser.time,
                "monotonic",
                side_effect=[1000.0, 1030.0, 1061.0],
            ),
            patch.object(pwa_browser.subprocess, "run", return_value=completed) as run,
        ):
            self.assertIsNone(pwa_browser.discover_luker_appx())
            self.assertIsNone(pwa_browser.discover_luker_appx())
            self.assertIsNone(pwa_browser.discover_luker_appx())

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

            with patch.object(pwa_browser.subprocess, "run", return_value=completed) as run:
                first = pwa_browser.discover_luker_appx()
                second = pwa_browser.discover_luker_appx()

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
            patch.object(main.urllib.request, "urlopen", return_value=FakeResponse()),
            patch.object(main, "Thread", FakeThread),
        ):
            launcher._schedule_auto_open_browser()

        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0].__self__, launcher)
        self.assertIs(posted[0].__func__, LukerLauncher._on_open_browser)


if __name__ == "__main__":
    unittest.main()
