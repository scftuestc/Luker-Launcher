import unittest

from core.readiness import LukerState
from log_window import empty_log_text, error_banner_colors, truncate_log_text
from ui.theme import PRESET_THEMES, mix_color


class EmptyLogTextTests(unittest.TestCase):
    def test_stopped_luker_has_start_hint(self):
        title, detail = empty_log_text(LukerState.STOPPED, 'luker', False)
        self.assertEqual(title, "还没有日志")
        self.assertIn("开始", detail)

    def test_starting_and_ready_have_distinct_titles(self):
        self.assertEqual(
            empty_log_text(LukerState.STARTING, 'luker', False)[0],
            "正在启动 Luker…",
        )
        self.assertEqual(
            empty_log_text(LukerState.READY, 'luker', False)[0],
            "暂无日志输出",
        )

    def test_gcl_source_mentions_enable_state(self):
        self.assertEqual(empty_log_text(LukerState.STOPPED, 'gcl', False)[0], "GCL 未启用")
        self.assertEqual(empty_log_text(LukerState.STOPPED, 'gcl', True)[0], "暂无 GCL 日志")


class TruncateLogTextTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(truncate_log_text(" a \n  b\tc "), "a b c")

    def test_short_text_is_unchanged(self):
        self.assertEqual(truncate_log_text("short"), "short")

    def test_long_text_is_cut_with_ellipsis(self):
        text = "x" * 100
        result = truncate_log_text(text, limit=20)
        self.assertEqual(len(result), 20)
        self.assertTrue(result.endswith("…"))


class ErrorBannerColorTests(unittest.TestCase):
    def test_mixes_card_and_error(self):
        colors = PRESET_THEMES['summer']
        banner = error_banner_colors(colors)
        self.assertEqual(
            banner['fg_color'],
            mix_color(colors['card'], colors['error'], 0.10),
        )
        self.assertEqual(
            banner['border_color'],
            mix_color(colors['border'], colors['error'], 0.45),
        )


if __name__ == '__main__':
    unittest.main()
