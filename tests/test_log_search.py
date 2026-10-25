import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import patch

import log.display
import log.search
from log.display import LogDisplay
from log.search import LogSearch, SearchBar


class FakeText:
    def __init__(self) -> None:
        self.added: list[tuple[str, str, str]] = []
        self.raised: list[tuple[str, ...]] = []
        self.deleted: list[tuple[str, str]] = []
        self.tag_configs: list[tuple[str, dict]] = []

    def tag_remove(self, *args) -> None:
        pass

    def tag_add(self, *args) -> None:
        self.added.append(args)

    def tag_raise(self, *args) -> None:
        self.raised.append(args)

    def tag_configure(self, tag: str, **kwargs) -> None:
        self.tag_configs.append((tag, kwargs))

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


class FakeNav:
    def pack_forget(self) -> None:
        pass


class FakeHint:
    def __init__(self) -> None:
        self.place_calls: list[dict[str, object]] = []
        self.hidden = 0

    def place(self, **options: object) -> None:
        self.place_calls.append(options)

    def place_forget(self) -> None:
        self.hidden += 1


class FakeVar:
    def __init__(self, value: str = '') -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def make_search(text: FakeText, label: FakeLabel | None = None) -> LogSearch:
    return LogSearch(
        lambda: text,
        label or FakeLabel(),
        FakeNav(),
        lambda: {
            "warning": "#ffffff",
            "accent": "#000000",
            "bg": "#111111",
            "on_accent": "#eeeeee",
        },
    )


class SearchColorTests(unittest.TestCase):
    def test_refresh_colors_reconfigures_highlight_tags(self):
        text = FakeText()
        search = make_search(text)

        search.refresh_colors()

        self.assertEqual(
            text.tag_configs,
            [
                ("search_highlight", {"background": "#ffffff", "foreground": "#111111"}),
                ("search_current", {"background": "#000000", "foreground": "#eeeeee"}),
            ],
        )


class SearchAdjustTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = FakeText()
        self.label = FakeLabel()
        self.search = make_search(self.text, self.label)

    @staticmethod
    def _results(lines: range) -> list[tuple[str, str]]:
        return [(f"{line}.0", f"{line}.1") for line in lines]

    def test_index_moves_back_when_earlier_results_are_removed(self):
        self.search.results = self._results(range(1, 11))
        self.search.current_index = 5

        self.search.adjust(3)

        self.assertEqual(self.search.current_index, 2)
        self.assertEqual(self.text.added, [("search_current", "3.0", "3.1")])
        self.assertEqual(self.label.text, "3/7")

    def test_current_result_removed_selects_next_result(self):
        self.search.results = self._results(range(1, 4))
        self.search.current_index = 1

        self.search.adjust(2)

        self.assertEqual(self.search.current_index, 0)
        self.assertEqual(self.text.added, [("search_current", "1.0", "1.1")])
        self.assertEqual(self.label.text, "1/1")

    def test_all_results_removed_clears_state(self):
        self.search.results = self._results(range(1, 3))
        self.search.current_index = 0

        self.search.adjust(5)

        self.assertEqual(self.search.results, [])
        self.assertEqual(self.search.current_index, -1)
        self.assertEqual(self.label.text, "0/0")


class DisplayTrimTests(unittest.TestCase):
    def test_byte_limit_removes_oldest_entries(self):
        text = FakeText()
        display = LogDisplay(lambda: text, FakeLabel())
        display.entry_lines = deque([1, 1, 1])
        display.entry_bytes = deque([5, 5, 5])
        display.bytes = 15

        with patch.object(log.display, "MAX_LOG_BYTES", 10):
            removed = display.trim()

        self.assertEqual(removed, 1)
        self.assertEqual(list(display.entry_lines), [1, 1])
        self.assertEqual(list(display.entry_bytes), [5, 5])
        self.assertEqual(display.bytes, 10)


class SearchLimitTests(unittest.TestCase):
    def _run_search(self, positions: list[str]) -> tuple[LogSearch, SearchText]:
        text = SearchText(positions)
        search = make_search(text)

        with patch.object(log.search, "MAX_SEARCH_RESULTS", 3):
            search.perform("x")
        return search, text

    def test_stops_at_limit_and_marks_truncated(self):
        search, text = self._run_search(["1.0", "1.1", "1.2", "1.3"])

        self.assertEqual(len(search.results), 3)
        self.assertTrue(search.truncated)
        self.assertEqual(search.count_text(0), "1/3+")
        self.assertEqual(text.search_calls, 4)

    def test_exact_limit_is_not_truncated(self):
        search, text = self._run_search(["1.0", "1.1", "1.2"])

        self.assertEqual(len(search.results), 3)
        self.assertFalse(search.truncated)
        self.assertEqual(search.count_text(0), "1/3")
        self.assertEqual(text.search_calls, 4)


class SearchHintTests(unittest.TestCase):
    def make_bar(self, value: str = '', focused: bool = False) -> SearchBar:
        bar = object.__new__(SearchBar)
        bar._focused = focused
        bar.var = FakeVar(value)
        bar.entry = object()
        bar.hint = FakeHint()
        bar._get_scaling = lambda: 1.0
        return bar

    def test_empty_and_unfocused_shows_hint_over_entry(self):
        bar = self.make_bar()

        bar._update_hint()

        self.assertEqual(bar.hint.hidden, 0)
        self.assertEqual(
            bar.hint.place_calls,
            [
                {
                    'in_': bar.entry,
                    'x': 6,
                    'rely': 0.5,
                    'anchor': 'w',
                }
            ],
        )
        self.assertEqual(bar.var.get(), '')

    def test_non_empty_text_hides_hint(self):
        bar = self.make_bar('luker')

        bar._update_hint()

        self.assertEqual(bar.hint.place_calls, [])
        self.assertEqual(bar.hint.hidden, 1)

    def test_focused_entry_hides_hint(self):
        bar = self.make_bar(focused=True)

        bar._update_hint()

        self.assertEqual(bar.hint.place_calls, [])
        self.assertEqual(bar.hint.hidden, 1)

    def test_focus_handlers_toggle_hint(self):
        bar = self.make_bar()

        bar._on_focus_in()
        self.assertTrue(bar.focused)
        self.assertEqual(bar.hint.hidden, 1)

        bar._on_focus_out()
        self.assertFalse(bar.focused)
        self.assertEqual(len(bar.hint.place_calls), 1)


class SearchBehaviorTests(unittest.TestCase):
    def make_bar(self, value: str = '') -> tuple[SearchBar, list[str]]:
        bar = object.__new__(SearchBar)
        calls: list[str] = []
        bar._job = None
        bar._clearing = False
        bar._focused = False
        bar.var = FakeVar(value)
        bar.hint = FakeHint()
        bar._get_scaling = lambda: 1.0
        bar._host = SimpleNamespace(
            after=lambda delay, callback: calls.append(f'after:{delay}') or 'job',
            after_cancel=lambda job: calls.append(f'cancel:{job}'),
        )
        bar.nav = SimpleNamespace(pack=lambda **options: calls.append('nav'))
        bar.search = SimpleNamespace(
            clear_state=lambda: calls.append('clear'),
            perform=lambda text: calls.append(f'perform:{text}'),
        )
        bar.entry = SimpleNamespace(focus_set=lambda: calls.append('focus'))
        return bar, calls

    def test_clear_search_clears_state_once(self):
        bar, calls = self.make_bar('luker')

        bar.clear_and_focus()

        self.assertEqual(calls, ['clear', 'focus'])
        self.assertEqual(bar.var.get(), '')
        self.assertEqual(len(bar.hint.place_calls), 1)

    def test_non_empty_change_schedules_debounced_search(self):
        bar, calls = self.make_bar('luker')

        bar._on_change()

        self.assertEqual(calls, ['after:250'])

    def test_clear_input_cancels_job_and_clears_state(self):
        bar, calls = self.make_bar('')
        bar._job = 'old'

        bar._on_change()

        self.assertEqual(calls, ['cancel:old', 'clear'])

    def test_rerun_packs_nav_and_performs_search(self):
        bar, calls = self.make_bar('luker')

        bar.rerun()

        self.assertEqual(calls, ['nav', 'perform:luker'])

    def test_reset_cancels_pending_job(self):
        bar, calls = self.make_bar('luker')
        bar._job = 'old'

        bar.reset()

        self.assertEqual(calls, ['cancel:old', 'clear'])


if __name__ == "__main__":
    unittest.main()
