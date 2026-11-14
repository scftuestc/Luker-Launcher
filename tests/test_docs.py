import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DocsStructureTests(unittest.TestCase):
    def test_docs_structure(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "docs" / "tools" / "check_docs.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
