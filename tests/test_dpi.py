import unittest

import customtkinter as ctk

from dpi import (
    MonitorInfo,
    centered_position,
    clamp_popup_position,
    clamp_window_position,
    discard_window_scaling,
    fit_logical_window_size,
    format_geometry,
)


class MonitorInfoTests(unittest.TestCase):
    def test_scale_from_dpi(self):
        self.assertEqual(MonitorInfo(0, 0, 1920, 1080, 96).scale, 1.0)
        self.assertEqual(MonitorInfo(0, 0, 1920, 1080, 120).scale, 1.25)
        self.assertEqual(MonitorInfo(0, 0, 1920, 1080, 144).scale, 1.5)


class WindowSizeTests(unittest.TestCase):
    def test_settings_fit_at_100_percent(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 96)
        self.assertEqual(
            fit_logical_window_size(600, 720, monitor, 1.0, margin=16),
            (600, 720),
        )

    def test_settings_fit_at_125_percent(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 120)
        self.assertEqual(
            fit_logical_window_size(600, 720, monitor, 1.25, margin=16),
            (600, 720),
        )

    def test_settings_height_fits_at_150_percent_1080p(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 144)
        logical_width, logical_height = fit_logical_window_size(600, 720, monitor, 1.5, margin=16)
        self.assertEqual((logical_width, logical_height), (600, 672))
        self.assertLessEqual(round(logical_height * 1.5), monitor.height - 32)

    def test_log_window_fits_at_150_percent(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 144)
        self.assertEqual(
            fit_logical_window_size(960, 640, monitor, 1.5, margin=24),
            (960, 640),
        )

    def test_small_screen_shrinks_window(self):
        monitor = MonitorInfo(0, 0, 1366, 728, 144)
        logical_width, logical_height = fit_logical_window_size(960, 640, monitor, 1.5, margin=24)
        self.assertEqual((logical_width, logical_height), (878, 453))


class CenterPositionTests(unittest.TestCase):
    def test_centers_physical_window_in_work_area(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 144)
        self.assertEqual(centered_position(900, 1008, monitor), (510, 16))

    def test_centers_on_negative_secondary_monitor(self):
        monitor = MonitorInfo(-1920, 0, 0, 1080, 144)
        self.assertEqual(centered_position(900, 1008, monitor), (-1410, 36))


class PopupPositionTests(unittest.TestCase):
    def test_flips_left_and_up_near_edges(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 144)
        self.assertEqual(
            clamp_popup_position(1900, 1000, 330, 400, monitor),
            (1560, 590),
        )

    def test_clamps_into_negative_secondary_monitor(self):
        monitor = MonitorInfo(-1920, 0, 0, 1080, 120)
        self.assertEqual(
            clamp_popup_position(-100, 500, 330, 400, monitor),
            (-440, 500),
        )

    def test_clamps_top_left_with_margin(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 96)
        self.assertEqual(
            clamp_popup_position(-500, -50, 220, 300, monitor),
            (10, 10),
        )


class FormatGeometryTests(unittest.TestCase):
    def test_positive_position(self):
        self.assertEqual(format_geometry(220, 300, 100, 200), "220x300+100+200")

    def test_negative_position(self):
        self.assertEqual(format_geometry(220, 300, -100, 200), "220x300+-100+200")

    def test_position_only(self):
        self.assertEqual(format_geometry(None, None, -100, 50), "+-100+50")


class WindowPositionTests(unittest.TestCase):
    def test_clamps_window_into_work_area(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 144)
        self.assertEqual(
            clamp_window_position(1900, 1000, 900, 1008, monitor, margin=8),
            (1012, 24),
        )

    def test_keeps_window_inside_negative_monitor(self):
        monitor = MonitorInfo(-1920, 0, 0, 1080, 120)
        self.assertEqual(
            clamp_window_position(-2100, -20, 750, 900, monitor, margin=8),
            (-1912, 8),
        )


class ScalingCacheTests(unittest.TestCase):
    def test_discard_window_scaling_removes_entry(self):
        key = object()
        ctk.ScalingTracker.window_dpi_scaling_dict[key] = 1.0
        try:
            discard_window_scaling(key)
            self.assertNotIn(key, ctk.ScalingTracker.window_dpi_scaling_dict)
        finally:
            ctk.ScalingTracker.window_dpi_scaling_dict.pop(key, None)


if __name__ == "__main__":
    unittest.main()
