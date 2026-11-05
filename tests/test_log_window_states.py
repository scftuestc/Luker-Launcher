import datetime
import unittest

from luker_launcher.log.store import LogEntry
from luker_launcher.services.readiness import LukerState
from luker_launcher.theme import PRESET_THEMES
from luker_launcher.ui.log_window import LogWindow


class FakeOverlay:
    def __init__(self) -> None:
        self.placed = False
        self.lifts = 0

    def place(self, **_kwargs: object) -> None:
        self.placed = True

    def place_forget(self) -> None:
        self.placed = False

    def lift(self) -> None:
        self.lifts += 1


class FakeLabel:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)


class FakeBanner:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}
        self.manager = ""
        self.pack_calls = 0
        self.forget_calls = 0

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)

    def winfo_manager(self) -> str:
        return self.manager

    def pack(self, **_kwargs: object) -> None:
        self.manager = "pack"
        self.pack_calls += 1

    def pack_forget(self) -> None:
        self.manager = ""
        self.forget_calls += 1


class FakeDisplay:
    def __init__(self, count: int = 0, index: str | None = None) -> None:
        self.count = count
        self.last_error_index = index


class FakeLogs:
    def __init__(self, error: LogEntry | None = None) -> None:
        self.last_error = error


class LogWindowStateTests(unittest.TestCase):
    def make_window(
        self,
        *,
        count: int = 0,
        state: LukerState = LukerState.STOPPED,
        replaying: bool = False,
        error: LogEntry | None = None,
        index: str | None = None,
    ) -> LogWindow:
        window = object.__new__(LogWindow)
        window.COLORS = PRESET_THEMES["summer"]
        window._luker_state = state
        window._replaying = replaying
        window._display = FakeDisplay(count, index)
        window._logs = FakeLogs(error)
        window._overlay = FakeOverlay()
        window._overlay_title = FakeLabel()
        window._overlay_detail = FakeLabel()
        window._overlay_job = None
        window._error_banner = FakeBanner()
        window._error_label = FakeLabel()
        window._error_reveal_job = None
        window.log_text = object()
        window.jobs: list[tuple[int, object]] = []
        window.cancelled: list[str] = []
        window.after = lambda delay, callback: (
            window.jobs.append((delay, callback)),
            "job",
        )[1]
        window.after_cancel = window.cancelled.append
        return window

    def test_stopped_empty_state_shows_start_hint(self):
        window = self.make_window()

        window._update_log_state()

        self.assertTrue(window._overlay.placed)
        self.assertEqual(window._overlay_title.options["text"], "还没有日志")
        self.assertIn("开始", window._overlay_detail.options["text"])

    def test_starting_empty_state_shows_starting_text(self):
        window = self.make_window(state=LukerState.STARTING)

        window._update_log_state()

        self.assertEqual(window._overlay_title.options["text"], "正在启动 Luker…")

    def test_replay_shows_loading_after_delay(self):
        window = self.make_window(replaying=True)

        window._update_log_state()

        self.assertFalse(window._overlay.placed)
        self.assertEqual(window.jobs[0][0], 120)
        window.jobs[0][1]()
        self.assertTrue(window._overlay.placed)
        self.assertEqual(window._overlay_title.options["text"], "正在加载日志…")

    def test_replay_with_entries_hides_overlay(self):
        window = self.make_window(count=1, replaying=True)

        window._update_log_state()

        self.assertFalse(window._overlay.placed)

    def test_error_banner_shows_then_hides(self):
        error = LogEntry(datetime.datetime.now(), "[错误] 启动失败")
        window = self.make_window(count=1, error=error, index="1.0")

        window._update_log_state()
        self.assertEqual(window._error_banner.manager, "pack")
        self.assertTrue(str(window._error_label.options["text"]).startswith("最近错误 ·"))

        window._display.count = 0
        window._update_log_state()
        self.assertEqual(window._error_banner.manager, "")

    def test_replay_state_callback_updates_flag(self):
        window = self.make_window()

        window._on_replay_state_change(True)
        self.assertTrue(window._replaying)
        window._on_replay_state_change(False)
        self.assertFalse(window._replaying)


if __name__ == "__main__":
    unittest.main()
