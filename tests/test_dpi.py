import unittest

import customtkinter as ctk

from ui.dpi import (
    MonitorInfo,
    centered_position,
    clamp_popup_position,
    clamp_window_position,
    discard_window_scaling,
    fit_logical_window_size,
    fit_window_with_minimum,
    format_geometry,
    plan_window_placement,
)


class MonitorInfoTests(unittest.TestCase):
    def test_scale_from_dpi(self):
        self.assertEqual(MonitorInfo(0, 0, 1920, 1080, 96).scale, 1.0)
        self.assertEqual(MonitorInfo(0, 0, 1920, 1080, 120).scale, 1.25)
        self.assertEqual(MonitorInfo(0, 0, 1920, 1080, 144).scale, 1.5)

    def test_signature_changes_with_work_area_or_dpi(self):
        self.assertEqual(
            MonitorInfo(0, 0, 1920, 1080, 96).signature(),
            (0, 0, 1920, 1080, 96),
        )
        self.assertNotEqual(
            MonitorInfo(0, 0, 1920, 1080, 96).signature(),
            MonitorInfo(0, 0, 1920, 1040, 96).signature(),
        )
        self.assertNotEqual(
            MonitorInfo(0, 0, 1920, 1080, 96).signature(),
            MonitorInfo(0, 0, 1920, 1080, 120).signature(),
        )


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


class WindowMinimumTests(unittest.TestCase):
    def test_minimum_and_window_fit_large_monitor(self):
        monitor = MonitorInfo(0, 0, 1920, 1040, 96)
        self.assertEqual(
            fit_window_with_minimum(960, 640, 700, 450, monitor, 1.0, margin=24),
            (700, 450, 960, 640),
        )

    def test_minimum_shrinks_with_window_on_small_monitor(self):
        monitor = MonitorInfo(0, 0, 1280, 672, 144)
        min_width, min_height, width, height = fit_window_with_minimum(
            960, 640, 700, 450, monitor, 1.5, margin=24
        )

        self.assertEqual((min_width, min_height, width, height), (700, 416, 821, 416))
        self.assertLessEqual(min_width, width)
        self.assertLessEqual(min_height, height)
        self.assertLessEqual(round(height * 1.5) + 48, monitor.height)

    def test_minimum_restores_after_returning_to_large_monitor(self):
        small = MonitorInfo(0, 0, 1280, 672, 144)
        _, _, width, height = fit_window_with_minimum(960, 640, 700, 450, small, 1.5, margin=24)
        large = MonitorInfo(0, 0, 1920, 1040, 96)
        min_width, min_height, new_width, new_height = fit_window_with_minimum(
            width, height, 700, 450, large, 1.0, margin=24
        )

        self.assertEqual((min_width, min_height), (700, 450))
        self.assertEqual((new_width, new_height), (821, 450))

    def test_extreme_scale_keeps_minimum_inside_work_area(self):
        monitor = MonitorInfo(0, 0, 800, 600, 192)
        min_width, min_height, width, height = fit_window_with_minimum(
            960, 640, 700, 450, monitor, 2.0, margin=24
        )

        self.assertEqual((min_width, min_height, width, height), (376, 276, 376, 276))


class WindowPlacementTests(unittest.TestCase):
    def test_settings_window_is_centered(self):
        placement = plan_window_placement(
            600,
            720,
            MonitorInfo(0, 0, 1920, 1040, 96),
            1.0,
            margin=16,
        )

        self.assertEqual((placement.logical_width, placement.logical_height), (600, 720))
        self.assertIsNone(placement.minimum_width)
        self.assertIsNone(placement.minimum_height)
        self.assertEqual(placement.geometry, "600x720+660+160")

    def test_settings_window_is_clamped_on_small_monitor(self):
        placement = plan_window_placement(
            600,
            720,
            MonitorInfo(0, 0, 1366, 728, 144),
            1.5,
            margin=16,
            anchor="clamp",
            current_position=(1800, 900),
        )

        self.assertEqual((placement.logical_width, placement.logical_height), (600, 464))
        self.assertEqual(placement.geometry, "600x464+458+24")

    def test_log_window_keeps_minimum_size(self):
        placement = plan_window_placement(
            960,
            640,
            MonitorInfo(0, 0, 1280, 672, 144),
            1.5,
            margin=24,
            minimum=(700, 450),
            anchor="clamp",
            current_position=(0, 0),
        )

        self.assertEqual((placement.minimum_width, placement.minimum_height), (700, 416))
        self.assertEqual((placement.logical_width, placement.logical_height), (821, 416))
        self.assertEqual(placement.geometry, "821x416+8+8")

    def test_clamp_requires_current_position(self):
        with self.assertRaises(ValueError):
            plan_window_placement(
                600,
                720,
                MonitorInfo(0, 0, 1920, 1040, 96),
                1.0,
                anchor="clamp",
            )


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
