import ast
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_build_bat_uses_spec_and_project_root(self):
        text = (ROOT / "build.bat").read_text(encoding="utf-8")

        self.assertIn("pyinstaller launcher.spec", text)
        self.assertIn("--noconfirm", text)
        self.assertIn("--distpath .", text)

    def test_build_bat_stops_on_pyinstaller_failure(self):
        text = (ROOT / "build.bat").read_text(encoding="utf-8")

        self.assertIn("if errorlevel 1", text)
        self.assertIn(":fail", text)
        self.assertIn("exit /b 1", text)
        self.assertIn("exit /b 0", text)

    def test_launcher_spec_references_required_assets(self):
        spec_path = ROOT / "launcher.spec"
        text = spec_path.read_text(encoding="utf-8")

        ast.parse(text)
        self.assertIn("'main.py'", text)
        self.assertIn("name='Luker-Launcher'", text)
        self.assertIn("console=False", text)
        self.assertIn("icon='icon.ico'", text)
        self.assertIn("version='version_info.txt'", text)
        for name in ("main.py", "icon.ico", "version_info.txt"):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_check_bat_keeps_all_quality_gates(self):
        text = (ROOT / "check.bat").read_text(encoding="utf-8")

        for command in (
            "ruff format --check",
            "ruff check",
            "mypy .",
            "coverage run -m unittest discover",
            "coverage report",
        ):
            self.assertIn(command, text)
        self.assertIn(":fail", text)
        self.assertIn("exit /b 1", text)


@unittest.skipUnless(os.name == "nt", "build.bat 只在 Windows 上执行")
class BuildScriptBehaviorTests(unittest.TestCase):
    def _run_build(
        self, pyinstaller_exit_code: int
    ) -> tuple[subprocess.CompletedProcess[str], bool]:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            (work / "build.bat").write_bytes((ROOT / "build.bat").read_bytes())
            (work / "pyinstaller.bat").write_text(
                f"@echo off\r\nexit /b {pyinstaller_exit_code}\r\n",
                encoding="ascii",
            )
            (work / "build").mkdir()
            env = os.environ.copy()
            env["PATH"] = str(work) + os.pathsep + env.get("PATH", "")
            completed = subprocess.run(
                [os.environ.get("COMSPEC", "cmd.exe"), "/c", "build.bat"],
                cwd=work,
                env=env,
                input="\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
            return completed, (work / "build").exists()

    def test_failure_is_reported_and_does_not_clean_build_dir(self):
        result, build_dir_remains = self._run_build(1)

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Done!", result.stdout)
        self.assertIn("Build failed", result.stdout)
        self.assertTrue(build_dir_remains)

    def test_success_reports_done_and_cleans_build_dir(self):
        result, build_dir_remains = self._run_build(0)

        self.assertEqual(result.returncode, 0)
        self.assertIn("Done!", result.stdout)
        self.assertFalse(build_dir_remains)


if __name__ == "__main__":
    unittest.main()
