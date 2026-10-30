import unittest

from ui.switch import (
    SWITCH_ANIMATION_STEPS,
    AnimatedSwitch,
    switch_thumb_color,
    switch_thumb_hover_color,
    switch_track_colors,
)
from ui.theme import PRESET_THEMES, get_theme_colors


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


if __name__ == '__main__':
    unittest.main()
