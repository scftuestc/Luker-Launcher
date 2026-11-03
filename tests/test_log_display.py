import datetime
import unittest

from log.display import LogDisplay, configure_log_tags, get_tag_for_line, measure_log_indent


class FakeTextbox:
    def __init__(self) -> None:
        self.tags: dict[str, dict[str, object]] = {}

    def tag_configure(self, tag: str, **options: object) -> None:
        self.tags[tag] = options


class FakeInsertText:
    def __init__(self) -> None:
        self.parts: list[tuple[str, tuple[tuple[str, ...], ...]]] = []

    def index(self, _index: str) -> str:
        return "1.0"

    def insert(self, _index: str, text: str, *tags: tuple[str, ...]) -> None:
        self.parts.append((text, tags))


class FakeLabel:
    def configure(self, **_options: object) -> None:
        pass


class ConfigureLogTagsTests(unittest.TestCase):
    def test_maps_every_tag_to_unified_colors(self):
        textbox = FakeTextbox()
        colors = {
            'text': '#888888',
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
                'info': '#888888',
                'success': '#888888',
                'error': '#444444',
                'warn': '#888888',
                'accent': '#888888',
                'dim': '#888888',
                'separator': '#111111',
            },
        )
        self.assertFalse(textbox.tags['separator']['elide'])

    def test_body_tag_uses_timestamp_width_as_hanging_indent(self):
        textbox = FakeTextbox()
        colors = {
            'text': '#888888',
            'text_muted': '#111111',
            'info': '#222222',
            'success': '#333333',
            'error': '#444444',
            'warning': '#555555',
            'accent': '#666666',
            'text_dim': '#777777',
        }

        configure_log_tags(textbox, colors, body_indent=73)

        self.assertEqual(textbox.tags['body'], {'lmargin1': 0, 'lmargin2': 73})

    def test_measure_indent_returns_zero_for_non_tk_widget(self):
        self.assertEqual(measure_log_indent(object()), 0)


class InsertEntryTests(unittest.TestCase):
    def test_timestamp_and_body_share_the_hanging_indent_tag(self):
        textbox = FakeInsertText()
        display = LogDisplay(lambda: textbox, FakeLabel())

        display._insert_entry(
            textbox,
            "[信息] hello",
            datetime.datetime(2026, 1, 2, 3, 4, 5),
        )

        self.assertEqual(
            textbox.parts,
            [
                ("[03:04:05] ", (("time", "body"),)),
                ("[信息] hello\n", (("info", "body"),)),
            ],
        )


class LogTagTests(unittest.TestCase):
    def test_launcher_tag(self):
        self.assertEqual(
            get_tag_for_line("[启动器] 已最小化到系统托盘"),
            "accent",
        )


if __name__ == "__main__":
    unittest.main()
