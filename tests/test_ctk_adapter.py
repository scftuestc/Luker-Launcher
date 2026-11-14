import tkinter as tk
import unittest
from unittest.mock import patch

from luker_launcher.ui import ctk_adapter


class FakeScalingTracker:
    def __init__(self) -> None:
        self.window_dpi_scaling_dict: dict[object, float] = {}
        self.updated: list[object] = []

    @classmethod
    def get_window_dpi_scaling(cls, _window):
        return 1.25

    def update_scaling_callbacks_for_window(self, window) -> None:
        self.updated.append(window)


class CtkAdapterTests(unittest.TestCase):
    def test_get_textbox_returns_inner_text_widget(self):
        class Widget:
            _textbox = object()

        self.assertIs(ctk_adapter.get_textbox(Widget()), Widget._textbox)

    def test_get_widget_scaling_returns_scale(self):
        class Widget:
            def _get_widget_scaling(self):
                return 1.5

        self.assertEqual(ctk_adapter.get_widget_scaling(Widget()), 1.5)

    def test_get_widget_scaling_falls_back_without_private_method(self):
        self.assertEqual(ctk_adapter.get_widget_scaling(object()), 1.0)

    def test_get_widget_scaling_falls_back_on_tcl_error(self):
        class Widget:
            def _get_widget_scaling(self):
                raise tk.TclError("bad")

        self.assertEqual(ctk_adapter.get_widget_scaling(Widget()), 1.0)

    def test_get_widget_scaling_falls_back_on_non_positive(self):
        class Widget:
            def _get_widget_scaling(self):
                return 0

        self.assertEqual(ctk_adapter.get_widget_scaling(Widget()), 1.0)

    def test_get_window_dpi_scaling_uses_tracker(self):
        with patch.object(ctk_adapter.ctk, "ScalingTracker", FakeScalingTracker()):
            self.assertEqual(ctk_adapter.get_window_dpi_scaling(object()), 1.25)

    def test_window_scaling_cache_updates_once(self):
        tracker = FakeScalingTracker()
        window = object()
        with patch.object(ctk_adapter.ctk, "ScalingTracker", tracker):
            self.assertTrue(ctk_adapter.set_window_scaling_cache(window, 1.5))
            self.assertFalse(ctk_adapter.set_window_scaling_cache(window, 1.5))

        self.assertEqual(tracker.window_dpi_scaling_dict[window], 1.5)
        self.assertEqual(tracker.updated, [window])

    def test_window_scaling_cache_discard(self):
        tracker = FakeScalingTracker()
        window = object()
        tracker.window_dpi_scaling_dict[window] = 1.5
        with patch.object(ctk_adapter.ctk, "ScalingTracker", tracker):
            ctk_adapter.discard_window_scaling_cache(window)

        self.assertNotIn(window, tracker.window_dpi_scaling_dict)


if __name__ == "__main__":
    unittest.main()
