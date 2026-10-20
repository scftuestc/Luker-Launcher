import subprocess
import unittest
from unittest.mock import Mock, patch

import pwa_browser

VALID_FAMILY_NAME = "127.0.0.1-test_8wekyb3d8bbwe"


class PwaTimeoutTests(unittest.TestCase):
    def test_is_appx_installed_timeout_returns_false(self):
        timeout = subprocess.TimeoutExpired("powershell", 10)
        with patch.object(pwa_browser.subprocess, "run", side_effect=timeout):
            self.assertFalse(pwa_browser.is_appx_installed(VALID_FAMILY_NAME))

    def test_discover_luker_appx_timeout_returns_none(self):
        timeout = subprocess.TimeoutExpired("powershell", 10)
        pwa_browser._discovered_appx = None
        pwa_browser._discovery_checked_at = 0.0
        try:
            with (
                patch.object(pwa_browser.time, "monotonic", return_value=1000.0),
                patch.object(pwa_browser.subprocess, "run", side_effect=timeout),
            ):
                self.assertIsNone(pwa_browser.discover_luker_appx())
        finally:
            pwa_browser._discovered_appx = None
            pwa_browser._discovery_checked_at = 0.0


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


if __name__ == "__main__":
    unittest.main()
