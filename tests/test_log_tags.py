import unittest

from log_tags import get_tag_for_line


class LogTagTests(unittest.TestCase):
    def test_gcl_error_tag(self):
        self.assertEqual(
            get_tag_for_line("[GCL 错误] 启动失败"),
            "error",
        )

    def test_gcl_warning_tag(self):
        self.assertEqual(
            get_tag_for_line("[GCL 警告] 端口被占用"),
            "warn",
        )

    def test_gcl_info_tag(self):
        self.assertEqual(
            get_tag_for_line("[GCL 信息] 已启动"),
            "info",
        )

    def test_launcher_tag(self):
        self.assertEqual(
            get_tag_for_line("[启动器] 已最小化到系统托盘"),
            "accent",
        )


if __name__ == "__main__":
    unittest.main()
