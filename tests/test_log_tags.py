import unittest

from log_tags import configure_log_tags, get_tag_for_line


class FakeTextbox:
    def __init__(self) -> None:
        self.tags: dict[str, dict[str, object]] = {}

    def tag_configure(self, tag: str, **options: object) -> None:
        self.tags[tag] = options


class ConfigureLogTagsTests(unittest.TestCase):
    def test_maps_every_tag_to_theme_colors(self):
        textbox = FakeTextbox()
        colors = {
            'text_muted': '#111111',
            'info': '#222222',
            'success': '#333333',
            'error': '#444444',
            'warning': '#555555',
            'accent': '#666666',
            'text_dim': '#777777',
        }

        configure_log_tags(textbox, colors)

        self.assertEqual(
            {tag: options['foreground'] for tag, options in textbox.tags.items()},
            {
                'time': '#111111',
                'info': '#222222',
                'success': '#333333',
                'error': '#444444',
                'warn': '#555555',
                'accent': '#666666',
                'dim': '#777777',
                'separator': '#666666',
            },
        )
        self.assertFalse(textbox.tags['separator']['elide'])


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
