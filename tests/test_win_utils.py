import unittest
from unittest.mock import patch

import win_utils
from win_utils import bind_window_drag, hex_to_colorref, sync_window_blur


class HexToColorrefTests(unittest.TestCase):
    def test_converts_rgb_with_default_alpha(self):
        self.assertEqual(hex_to_colorref("#112233"), 0xDD332211)

    def test_custom_alpha_is_preserved(self):
        self.assertEqual(hex_to_colorref("#112233", alpha=0xEE), 0xEE332211)

    def test_invalid_length_keeps_alpha(self):
        self.assertEqual(hex_to_colorref("#12345", alpha=0xEE), 0xEE000000)

    def test_invalid_hex_keeps_alpha(self):
        self.assertEqual(hex_to_colorref("#GGGGGG", alpha=0xEE), 0xEE000000)


class FakeWindow:
    def winfo_id(self) -> int:
        return 1


class BlurTests(unittest.TestCase):
    def test_enable_blur_propagates_api_failure(self):
        with (
            patch.object(win_utils, "windll") as windll_mock,
            self.assertRaises(OSError),
        ):
            windll_mock.dwmapi.DwmSetWindowAttribute.side_effect = OSError("boom")
            win_utils.WindowsBlur.enable_blur(1)

    def test_apply_blur_propagates_extend_failure(self):
        with (
            patch.object(win_utils.WindowsBlur, "extend_frame", side_effect=OSError("boom")),
            self.assertRaises(OSError),
        ):
            win_utils.apply_blur(1, "#000000")

    def test_apply_window_blur_reports_context(self):
        with (
            patch.object(win_utils, "windll") as windll_mock,
            patch.object(win_utils, "apply_blur", side_effect=OSError("boom")),
            self.assertLogs("win_utils", level="WARNING") as logs,
        ):
            windll_mock.user32.GetParent.return_value = 1
            win_utils.apply_window_blur(FakeWindow(), "#000000", context="测试窗口")

        self.assertIn("测试窗口毛玻璃失败", logs.output[0])

    def test_apply_window_blur_passes_arguments(self):
        with (
            patch.object(win_utils, "windll") as windll_mock,
            patch.object(win_utils, "apply_blur") as apply_mock,
        ):
            windll_mock.user32.GetParent.return_value = 42
            win_utils.apply_window_blur(FakeWindow(), "#112233", alpha=0xEE, context="测试")

        apply_mock.assert_called_once_with(42, "#112233", alpha=0xEE, accent_state=4)

    def test_disable_blur_clears_accent_and_layered_style(self):
        with patch.object(win_utils, "windll") as windll_mock:
            windll_mock.user32.GetWindowLongW.return_value = 0x80008
            win_utils.WindowsBlur.disable_blur(1)

        windll_mock.user32.SetWindowCompositionAttribute.assert_called_once()
        windll_mock.dwmapi.DwmExtendFrameIntoClientArea.assert_called_once()
        windll_mock.user32.SetWindowLongW.assert_called_once()
        windll_mock.user32.SetWindowPos.assert_called_once()
        windll_mock.dwmapi.DwmFlush.assert_called_once()

    def test_disable_window_blur_reports_context(self):
        with (
            patch.object(win_utils, "windll") as windll_mock,
            patch.object(
                win_utils.WindowsBlur,
                "disable_blur",
                side_effect=OSError("boom"),
            ),
            self.assertLogs("win_utils", level="WARNING") as logs,
        ):
            windll_mock.user32.GetParent.return_value = 1
            win_utils.disable_window_blur(FakeWindow(), context="测试窗口")

        self.assertIn("测试窗口关闭毛玻璃失败", logs.output[0])


class FakeAlphaWindow:
    def __init__(self) -> None:
        self.alphas: list[float] = []

    def attributes(self, name: str, value: float | None = None) -> None:
        if name == '-alpha':
            assert value is not None
            self.alphas.append(value)


class SyncWindowBlurTests(unittest.TestCase):
    def test_enabled_dark_background_uses_acrylic(self):
        window = FakeAlphaWindow()
        with (
            patch.object(win_utils, 'apply_window_blur') as apply_mock,
            patch.object(win_utils, 'disable_window_blur') as disable_mock,
        ):
            sync_window_blur(
                window,
                "#112233",
                enabled=True,
                window_alpha=0.97,
                tint_alpha=0xEE,
                context="测试窗口",
            )

        self.assertEqual(window.alphas, [1.0, 0.97])
        apply_mock.assert_called_once_with(
            window,
            "#112233",
            alpha=0xEE,
            accent_state=4,
            context="测试窗口",
        )
        disable_mock.assert_not_called()

    def test_enabled_light_background_uses_blur_behind(self):
        window = FakeAlphaWindow()
        with patch.object(win_utils, 'apply_window_blur') as apply_mock:
            sync_window_blur(
                window,
                "#f0ede8",
                enabled=True,
                window_alpha=0.97,
                context="测试窗口",
            )

        apply_mock.assert_called_once_with(
            window,
            "#f0ede8",
            alpha=0xDD,
            accent_state=3,
            context="测试窗口",
        )

    def test_disabled_sets_opaque_alpha_and_disables_blur(self):
        window = FakeAlphaWindow()
        with (
            patch.object(win_utils, 'apply_window_blur') as apply_mock,
            patch.object(win_utils, 'disable_window_blur') as disable_mock,
        ):
            sync_window_blur(
                window,
                "#112233",
                enabled=False,
                window_alpha=0.97,
                context="测试窗口",
            )

        self.assertEqual(window.alphas, [1.0])
        apply_mock.assert_not_called()
        disable_mock.assert_called_once_with(window, context="测试窗口")


class FakeWidget:
    def __init__(self, x: int, y: int) -> None:
        self._x = x
        self._y = y
        self.bindings: dict[str, object] = {}
        self.geometry_value: str | None = None

    def bind(self, sequence: str, callback: object) -> None:
        self.bindings[sequence] = callback

    def winfo_x(self) -> int:
        return self._x

    def winfo_y(self) -> int:
        return self._y

    def geometry(self, value: str) -> None:
        self.geometry_value = value


class FakeEvent:
    def __init__(self, x_root: int, y_root: int) -> None:
        self.x_root = x_root
        self.y_root = y_root


class WindowDragTests(unittest.TestCase):
    def test_binds_both_events_on_every_widget(self):
        window = FakeWidget(0, 0)
        first = FakeWidget(0, 0)
        second = FakeWidget(0, 0)

        bind_window_drag(window, first, second)

        for widget in (first, second):
            self.assertIn("<Button-1>", widget.bindings)
            self.assertIn("<B1-Motion>", widget.bindings)

    def test_drag_uses_press_offset(self):
        window = FakeWidget(100, 200)
        handle = FakeWidget(0, 0)
        bind_window_drag(window, handle)

        handle.bindings["<Button-1>"](FakeEvent(120, 220))
        handle.bindings["<B1-Motion>"](FakeEvent(150, 260))

        self.assertEqual(window.geometry_value, "+130+240")


if __name__ == "__main__":
    unittest.main()
