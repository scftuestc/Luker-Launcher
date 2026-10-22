import re
import unittest
from unittest.mock import patch

import window_resize
from dpi import MonitorInfo
from window_resize import WindowResizer


class FakeEvent:
    def __init__(
        self,
        widget: object,
        x: int = 0,
        y: int = 0,
        x_root: int = 0,
        y_root: int = 0,
    ) -> None:
        self.widget = widget
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root


class FakeWindow:
    """只实现 WindowResizer 用到的窗口接口。"""

    def __init__(self, width: int = 960, height: int = 640, x: int = 0, y: int = 0) -> None:
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        self.viewable = True
        self.exists = True
        self.binds: dict[str, object] = {}
        self.bind_add: dict[str, str | None] = {}
        self.geometry_specs: list[str] = []
        self.minsize_args: tuple[int, int] | None = None
        self.maxsize_args: tuple[int, int] | None = None
        self.cursor = ''
        self.idle_calls = 0
        self.defer_idle = False
        self.idle_callbacks: list[object] = []

    def bind(self, sequence: str, callback: object, add: str | None = None) -> None:
        self.binds[sequence] = callback
        self.bind_add[sequence] = add

    def geometry(self, spec: str) -> None:
        match = re.fullmatch(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', spec)
        assert match is not None, spec
        self.geometry_specs.append(spec)
        self.width = int(match.group(1))
        self.height = int(match.group(2))
        self.x = int(match.group(3))
        self.y = int(match.group(4))

    def minsize(self, width: int, height: int) -> None:
        self.minsize_args = (width, height)

    def maxsize(self, width: int, height: int) -> None:
        self.maxsize_args = (width, height)

    def configure(self, *, cursor: str) -> None:
        self.cursor = cursor

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def winfo_x(self) -> int:
        return self.x

    def winfo_y(self) -> int:
        return self.y

    def winfo_id(self) -> int:
        return 1

    def winfo_exists(self) -> bool:
        return self.exists

    def winfo_viewable(self) -> bool:
        return self.viewable

    def after_idle(self, callback: object) -> None:
        self.idle_calls += 1
        self.idle_callbacks.append(callback)
        if not self.defer_idle:
            callback()


class WindowResizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = MonitorInfo(0, 0, 1920, 1040, 96)
        monitor_patch = patch.object(window_resize, 'get_monitor_info', return_value=self.monitor)
        self.monitor_mock = monitor_patch.start()
        self.addCleanup(monitor_patch.stop)
        scale_patch = patch.object(
            window_resize,
            'sync_window_scaling',
            side_effect=lambda _window, scale: scale,
        )
        scale_patch.start()
        self.addCleanup(scale_patch.stop)
        window_scale_patch = patch.object(window_resize, '_get_window_scale', return_value=1.0)
        window_scale_patch.start()
        self.addCleanup(window_scale_patch.stop)

    def make_resizer(
        self,
        monitor: MonitorInfo | None = None,
    ) -> tuple[FakeWindow, WindowResizer]:
        if monitor is not None:
            self.monitor_mock.return_value = monitor
        window = FakeWindow()
        resizer = WindowResizer(window)
        resizer.apply_initial_geometry()
        return window, resizer

    def test_initial_geometry_is_centered(self):
        window, _ = self.make_resizer()

        self.assertEqual(window.geometry_specs[-1], '960x640+480+200')
        self.assertEqual(window.minsize_args, (700, 450))
        self.assertEqual(window.maxsize_args, (10000, 10000))

    def test_initial_geometry_supports_negative_monitor(self):
        window, _ = self.make_resizer(MonitorInfo(-1920, 0, 0, 1080, 96))

        self.assertEqual(window.geometry_specs[-1], '960x640+-1440+220')
        self.assertEqual((window.x, window.y), (-1440, 220))

    def test_initial_geometry_shrinks_on_small_high_dpi_screen(self):
        window, _ = self.make_resizer(MonitorInfo(0, 0, 1366, 728, 144))

        self.assertEqual(window.geometry_specs[-1], '878x453+24+24')
        self.assertEqual(window.minsize_args, (700, 450))

    def test_same_monitor_does_not_touch_geometry(self):
        window, resizer = self.make_resizer()
        before = len(window.geometry_specs)

        resizer.fit_to_current_monitor()

        self.assertEqual(len(window.geometry_specs), before)

    def test_monitor_change_refits_and_clamps_position(self):
        window, resizer = self.make_resizer()
        window.x, window.y = 0, 0
        self.monitor_mock.return_value = MonitorInfo(0, 0, 1366, 728, 144)

        resizer.fit_to_current_monitor()

        self.assertEqual(window.geometry_specs[-1], '878x453+8+8')
        self.assertEqual(window.minsize_args, (700, 450))
        self.assertEqual(window.maxsize_args, (10000, 10000))

    def test_hidden_window_skips_monitor_fit(self):
        window, resizer = self.make_resizer()
        window.viewable = False
        before = len(window.geometry_specs)
        self.monitor_mock.return_value = MonitorInfo(0, 0, 1366, 728, 144)

        resizer.fit_to_current_monitor()

        self.assertEqual(len(window.geometry_specs), before)

    def test_missing_window_skips_monitor_fit(self):
        window, resizer = self.make_resizer()
        window.exists = False
        before = len(window.geometry_specs)
        self.monitor_mock.return_value = MonitorInfo(0, 0, 1366, 728, 144)

        resizer.fit_to_current_monitor()

        self.assertEqual(len(window.geometry_specs), before)

    def test_edge_detection_sets_cursor(self):
        window, resizer = self.make_resizer()
        resizer.bind_events()
        motion = window.binds['<Motion>']

        cases = [
            ((0, 0), 'size_nw_se'),
            ((959, 0), 'size_ne_sw'),
            ((0, 639), 'size_ne_sw'),
            ((959, 639), 'size_nw_se'),
            ((480, 0), 'size_ns'),
            ((480, 639), 'size_ns'),
            ((0, 320), 'size_we'),
            ((959, 320), 'size_we'),
            ((480, 320), ''),
        ]
        for (x, y), cursor in cases:
            with self.subTest(x=x, y=y):
                motion(FakeEvent(window, x=x, y=y))
                self.assertEqual(window.cursor, cursor)

    def test_child_widget_clears_resize_edge(self):
        window, resizer = self.make_resizer()
        resizer.bind_events()
        motion = window.binds['<Motion>']

        motion(FakeEvent(window, x=0, y=0))
        motion(FakeEvent(object(), x=0, y=0))

        self.assertEqual(window.cursor, '')

    def test_east_drag_respects_minimum_width(self):
        window, resizer = self.make_resizer()
        resizer.bind_events()

        window.binds['<Motion>'](FakeEvent(window, x=959, y=320))
        window.binds['<Button-1>'](FakeEvent(window, x_root=959, y_root=320))
        window.binds['<B1-Motion>'](FakeEvent(window, x_root=0, y_root=320))

        self.assertEqual(window.geometry_specs[-1], '700x640+480+200')

    def test_west_drag_moves_origin(self):
        window, resizer = self.make_resizer()
        resizer.bind_events()

        window.binds['<Motion>'](FakeEvent(window, x=0, y=320))
        window.binds['<Button-1>'](FakeEvent(window, x_root=480, y_root=320))
        window.binds['<B1-Motion>'](FakeEvent(window, x_root=530, y_root=320))

        self.assertEqual(window.geometry_specs[-1], '910x640+530+200')

    def test_drag_without_edge_is_ignored(self):
        window, resizer = self.make_resizer()
        resizer.bind_events()
        before = len(window.geometry_specs)

        window.binds['<Motion>'](FakeEvent(window, x=480, y=320))
        window.binds['<Button-1>'](FakeEvent(window, x_root=480, y_root=320))
        window.binds['<B1-Motion>'](FakeEvent(window, x_root=0, y_root=320))

        self.assertEqual(len(window.geometry_specs), before)

    def test_configure_binding_preserves_existing_handlers(self):
        window, resizer = self.make_resizer()

        resizer.bind_events()

        self.assertEqual(window.bind_add['<Configure>'], '+')
        self.assertIsNone(window.bind_add['<Motion>'])

    def test_configure_coalesces_idle_fits(self):
        window, resizer = self.make_resizer()
        resizer.bind_events()
        configure = window.binds['<Configure>']
        window.defer_idle = True

        configure(FakeEvent(window))
        configure(FakeEvent(window))

        self.assertEqual(window.idle_calls, 1)
        self.assertEqual(len(window.idle_callbacks), 1)

        window.idle_callbacks.pop(0)()
        configure(FakeEvent(window))
        self.assertEqual(window.idle_calls, 2)

    def test_configure_only_reacts_to_root_window(self):
        window, resizer = self.make_resizer()
        resizer.bind_events()
        configure = window.binds['<Configure>']
        before = window.idle_calls

        configure(FakeEvent(object()))
        self.assertEqual(window.idle_calls, before)

        configure(FakeEvent(window))
        self.assertEqual(window.idle_calls, before + 1)


if __name__ == '__main__':
    unittest.main()
