import unittest
from unittest.mock import patch

from core.readiness import LukerState
from log_window import LogWindow
from ui.theme import (
    LOGO_GLOW_INTERVAL_MS,
    LOGO_GLOW_STEP,
    LOGO_STOPPED_COLOR,
    shade_color,
)

COLORS = {
    'bg': '#111111',
    'success': '#22aa44',
    'error': '#cc3344',
    'warning': '#ddaa22',
}


class FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class TransportButtonTests(unittest.TestCase):
    def make_window(self) -> LogWindow:
        window = object.__new__(LogWindow)
        window.COLORS = dict(COLORS)
        window._is_running = False
        window._luker_state = LukerState.STOPPED
        window._logo_is_gray = True
        window._logo_bars = []
        window._play_icon = None
        window.play_btn = FakeWidget()
        window.status_dot = FakeWidget()
        window.status_text = FakeWidget()
        return window

    def test_running_switches_to_stop_icon_and_error_color(self):
        window = self.make_window()

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(LukerState.READY)

        self.assertEqual(window.play_btn.options['image'], 'stop:#111111')
        self.assertEqual(window.play_btn.options['fg_color'], COLORS['error'])
        self.assertEqual(
            window.play_btn.options['hover_color'],
            shade_color(COLORS['error'], 0.85),
        )
        self.assertEqual(
            window.status_text.options,
            {'text': '运行中', 'text_color': COLORS['success']},
        )
        self.assertEqual(
            window.status_dot.options,
            {'text_color': COLORS['success']},
        )

    def test_stopped_switches_to_play_icon_and_success_color(self):
        window = self.make_window()
        window._is_running = True

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(LukerState.STOPPED)

        self.assertEqual(window.play_btn.options['image'], 'play:#111111')
        self.assertEqual(window.play_btn.options['fg_color'], COLORS['success'])
        self.assertEqual(
            window.status_text.options,
            {'text': '已停止', 'text_color': COLORS['error']},
        )

    def test_starting_shows_warning_and_stop_icon(self):
        window = self.make_window()

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(LukerState.STARTING)

        self.assertEqual(window.play_btn.options['image'], 'stop:#111111')
        self.assertEqual(window.play_btn.options['fg_color'], COLORS['error'])
        self.assertEqual(
            window.status_text.options,
            {'text': '启动中', 'text_color': COLORS['warning']},
        )

    def test_starting_and_stopped_turn_logo_gray(self):
        for state in (LukerState.STARTING, LukerState.STOPPED):
            with self.subTest(state=state):
                window = self.make_window()
                bars = [FakeWidget() for _ in range(4)]
                window._logo_bars = bars
                window._logo_is_gray = False

                with patch(
                    'log_window.transport_icon',
                    side_effect=lambda kind, color: f'{kind}:{color}',
                ):
                    window.update_status(state)

                self.assertTrue(window._logo_is_gray)
                for bar in bars:
                    self.assertEqual(bar.options['fg_color'], LOGO_STOPPED_COLOR)

    def test_ready_does_not_force_logo_gray(self):
        window = self.make_window()
        bars = [FakeWidget() for _ in range(4)]
        window._logo_bars = bars
        window._logo_is_gray = False

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(LukerState.READY)

        self.assertFalse(window._logo_is_gray)
        self.assertEqual(bars[0].options, {})

    def test_icon_color_follows_theme_background(self):
        window = self.make_window()
        window.COLORS = {**COLORS, 'bg': '#abcdef'}

        with patch(
            'log_window.transport_icon',
            side_effect=lambda kind, color: f'{kind}:{color}',
        ):
            window.update_status(LukerState.STOPPED)

        self.assertEqual(window.play_btn.options['image'], 'play:#abcdef')


class GlowAnimationTests(unittest.TestCase):
    def make_window(
        self,
        state: LukerState,
        *,
        viewable: bool = True,
    ) -> tuple[LogWindow, list[FakeWidget], list[tuple[int, object]]]:
        window = object.__new__(LogWindow)
        bars = [FakeWidget() for _ in range(4)]
        calls: list[tuple[int, object]] = []

        def schedule(delay: int, callback: object) -> str:
            calls.append((delay, callback))
            return 'job'

        window._luker_state = state
        window._logo_is_gray = True
        window._glow_phase = 0.0
        window._glow_job = None
        window._logo_bars = bars
        window.winfo_viewable = lambda: viewable
        window.after = schedule
        return window, bars, calls

    def test_ready_uses_shared_step_and_interval(self):
        window, bars, calls = self.make_window(LukerState.READY)

        with patch(
            'log_window.logo_bar_glow_color',
            side_effect=lambda index, phase: f'{index}:{phase:.4f}',
        ):
            window._animate_glow()

        self.assertAlmostEqual(window._glow_phase, LOGO_GLOW_STEP)
        self.assertEqual(bars[0].options['fg_color'], f'0:{LOGO_GLOW_STEP:.4f}')
        self.assertEqual(calls[0][0], LOGO_GLOW_INTERVAL_MS)
        self.assertEqual(calls[0][1], window._animate_glow)
        self.assertEqual(window._glow_job, 'job')

    def test_restart_glow_cancels_pending_job_and_animates_now(self):
        window, bars, _calls = self.make_window(LukerState.READY)
        window._glow_job = 'old'
        canceled: list[object] = []
        window.after_cancel = canceled.append

        with patch(
            'log_window.logo_bar_glow_color',
            side_effect=lambda index, phase: f'{index}:{phase:.4f}',
        ):
            window._restart_glow()

        self.assertEqual(canceled, ['old'])
        self.assertAlmostEqual(window._glow_phase, LOGO_GLOW_STEP)
        self.assertEqual(bars[0].options['fg_color'], f'0:{LOGO_GLOW_STEP:.4f}')
        self.assertEqual(window._glow_job, 'job')

    def test_not_ready_turns_bars_gray_and_slows_polling(self):
        window, bars, calls = self.make_window(LukerState.STARTING)
        window._logo_is_gray = False

        window._animate_glow()

        for bar in bars:
            self.assertEqual(bar.options['fg_color'], LOGO_STOPPED_COLOR)
        self.assertTrue(window._logo_is_gray)
        self.assertEqual(calls[0][0], 300)

    def test_hidden_window_does_not_touch_bars(self):
        window, bars, calls = self.make_window(LukerState.READY, viewable=False)
        window._glow_phase = 0.3

        window._animate_glow()

        self.assertEqual(window._glow_phase, 0.3)
        self.assertEqual(bars[0].options, {})
        self.assertEqual(calls[0][0], 500)


if __name__ == '__main__':
    unittest.main()
