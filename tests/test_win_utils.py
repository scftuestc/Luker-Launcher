import unittest

from win_utils import bind_window_drag, hex_to_colorref


class HexToColorrefTests(unittest.TestCase):
    def test_converts_rgb_with_default_alpha(self):
        self.assertEqual(hex_to_colorref("#112233"), 0xDD332211)

    def test_custom_alpha_is_preserved(self):
        self.assertEqual(hex_to_colorref("#112233", alpha=0xEE), 0xEE332211)

    def test_invalid_length_keeps_alpha(self):
        self.assertEqual(hex_to_colorref("#12345", alpha=0xEE), 0xEE000000)

    def test_invalid_hex_keeps_alpha(self):
        self.assertEqual(hex_to_colorref("#GGGGGG", alpha=0xEE), 0xEE000000)


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
