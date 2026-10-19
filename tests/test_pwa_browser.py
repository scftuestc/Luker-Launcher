import subprocess
import unittest
from unittest.mock import patch

import pwa_browser


class PwaTimeoutTests(unittest.TestCase):
    def test_is_appx_installed_timeout_returns_false(self):
        timeout = subprocess.TimeoutExpired("powershell", 10)
        with patch.object(pwa_browser.subprocess, "run", side_effect=timeout):
            self.assertFalse(pwa_browser.is_appx_installed("package_family"))

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


if __name__ == "__main__":
    unittest.main()
