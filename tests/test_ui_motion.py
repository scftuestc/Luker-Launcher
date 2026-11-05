import tkinter as tk
import unittest

from luker_launcher.ui.motion import WindowFade, ease_in_out_cubic, ease_out_cubic, fade_palette


class FakeWindow:
    def __init__(self, exists: bool = True) -> None:
        self.alpha: list[float] = []
        self.jobs: dict[str, tuple[int, object, tuple[object, ...]]] = {}
        self._next_id = 0
        self.exists = exists

    def attributes(self, name: str, value: float) -> None:
        self.alpha.append((name, value))

    def after(self, delay: int, callback: object, *args: object) -> str:
        self._next_id += 1
        job = str(self._next_id)
        self.jobs[job] = (delay, callback, args)
        return job

    def after_cancel(self, job: str) -> None:
        self.jobs.pop(job, None)

    def winfo_exists(self) -> bool:
        return self.exists

    def run_next(self) -> None:
        job = min(self.jobs, key=int)
        _delay, callback, args = self.jobs.pop(job)
        callback(*args)  # type: ignore[operator]


class EasingTests(unittest.TestCase):
    def test_endpoints_and_monotonicity(self):
        self.assertEqual(ease_out_cubic(0.0), 0.0)
        self.assertEqual(ease_out_cubic(1.0), 1.0)
        self.assertEqual(ease_in_out_cubic(0.0), 0.0)
        self.assertEqual(ease_in_out_cubic(1.0), 1.0)
        values = [ease_out_cubic(i / 10) for i in range(11)]
        self.assertEqual(values, sorted(values))

    def test_out_of_range_is_clamped(self):
        self.assertEqual(ease_out_cubic(-1.0), 0.0)
        self.assertEqual(ease_out_cubic(2.0), 1.0)


class PaletteFadeTests(unittest.TestCase):
    def test_interpolates_and_snaps_to_endpoints(self):
        start = {'bg': '#000000', 'text': '#ffffff'}
        end = {'bg': '#ffffff', 'text': '#000000'}

        self.assertEqual(fade_palette(start, end, 0.0), start)
        self.assertEqual(fade_palette(start, end, 1.0), end)
        middle = fade_palette(start, end, 0.5)
        self.assertNotEqual(middle['bg'], start['bg'])
        self.assertNotEqual(middle['bg'], end['bg'])


class WindowFadeTests(unittest.TestCase):
    def test_fades_to_target_and_calls_done_once(self):
        window = FakeWindow()
        done: list[bool] = []
        fade = WindowFade(window, interval_ms=10)

        fade.start(0.0, 1.0, duration_ms=20, on_done=lambda: done.append(True))

        self.assertTrue(fade.running)
        self.assertEqual(window.alpha[0], ('-alpha', 0.0))
        while window.jobs:
            window.run_next()

        self.assertFalse(fade.running)
        self.assertEqual(window.alpha[-1], ('-alpha', 1.0))
        self.assertEqual(done, [True])

    def test_cancel_stops_and_can_reset_alpha(self):
        window = FakeWindow()
        fade = WindowFade(window, interval_ms=10)
        fade.start(0.0, 1.0, duration_ms=100)
        window.run_next()

        fade.cancel(reset=0.5)

        self.assertFalse(fade.running)
        self.assertEqual(window.jobs, {})
        self.assertEqual(window.alpha[-1], ('-alpha', 0.5))

    def test_destroyed_window_stops_without_done(self):
        window = FakeWindow(exists=False)
        done: list[bool] = []
        fade = WindowFade(window, interval_ms=10)
        fade.start(0.0, 1.0, duration_ms=20, on_done=lambda: done.append(True))

        while window.jobs:
            window.run_next()

        self.assertFalse(fade.running)
        self.assertEqual(done, [])


class TclErrorGuardTests(unittest.TestCase):
    def test_attributes_tcl_error_is_ignored(self):
        class BrokenWindow(FakeWindow):
            def attributes(self, name: str, value: float) -> None:
                raise tk.TclError('gone')

        window = BrokenWindow()
        fade = WindowFade(window, interval_ms=10)
        fade.start(0.0, 1.0, duration_ms=10)
        self.assertEqual(window.alpha, [])


if __name__ == '__main__':
    unittest.main()
