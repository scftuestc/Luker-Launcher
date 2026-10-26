import unittest

from ui.dpi import MonitorInfo
from ui.tooltip import Tooltip, tooltip_position

MONITOR = MonitorInfo(0, 0, 1920, 1080, 96)
COLORS = {
    'card_hover': '#bcc2c8',
    'border': '#878e96',
    'text': '#171b1f',
}


class TooltipPositionTests(unittest.TestCase):
    def test_places_below_and_centers(self):
        self.assertEqual(
            tooltip_position((100, 100, 18, 18), (200, 50), MONITOR),
            (9, 124),
        )

    def test_clamps_to_right_edge(self):
        self.assertEqual(
            tooltip_position((1900, 100, 18, 18), (200, 50), MONITOR),
            (1712, 124),
        )

    def test_flips_above_when_bottom_is_crowded(self):
        self.assertEqual(
            tooltip_position((100, 1050, 18, 18), (200, 50), MONITOR)[1],
            994,
        )

    def test_stays_inside_small_work_area(self):
        monitor = MonitorInfo(0, 0, 120, 80, 96)
        x, y = tooltip_position((0, 0, 18, 18), (200, 50), monitor)

        self.assertGreaterEqual(x, 8)
        self.assertGreaterEqual(y, 8)


class FakeWidget:
    def __init__(self) -> None:
        self.bindings: list[tuple[str, str | None]] = []

    def bind(self, sequence: str, _callback: object, add: str | None = None) -> None:
        self.bindings.append((sequence, add))


class TooltipAttachTests(unittest.TestCase):
    @staticmethod
    def _tooltip() -> Tooltip:
        return Tooltip(object(), COLORS, 'Segoe UI')

    def test_attach_binds_hover_and_cleanup_events(self):
        widget = FakeWidget()

        self._tooltip().attach(widget, 'hint')

        self.assertEqual(
            widget.bindings,
            [
                ('<Enter>', '+'),
                ('<Leave>', '+'),
                ('<Button-1>', '+'),
                ('<Configure>', '+'),
                ('<Destroy>', '+'),
            ],
        )

    def test_hide_ignores_other_widget(self):
        tooltip = self._tooltip()
        anchor = object()
        tooltip._anchor = anchor

        tooltip.hide(object())

        self.assertIs(tooltip._anchor, anchor)

    def test_hide_and_destroy_before_window_exists(self):
        tooltip = self._tooltip()

        tooltip.hide()
        tooltip.destroy()

        self.assertIsNone(tooltip._window)


if __name__ == '__main__':
    unittest.main()
