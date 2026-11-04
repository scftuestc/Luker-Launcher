import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import DEFAULT_CLOSE_BEHAVIOR, DEFAULT_PORT, Config
from ui.theme import DEFAULT_THEME, LEGACY_THEME_ALIASES, PRESET_THEMES


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "launcher_config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, data) -> None:
        self.config_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _make_luker_dir(self, port_text: str) -> Path:
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir(exist_ok=True)
        (luker_dir / "config.yaml").write_text(port_text, encoding="utf-8")
        return luker_dir

    def test_missing_file_uses_defaults(self):
        config = Config(self.config_path)
        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertFalse(config.use_pwa_mode)
        self.assertTrue(config.blur_enabled)
        self.assertEqual(config.close_behavior, DEFAULT_CLOSE_BEHAVIOR)
        self.assertIsNone(config.luker_path)
        self.assertIsNone(config.load_error)

    def test_invalid_json_uses_defaults(self):
        self.config_path.write_text("{not json", encoding="utf-8")
        config = Config(self.config_path)
        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertIsNone(config.luker_path)
        self.assertIsNotNone(config.load_error)

    def test_invalid_json_does_not_log_before_logging_is_configured(self):
        self.config_path.write_text("{not json", encoding="utf-8")

        with self.assertNoLogs("config", level="WARNING"):
            Config(self.config_path)

    def test_invalid_utf8_config_uses_defaults(self):
        self.config_path.write_bytes(b'{"theme": "\xff"}')

        config = Config(self.config_path)

        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertIsNone(config.luker_path)
        self.assertIsNotNone(config.load_error)

    def test_utf8_bom_config_is_read_normally(self):
        self.config_path.write_bytes(
            b'\xef\xbb\xbf' + json.dumps({"theme": "ocean_cyan"}).encode("utf-8")
        )

        config = Config(self.config_path)

        self.assertEqual(config.theme_name, "ocean_cyan")
        self.assertIsNone(config.load_error)

    def test_non_object_json_uses_defaults(self):
        self.config_path.write_text("[]", encoding="utf-8")

        config = Config(self.config_path)

        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertIsNone(config.luker_path)
        self.assertIsNotNone(config.load_error)

    def test_report_load_error_emits_warning_only_once(self):
        self.config_path.write_text("{not json", encoding="utf-8")
        config = Config(self.config_path)

        with self.assertLogs("config", level="WARNING") as logs:
            self.assertTrue(config.report_load_error())

        self.assertIn("读取配置失败", logs.output[0])
        self.assertIsNone(config.load_error)
        self.assertFalse(config.report_load_error())

    def test_normalize_drops_wrong_types(self):
        self._write(
            {
                "use_pwa_mode": "false",
                "blur_enabled": "false",
                "close_behavior": "unknown",
                "theme": "unknown",
                "luker_path": 123,
                "unknown_key": True,
            }
        )
        config = Config(self.config_path)
        self.assertFalse(config.use_pwa_mode)
        self.assertTrue(config.blur_enabled)
        self.assertEqual(config.close_behavior, DEFAULT_CLOSE_BEHAVIOR)
        self.assertEqual(config.theme_name, DEFAULT_THEME)
        self.assertIsNone(config.luker_path)

    def test_legacy_theme_ids_are_migrated(self):
        for legacy, current in LEGACY_THEME_ALIASES.items():
            with self.subTest(legacy=legacy):
                self._write({"theme": legacy})
                config = Config(self.config_path)
                self.assertEqual(config.theme_name, current)
                colors = config.get_theme_colors()
                for key, value in colors.items():
                    self.assertEqual(value, PRESET_THEMES[current][key])
                self.assertNotIn("name", colors)

    def test_legacy_theme_id_is_migrated_by_setter(self):
        config = Config(self.config_path)
        config.theme_name = "deep_blue"

        self.assertEqual(config.theme_name, "summer")
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["theme"], "summer")

    def test_legacy_path_key_is_supported(self):
        self._write({"sillytavern_path": "D:/Old/Luker"})
        config = Config(self.config_path)
        self.assertEqual(config.luker_path, "D:/Old/Luker")

        config.luker_path = "D:/New/Luker"
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["luker_path"], "D:/New/Luker")
        self.assertNotIn("sillytavern_path", saved)

    def test_legacy_gcl_keys_are_ignored_and_removed_on_save(self):
        self._write(
            {
                "luker_path": "D:/Luker",
                "gcl_enabled": True,
                "gcl_bat_path": "D:/Old/start.bat",
                "gcl_url": "http://127.0.0.1:7861/",
                "blur_enabled": True,
            }
        )
        config = Config(self.config_path)
        self.assertEqual(config.luker_path, "D:/Luker")
        self.assertTrue(config.blur_enabled)

        config.blur_enabled = False

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertFalse(any(key.startswith("gcl_") for key in saved))
        self.assertEqual(saved["luker_path"], "D:/Luker")
        self.assertFalse(saved["blur_enabled"])

    def test_blur_callback_can_be_removed(self):
        config = Config(self.config_path)
        calls = []

        def callback(enabled):
            calls.append(enabled)

        config.add_blur_change_callback(callback)
        config.blur_enabled = False
        self.assertEqual(calls, [False])

        config.remove_blur_change_callback(callback)
        config.blur_enabled = True
        self.assertEqual(calls, [False])

    def test_close_behavior_roundtrips(self):
        config = Config(self.config_path)
        config.close_behavior = "tray"

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["close_behavior"], "tray")

        reloaded = Config(self.config_path)
        self.assertEqual(reloaded.close_behavior, "tray")

    def test_invalid_close_behavior_is_ignored(self):
        config = Config(self.config_path)
        config.close_behavior = "tray"
        config.close_behavior = "invalid"

        self.assertEqual(config.close_behavior, "tray")
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["close_behavior"], "tray")

    def test_close_behavior_callback_can_be_removed(self):
        config = Config(self.config_path)
        calls = []

        def callback(value):
            calls.append(value)

        config.add_close_behavior_change_callback(callback)
        config.close_behavior = "exit"
        self.assertEqual(calls, ["exit"])

        config.remove_close_behavior_change_callback(callback)
        config.close_behavior = "ask"
        self.assertEqual(calls, ["exit"])

    def test_blur_enabled_roundtrips(self):
        config = Config(self.config_path)
        config.blur_enabled = False

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertFalse(saved["blur_enabled"])
        self.assertFalse(self.config_path.with_name(self.config_path.name + ".tmp").exists())

        reloaded = Config(self.config_path)
        self.assertFalse(reloaded.blur_enabled)

    def test_mist_gray_disables_blur_but_keeps_saved_preference(self):
        self._write({"theme": "mist_gray", "blur_enabled": True})
        config = Config(self.config_path)

        self.assertFalse(config.blur_available)
        self.assertFalse(config.blur_enabled)

        config.theme_name = "summer"

        self.assertTrue(config.blur_available)
        self.assertTrue(config.blur_enabled)

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

    def test_valid_luker_path_accepts_regular_files(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        (luker_dir / "Start.bat").write_text("", encoding="utf-8")
        (luker_dir / "server.js").write_text("", encoding="utf-8")

        config = Config(self.config_path)
        self.assertTrue(config.is_valid_luker_path(str(luker_dir)))

    def test_luker_path_rejects_directories_named_like_files(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        (luker_dir / "Start.bat").mkdir()
        (luker_dir / "server.js").mkdir()

        config = Config(self.config_path)
        self.assertFalse(config.is_valid_luker_path(str(luker_dir)))

    def test_luker_path_requires_both_files(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        (luker_dir / "Start.bat").write_text("", encoding="utf-8")

        config = Config(self.config_path)
        self.assertFalse(config.is_valid_luker_path(str(luker_dir)))

    def test_invalid_utf8_luker_config_yaml_falls_back(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        (luker_dir / "config.yaml").write_bytes(b"port: 8123\n\xff")
        config = Config(self.config_path)
        config.luker_path = str(luker_dir)

        self.assertEqual(config.get_server_port(), DEFAULT_PORT)

    def test_luker_config_yaml_with_bom_is_read(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        (luker_dir / "config.yaml").write_bytes(b"\xef\xbb\xbfport: 8125\n")
        config = Config(self.config_path)
        config.luker_path = str(luker_dir)

        self.assertEqual(config.get_server_port(), 8125)

    def test_oversized_port_number_falls_back_without_raising(self):
        luker_dir = self._make_luker_dir("port: " + "9" * 5000 + "\n")
        config = Config(self.config_path)
        config.luker_path = str(luker_dir)

        self.assertEqual(config.get_server_port(), DEFAULT_PORT)

    def test_server_port_is_cached_until_file_changes(self):
        luker_dir = self._make_luker_dir("port: 8123\n")
        config_yaml = luker_dir / "config.yaml"
        config = Config(self.config_path)
        config.luker_path = str(luker_dir)
        original = Path.read_text
        reads: list[Path] = []

        def counting_read(path_obj, *args, **kwargs):
            reads.append(path_obj)
            return original(path_obj, *args, **kwargs)

        with patch.object(Path, "read_text", new=counting_read):
            self.assertEqual(config.get_server_port(), 8123)
            self.assertEqual(config.get_server_port(), 8123)

        self.assertEqual(reads, [config_yaml])

        config_yaml.write_text("port: 8124\n", encoding="utf-8")
        stat = config_yaml.stat()
        os.utime(config_yaml, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

        with patch.object(Path, "read_text", new=counting_read):
            self.assertEqual(config.get_server_port(), 8124)

        self.assertEqual(len(reads), 2)

    def test_missing_luker_config_yaml_warns_once(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        config = Config(self.config_path)
        config.luker_path = str(luker_dir)

        with self.assertLogs("config", level="WARNING") as logs:
            self.assertEqual(config.get_server_port(), DEFAULT_PORT)
            self.assertEqual(config.get_server_port(), DEFAULT_PORT)

        self.assertEqual(len(logs.output), 1)

    def test_port_recovers_after_luker_config_appears(self):
        luker_dir = Path(self.temp_dir.name) / "Luker"
        luker_dir.mkdir()
        config = Config(self.config_path)
        config.luker_path = str(luker_dir)

        with self.assertLogs("config", level="WARNING"):
            self.assertEqual(config.get_server_port(), DEFAULT_PORT)

        (luker_dir / "config.yaml").write_text("port: 8123\n", encoding="utf-8")

        self.assertEqual(config.get_server_port(), 8123)

    def test_null_byte_luker_path_falls_back(self):
        self._write({"luker_path": "C:/bad\u0000x"})
        config = Config(self.config_path)

        self.assertEqual(config.get_server_port(), DEFAULT_PORT)

    def test_save_with_unencodable_value_cleans_temp_file(self):
        config = Config(self.config_path)
        temp_path = self.config_path.with_name(self.config_path.name + ".tmp")

        config.pwa_app_id = "\ud800"

        self.assertFalse(temp_path.exists())

    def test_save_failure_keeps_value_in_memory_and_logs_error(self):
        config = Config(self.config_path)
        blocked = Path(self.temp_dir.name) / "blocked.json"
        blocked.mkdir()
        config.config_path = blocked

        with self.assertLogs("config", level="ERROR") as logs:
            config.theme_name = "ocean_cyan"

        self.assertEqual(config.theme_name, "ocean_cyan")
        self.assertIn("保存配置失败", logs.output[0])

    def test_unknown_keys_are_dropped_when_saving(self):
        self._write({"luker_path": "D:/Luker", "future_key": {"nested": True}})
        config = Config(self.config_path)

        config.use_pwa_mode = True

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertNotIn("future_key", saved)
        self.assertEqual(saved["luker_path"], "D:/Luker")


if __name__ == "__main__":
    unittest.main()
