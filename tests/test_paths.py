import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from luker_launcher import paths


class SourcePathTests(unittest.TestCase):
    def test_source_paths_point_to_repository_root(self):
        root = Path(__file__).resolve().parents[1]

        self.assertEqual(paths.get_app_dir(), root)
        self.assertEqual(paths.get_bundle_dir(), root)
        self.assertTrue(paths.resource_path("icon.ico").is_file())


class FrozenPathTests(unittest.TestCase):
    def test_frozen_paths_use_executable_dir_and_meipass(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "app" / "Luker-Launcher.exe"
            bundle = root / "bundle"

            with (
                patch.object(paths.sys, "frozen", True, create=True),
                patch.object(paths.sys, "executable", str(executable)),
                patch.object(paths.sys, "_MEIPASS", str(bundle), create=True),
            ):
                self.assertEqual(paths.get_app_dir(), executable.parent)
                self.assertEqual(paths.get_bundle_dir(), bundle)
                self.assertEqual(paths.resource_path("icon.ico"), bundle / "icon.ico")


if __name__ == "__main__":
    unittest.main()
