import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

from luker_launcher.theme import PRESET_THEMES, get_theme_colors
from ui.ctk_adapter import CtkSwitchAdapter
from ui.switch import (
    SWITCH_ANIMATION_STEPS,
    AnimatedSwitch,
    switch_thumb_color,
    switch_thumb_hover_color,
    switch_track_colors,
)


class CtkSwitchAdapterTests(unittest.TestCase):
    def make_switch(self, **overrides) -> tuple[SimpleNamespace, Mock, Mock]:
        canvas = Mock()
        draw_engine = Mock()
        values = {
            '_canvas': canvas,
            '_draw_engine': draw_engine,
            '_switch_width': 44,
            '_switch_height': 22,
            '_corner_radius': 10,
            '_border_width': 2,
            '_button_length': 20,
            '_apply_widget_scaling': lambda value: value * 2,
        }
        values.update(overrides)
        return SimpleNamespace(**values), canvas, draw_engine

    def test_supported_when_private_interface_exists(self):
        switch, _, _ = self.make_switch()

        self.assertTrue(CtkSwitchAdapter(switch).supported)

    def test_missing_private_attribute_disables_adapter(self):
        switch, canvas, draw_engine = self.make_switch(_canvas=None)
        adapter = CtkSwitchAdapter(switch)

        self.assertFalse(adapter.supported)
        adapter.draw_slider(0.5, '#ffffff')
        adapter.set_track_colors('#111111', '#222222')

        canvas.itemconfig.assert_not_called()
        draw_engine.draw_rounded_slider_with_border_and_button.assert_not_called()

    def test_draw_slider_delegates_scaled_geometry(self):
        switch, canvas, draw_engine = self.make_switch()

        CtkSwitchAdapter(switch).draw_slider(0.5, '#abcdef')

        canvas.itemconfig.assert_called_once_with(
            'slider_parts',
            fill='#abcdef',
            outline='#abcdef',
        )
        draw_engine.draw_rounded_slider_with_border_and_button.assert_called_once_with(
            88,
            44,
            20,
            4,
            40,
            20,
            0.5,
            'w',
        )

    def test_track_colors_update_inner_and_progress(self):
        switch, canvas, _ = self.make_switch()

        CtkSwitchAdapter(switch).set_track_colors('#111111', '#222222')

        self.assertEqual(
            canvas.itemconfig.call_args_list,
            [
                call('inner_parts', fill='#111111', outline='#111111'),
                call('progress_parts', fill='#222222', outline='#222222'),
            ],
        )


class SwitchColorTests(unittest.TestCase):
    def test_track_uses_border_and_accent_without_hover(self):
        colors = get_theme_colors('summer')

        self.assertEqual(switch_track_colors(colors, False), (colors['border'], colors['accent']))

    def test_track_changes_on_hover(self):
        for name in PRESET_THEMES:
            with self.subTest(theme=name):
                colors = get_theme_colors(name)
                off, on = switch_track_colors(colors, False)
                hover_off, hover_on = switch_track_colors(colors, True)

                self.assertNotEqual(hover_off, off)
                self.assertNotEqual(hover_on, on)

    def test_thumb_moves_between_text_and_on_accent(self):
        for name in PRESET_THEMES:
            with self.subTest(theme=name):
                colors = get_theme_colors(name)

                self.assertEqual(switch_thumb_color(colors, 0.0), colors['text'])
                self.assertEqual(switch_thumb_color(colors, 1.0), colors['on_accent'])
                self.assertNotEqual(
                    switch_thumb_hover_color(colors, 0.5),
                    switch_thumb_color(colors, 0.5),
                )


class SwitchAnimationTests(unittest.TestCase):
    def make_switch(self, value: float, target: float) -> AnimatedSwitch:
        switch = object.__new__(AnimatedSwitch)
        switch._slider_value = value
        switch._animation_target = target
        switch._animation_job = None
        switch._destroyed = False
        switch._adapter = SimpleNamespace(supported=True)
        switch.redraws = []
        switch.jobs = []
        switch._redraw_slider = lambda: switch.redraws.append(switch._slider_value)
        switch.after = lambda delay, callback: switch.jobs.append((delay, callback)) or 'job'
        return switch

    def test_tick_reaches_target_and_stops(self):
        switch = self.make_switch(0.0, 1.0)

        for _ in range(SWITCH_ANIMATION_STEPS):
            switch._tick_animation()

        self.assertEqual(switch._slider_value, 1.0)
        self.assertEqual(switch.redraws[-1], 1.0)
        self.assertIsNone(switch._animation_job)

    def test_reverse_mid_animation_returns_to_zero(self):
        switch = self.make_switch(0.0, 1.0)
        switch._tick_animation()
        switch._animation_target = 0.0

        for _ in range(SWITCH_ANIMATION_STEPS):
            switch._tick_animation()

        self.assertEqual(switch._slider_value, 0.0)
        self.assertIsNone(switch._animation_job)

    def test_animate_to_schedules_only_one_job(self):
        switch = self.make_switch(0.0, 0.0)

        switch._animate_to(1.0)
        switch._animate_to(1.0)

        self.assertEqual(len(switch.jobs), 1)
        self.assertEqual(switch._animation_job, 'job')

    def test_destroyed_switch_does_not_schedule(self):
        switch = self.make_switch(0.0, 0.0)
        switch._destroyed = True

        switch._animate_to(1.0)
        switch._tick_animation()

        self.assertEqual(switch.jobs, [])
        self.assertIsNone(switch._animation_job)

    def test_unsupported_adapter_switches_immediately(self):
        switch = self.make_switch(0.0, 0.0)
        switch._adapter = SimpleNamespace(supported=False)

        switch._animate_to(1.0)

        self.assertEqual(switch._slider_value, 1.0)
        self.assertEqual(switch.jobs, [])


if __name__ == '__main__':
    unittest.main()
