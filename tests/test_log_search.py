import unittest
from collections import deque
from unittest.mock import patch

import log_window
from log_window import LogWindow


class FakeText:
    def __init__(self) -> None:
        self.added: list[tuple[str, str, str]] = []
        self.raised: list[tuple[str, ...]] = []
        self.deleted: list[tuple[str, str]] = []

    def tag_remove(self, *args) -> None:
        pass

    def tag_add(self, *args) -> None:
        self.added.append(args)

    def tag_raise(self, *args) -> None:
        self.raised.append(args)

    def tag_configure(self, *args, **kwargs) -> None:
        pass

    def see(self, *args) -> None:
        pass

    def configure(self, **kwargs) -> None:
        pass

    def delete(self, start: str, end: str) -> None:
        self.deleted.append((start, end))


class SearchText(FakeText):
    def __init__(self, positions: list[str]) -> None:
        super().__init__()
        self._positions = iter(positions)
        self.search_calls = 0

    def search(self, *args, **kwargs) -> str:
        self.search_calls += 1
        return next(self._positions, "")


class FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, **kwargs) -> None:
        self.text = kwargs.get("text", "")


class SearchAdjustTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window = object.__new__(LogWindow)
        self.text = FakeText()
        self.label = FakeLabel()
        self.window._search_results = []
        self.window._search_current_index = -1
        self.window._search_truncated = False
        self.window._get_textbox = lambda: self.text
        self.window._search_count_label = self.label

    @staticmethod
    def _results(lines: range) -> list[tuple[str, str]]:
        return [(f"{line}.0", f"{line}.1") for line in lines]

    def test_index_moves_back_when_earlier_results_are_removed(self):
        self.window._search_results = self._results(range(1, 11))
        self.window._search_current_index = 5

        self.window._adjust_search_positions(3)

        self.assertEqual(self.window._search_current_index, 2)
        self.assertEqual(self.text.added, [("search_current", "3.0", "3.1")])
        self.assertEqual(self.label.text, "3/7")

    def test_current_result_removed_selects_next_result(self):
        self.window._search_results = self._results(range(1, 4))
        self.window._search_current_index = 1

        self.window._adjust_search_positions(2)

        self.assertEqual(self.window._search_current_index, 0)
        self.assertEqual(self.text.added, [("search_current", "1.0", "1.1")])
        self.assertEqual(self.label.text, "1/1")

    def test_all_results_removed_clears_state(self):
        self.window._search_results = self._results(range(1, 3))
        self.window._search_current_index = 0

        self.window._adjust_search_positions(5)

        self.assertEqual(self.window._search_results, [])
        self.assertEqual(self.window._search_current_index, -1)
        self.assertEqual(self.label.text, "0/0")


class DisplayTrimTests(unittest.TestCase):
    def test_byte_limit_removes_oldest_entries(self):
        window = object.__new__(LogWindow)
        window._display_entry_lines = deque([1, 1, 1])
        window._display_entry_bytes = deque([5, 5, 5])
        window._display_bytes = 15
        window._search_results = []
        window._get_textbox = lambda: FakeText()

        with patch.object(log_window, "MAX_LOG_BYTES", 10):
            window._trim_display()

        self.assertEqual(list(window._display_entry_lines), [1, 1])
        self.assertEqual(list(window._display_entry_bytes), [5, 5])
        self.assertEqual(window._display_bytes, 10)


class SearchLimitTests(unittest.TestCase):
    def _run_search(self, positions: list[str]):
        window = object.__new__(LogWindow)
        text = SearchText(positions)
        window._get_textbox = lambda: text
        window._search_results = []
        window._search_current_index = -1
        window._search_truncated = False
        window._search_count_label = FakeLabel()
        window.COLORS = {'warning': '#ffffff', 'accent': '#000000'}

        with patch.object(log_window, "MAX_SEARCH_RESULTS", 3):
            window._perform_search("x")
        return window, text

    def test_stops_at_limit_and_marks_truncated(self):
        window, text = self._run_search(["1.0", "1.1", "1.2", "1.3"])

        self.assertEqual(len(window._search_results), 3)
        self.assertTrue(window._search_truncated)
        self.assertEqual(window._search_count_label.text, "1/3+")
        self.assertEqual(text.search_calls, 4)

    def test_exact_limit_is_not_truncated(self):
        window, text = self._run_search(["1.0", "1.1", "1.2"])

        self.assertEqual(len(window._search_results), 3)
        self.assertFalse(window._search_truncated)
        self.assertEqual(window._search_count_label.text, "1/3")
        self.assertEqual(text.search_calls, 4)


if __name__ == "__main__":
    unittest.main()
