import unittest
from types import SimpleNamespace

from log_search_bar import SearchBar


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


if __name__ == '__main__':
    unittest.main()
