import unittest
from unittest.mock import patch

import log_replay
from log_display import LogDisplay
from log_queue import BoundedLogQueue
from log_replay import LogReplay
from log_search import LogSearch
from log_store import LogStore
from log_window import LogWindow


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class FakeText:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    def configure(self, **_kwargs) -> None:
        pass

    def delete(self, start: str, end: str) -> None:
        self.deleted.append((start, end))

    def tag_remove(self, *_args) -> None:
        pass


class FakeNav:
    def pack_forget(self) -> None:
        pass


class FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, **kwargs) -> None:
        self.text = kwargs.get("text", "")


class ReplayTests(unittest.TestCase):
    def _make_window(self, lines: list[str]):
        window = object.__new__(LogWindow)
        window._get_textbox = lambda: FakeText()
        window._search_var = FakeVar()
        window._search_job = None
        window._search_nav = FakeNav()
        window._search_count_label = FakeLabel()
        window._search = LogSearch(
            lambda: FakeText(),
            window._search_count_label,
            window._search_nav,
            lambda: {},
        )
        window.count_label = FakeLabel()
        window._luker_store = LogStore()
        window._gcl_store = LogStore()
        for line in lines:
            window._luker_store.append(line)
        window._log_source = "luker"
        window._display = LogDisplay(lambda: FakeText(), FakeLabel())
        window._display_dirty = True

        batches: list[list] = []
        window._add_log_lines = lambda entries: batches.append(list(entries))

        after_calls: list[tuple[int, object]] = []

        def fake_after(delay: int, callback) -> str:
            after_calls.append((delay, callback))
            return f"job-{len(after_calls)}"

        cancel_calls: list[str] = []
        window.after = fake_after
        window.after_cancel = cancel_calls.append
        window.winfo_exists = lambda: True
        window._search_calls = 0

        def fake_search() -> None:
            window._search_calls += 1

        window._run_search = fake_search
        window._replay = LogReplay(
            schedule=fake_after,
            cancel=cancel_calls.append,
            add_entries=window._add_log_lines,
            exists=window.winfo_exists,
            on_finished=window._on_replay_finished,
        )
        return window, batches, after_calls, cancel_calls

    def test_refresh_schedules_chunks_without_bulk_insert(self):
        window, batches, after_calls, _cancel_calls = self._make_window(["a", "b", "c"])

        with patch.object(log_replay, "REPLAY_BATCH_SIZE", 2):
            window._refresh_log_display()

            self.assertTrue(window._replay.active)
            self.assertEqual(batches, [])
            self.assertEqual(len(after_calls), 1)

            delay, first_chunk = after_calls.pop(0)
            self.assertEqual(delay, log_replay.REPLAY_YIELD_MS)
            first_chunk()
            self.assertEqual([entry.text for entry in batches[0]], ["a", "b"])

            after_calls.pop(0)[1]()
            self.assertEqual([entry.text for entry in batches[1]], ["c"])
            self.assertFalse(window._replay.active)

    def test_live_logs_wait_in_tail_during_replay(self):
        window, batches, after_calls, _cancel_calls = self._make_window(["old"])
        window._refresh_log_display()
        pending = BoundedLogQueue(max_lines=10, max_bytes=100)
        pending.put("live")

        window._drain_log_queue(pending, window._luker_store, "luker")

        self.assertEqual([entry.text for entry in window._replay.tail], ["live"])
        self.assertEqual(batches, [])

        while after_calls:
            after_calls.pop(0)[1]()

        self.assertEqual([entry.text for entry in batches[-1]], ["live"])
        self.assertFalse(window._replay.active)

    def test_hide_cancels_replay_and_marks_dirty(self):
        window, _batches, _after_calls, cancel_calls = self._make_window(["a"])
        window._refresh_log_display()
        window.withdraw = lambda: None

        window.hide()

        self.assertFalse(window._replay.active)
        self.assertTrue(window._display_dirty)
        self.assertEqual(cancel_calls, ["job-1"])

    def test_finish_replay_runs_search_only_when_query_exists(self):
        window, _batches, after_calls, _cancel_calls = self._make_window(["a"])
        window._search_var.value = "needle"
        window._refresh_log_display()

        while after_calls:
            after_calls.pop(0)[1]()

        self.assertEqual(window._search_calls, 1)

    def test_cancel_replay_clears_snapshot_and_tail(self):
        window, _batches, _after_calls, cancel_calls = self._make_window([])
        window._replay.job = "job-9"
        window._replay.active = True
        window._replay.entries = [object()]
        window._replay.index = 1
        window._replay.tail.append(object())

        window._replay.cancel()

        self.assertEqual(cancel_calls, ["job-9"])
        self.assertFalse(window._replay.active)
        self.assertEqual(window._replay.entries, [])
        self.assertEqual(window._replay.index, 0)
        self.assertEqual(len(window._replay.tail), 0)


if __name__ == "__main__":
    unittest.main()
