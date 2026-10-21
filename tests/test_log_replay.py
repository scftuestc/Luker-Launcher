import unittest
from collections import deque
from unittest.mock import patch

import log_window
from log_queue import BoundedLogQueue
from log_search import LogSearch
from log_store import MAX_LOG_ENTRIES, LogStore
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
        window._display_entry_lines = deque()
        window._display_entry_bytes = deque()
        window._display_bytes = 0
        window._last_log_timestamp = None
        window._display_dirty = True
        window._replay_job = None
        window._replay_active = False
        window._replay_entries = []
        window._replay_index = 0
        window._replay_tail = deque(maxlen=MAX_LOG_ENTRIES)

        batches: list[list] = []
        window._add_log_lines = lambda entries: batches.append(list(entries))

        after_calls: list[tuple[int, object]] = []

        def fake_after(delay: int, callback) -> str:
            after_calls.append((delay, callback))
            return f"job-{len(after_calls)}"

        window.after = fake_after
        cancel_calls: list[str] = []
        window.after_cancel = cancel_calls.append
        window.winfo_exists = lambda: True
        window._search_calls = 0

        def fake_search() -> None:
            window._search_calls += 1

        window._run_search = fake_search
        return window, batches, after_calls, cancel_calls

    def test_refresh_schedules_chunks_without_bulk_insert(self):
        window, batches, after_calls, _cancel_calls = self._make_window(["a", "b", "c"])

        with patch.object(log_window, "REPLAY_BATCH_SIZE", 2):
            window._refresh_log_display()

            self.assertTrue(window._replay_active)
            self.assertEqual(batches, [])
            self.assertEqual(len(after_calls), 1)

            delay, first_chunk = after_calls.pop(0)
            self.assertEqual(delay, log_window.REPLAY_YIELD_MS)
            first_chunk()
            self.assertEqual([entry.text for entry in batches[0]], ["a", "b"])

            after_calls.pop(0)[1]()
            self.assertEqual([entry.text for entry in batches[1]], ["c"])
            self.assertFalse(window._replay_active)

    def test_live_logs_wait_in_tail_during_replay(self):
        window, batches, after_calls, _cancel_calls = self._make_window(["old"])
        window._refresh_log_display()
        pending = BoundedLogQueue(max_lines=10, max_bytes=100)
        pending.put("live")

        window._drain_log_queue(pending, window._luker_store, "luker")

        self.assertEqual([entry.text for entry in window._replay_tail], ["live"])
        self.assertEqual(batches, [])

        while after_calls:
            after_calls.pop(0)[1]()

        self.assertEqual([entry.text for entry in batches[-1]], ["live"])
        self.assertFalse(window._replay_active)

    def test_hide_cancels_replay_and_marks_dirty(self):
        window, _batches, _after_calls, cancel_calls = self._make_window(["a"])
        window._refresh_log_display()
        window.withdraw = lambda: None

        window.hide()

        self.assertFalse(window._replay_active)
        self.assertTrue(window._display_dirty)
        self.assertEqual(cancel_calls, ["job-1"])

    def test_finish_replay_runs_search_only_when_query_exists(self):
        window, _batches, _after_calls, _cancel_calls = self._make_window([])
        window._replay_active = True
        window._replay_entries = []
        window._replay_tail = deque()

        window._finish_replay()
        self.assertEqual(window._search_calls, 0)

        window._search_var.value = "needle"
        window._replay_active = True
        window._finish_replay()
        self.assertEqual(window._search_calls, 1)

    def test_cancel_replay_clears_snapshot_and_tail(self):
        window, _batches, _after_calls, cancel_calls = self._make_window([])
        window._replay_job = "job-9"
        window._replay_active = True
        window._replay_entries = [object()]
        window._replay_index = 1
        window._replay_tail.append(object())

        window._cancel_replay()

        self.assertEqual(cancel_calls, ["job-9"])
        self.assertFalse(window._replay_active)
        self.assertEqual(window._replay_entries, [])
        self.assertEqual(window._replay_index, 0)
        self.assertEqual(len(window._replay_tail), 0)


if __name__ == "__main__":
    unittest.main()
