import re
import unittest
from pathlib import Path

from config import APP_VERSION

VERSION_INFO_PATH = Path(__file__).resolve().parents[1] / "version_info.txt"


class VersionConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = VERSION_INFO_PATH.read_text(encoding="utf-8")
        cls.file_version = cls._parse_tuple("filevers")
        cls.product_version = cls._parse_tuple("prodvers")
        cls.string_versions = dict(re.findall(r"StringStruct\('([^']+)',\s*'([^']*)'\)", cls.text))

    @classmethod
    def _parse_tuple(cls, key: str) -> tuple[int, ...]:
        match = re.search(rf"{key}=\(([^)]*)\)", cls.text)
        if match is None:
            raise AssertionError(f"version_info.txt 缺少 {key}")
        return tuple(int(part.strip()) for part in match.group(1).split(","))

    @staticmethod
    def _padded(version: str) -> tuple[int, ...]:
        parts = [int(part) for part in version.split(".")]
        return tuple(parts + [0] * (4 - len(parts)))

    def test_file_and_product_versions_match(self):
        self.assertEqual(self.file_version, self.product_version)

    def test_string_versions_match_numeric_versions(self):
        expected = ".".join(str(part) for part in self.file_version)
        self.assertEqual(self.string_versions["FileVersion"], expected)
        self.assertEqual(self.string_versions["ProductVersion"], expected)

    def test_app_version_matches_version_info(self):
        self.assertEqual(self._padded(APP_VERSION), self.file_version)


if __name__ == "__main__":
    unittest.main()
