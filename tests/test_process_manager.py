import socket
import tempfile
import unittest
from pathlib import Path

from process_manager import GCLProcessManager, LukerProcessManager


class ProcessManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.luker_dir = Path(self.temp_dir.name)
        (self.luker_dir / "server.js").write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_luker_command_allows_browser_launch(self):
        manager = LukerProcessManager(str(self.luker_dir), let_luker_open_browser=True)
        self.assertEqual(manager._build_command(), ["node", "server.js"])

    def test_luker_command_disables_browser_launch(self):
        manager = LukerProcessManager(str(self.luker_dir), let_luker_open_browser=False)
        self.assertEqual(
            manager._build_command(),
            ["node", "server.js", "--browserLaunchEnabled", "false"],
        )

    def test_luker_requires_server_js(self):
        missing = Path(self.temp_dir.name) / "missing"
        manager = LukerProcessManager(str(missing))
        self.assertIn("server.js", manager._startup_error())

    def test_occupied_port_blocks_start(self):
        logs = []
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(5)
            port = listener.getsockname()[1]

            manager = LukerProcessManager(str(self.luker_dir), server_port=port)
            manager.add_log_callback(logs.append)
            self.assertFalse(manager.start())

        self.assertTrue(any("端口" in line for line in logs))
        self.assertFalse(manager.is_running)

    def test_gcl_command_and_working_directory(self):
        bat_path = self.luker_dir / "start.bat"
        bat_path.write_text("", encoding="utf-8")

        manager = GCLProcessManager(str(bat_path))
        self.assertEqual(manager._build_command(), ["cmd", "/c", str(bat_path)])
        self.assertEqual(manager._startup_cwd(), str(self.luker_dir))
        self.assertEqual(manager._encoding, "mbcs")


if __name__ == "__main__":
    unittest.main()
