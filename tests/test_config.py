import json
import tempfile
import unittest
from pathlib import Path

from config import DEFAULT_PORT, Config
from theme import DEFAULT_THEME, PRESET_THEMES


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "launcher_config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, data) -> None:
        self.config_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_missing_file_uses_defaults(self):
        config = Config(self.config_path)
        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertFalse(config.use_pwa_mode)
        self.assertFalse(config.gcl_enabled)
        self.assertIsNone(config.luker_path)

    def test_invalid_json_uses_defaults(self):
        self.config_path.write_text("{not json", encoding="utf-8")
        config = Config(self.config_path)
        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertIsNone(config.luker_path)

    def test_normalize_drops_wrong_types(self):
        self._write(
            {
                "use_pwa_mode": "false",
                "gcl_enabled": 1,
                "theme": "unknown",
                "luker_path": 123,
                "gcl_url": "  ",
                "unknown_key": True,
            }
        )
        config = Config(self.config_path)
        self.assertFalse(config.use_pwa_mode)
        self.assertFalse(config.gcl_enabled)
        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertIsNone(config.luker_path)

    def test_legacy_path_key_is_supported(self):
        self._write({"sillytavern_path": "D:/Old/Luker"})
        config = Config(self.config_path)
        self.assertEqual(config.luker_path, "D:/Old/Luker")

        config.luker_path = "D:/New/Luker"
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["luker_path"], "D:/New/Luker")
        self.assertNotIn("sillytavern_path", saved)

    def test_save_is_atomic_and_roundtrips(self):
        config = Config(self.config_path)
        config.theme_name = "ocean_cyan"
        config.use_pwa_mode = True

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["theme"], "ocean_cyan")
        self.assertTrue(saved["use_pwa_mode"])
        self.assertFalse(self.config_path.with_name(self.config_path.name + ".tmp").exists())

        reloaded = Config(self.config_path)
        self.assertEqual(reloaded.theme_name, "ocean_cyan")
        self.assertTrue(reloaded.use_pwa_mode)

    def test_theme_colors_are_copies(self):
        config = Config(self.config_path)
        colors = config.get_theme_colors()
        colors["bg"] = "#000000"
        self.assertNotEqual(PRESET_THEMES[DEFAULT_THEME]["bg"], "#000000")

    def test_server_port_reads_only_top_level(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        (luker_dir / "Start.bat").write_text("", encoding="utf-8")
        (luker_dir / "server.js").write_text("", encoding="utf-8")
        (luker_dir / "config.yaml").write_text(
            "port: 8123\nbrowserLaunch:\n  port: 9999\n",
            encoding="utf-8",
        )

        config = Config(self.config_path)
        config.luker_path = str(luker_dir)
        self.assertEqual(config.get_server_port(), 8123)

    def test_invalid_port_falls_back_to_default(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        (luker_dir / "Start.bat").write_text("", encoding="utf-8")
        (luker_dir / "server.js").write_text("", encoding="utf-8")
        (luker_dir / "config.yaml").write_text("port: 70000\n", encoding="utf-8")

        config = Config(self.config_path)
        config.luker_path = str(luker_dir)
        self.assertEqual(config.get_server_port(), DEFAULT_PORT)


if __name__ == "__main__":
    unittest.main()
