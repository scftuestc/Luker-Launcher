import unittest

from luker_launcher.tray.menu import TrayMenu, next_menu_key


class FakeFrame:
    def __init__(self, manager: str = "pack") -> None:
        self.manager = manager
        self.options: dict[str, object] = {}

    def winfo_manager(self) -> str:
        return self.manager

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)


class FakeButton:
    def __init__(self, state: str = "normal") -> None:
        self.state = state
        self.invoked = 0

    def cget(self, key: str) -> object:
        return self.state if key == "state" else None

    def invoke(self) -> None:
        self.invoked += 1


def make_menu() -> TrayMenu:
    menu = object.__new__(TrayMenu)
    menu.COLORS = {"card_hover": "#111111", "accent": "#222222"}
    menu._selected_key = None
    menu._menu_focused = True
    menu.menu_items = {
        "window": {"frame": FakeFrame(), "btn": FakeButton()},
        "luker_toggle": {"frame": FakeFrame(), "btn": FakeButton()},
        "restart": {"frame": FakeFrame(), "btn": FakeButton("disabled")},
        "hidden": {"frame": FakeFrame(""), "btn": FakeButton()},
        "exit": {"frame": FakeFrame(), "btn": FakeButton()},
    }
    return menu


class NextMenuKeyTests(unittest.TestCase):
    def test_empty_list_returns_none(self):
        self.assertIsNone(next_menu_key([], None, 1))

    def test_missing_current_enters_from_an_end(self):
        self.assertEqual(next_menu_key(["a", "b"], None, 1), "a")
        self.assertEqual(next_menu_key(["a", "b"], None, -1), "b")

    def test_wraps_in_both_directions(self):
        self.assertEqual(next_menu_key(["a", "b", "c"], "c", 1), "a")
        self.assertEqual(next_menu_key(["a", "b", "c"], "a", -1), "c")


class NavigationTests(unittest.TestCase):
    def test_skips_hidden_and_disabled_items(self):
        menu = make_menu()

        self.assertEqual(menu._navigable_keys(), ["window", "luker_toggle", "exit"])

    def test_down_and_up_wrap_and_highlight(self):
        menu = make_menu()

        menu._on_key_down(None)
        self.assertEqual(menu._selected_key, "window")
        self.assertEqual(
            menu.menu_items["window"]["frame"].options,
            {"fg_color": "#111111", "border_width": 1, "border_color": "#222222"},
        )

        menu._on_key_down(None)
        menu._on_key_down(None)
        self.assertEqual(menu._selected_key, "exit")
        menu._on_key_down(None)
        self.assertEqual(menu._selected_key, "window")
        menu._on_key_up(None)
        self.assertEqual(menu._selected_key, "exit")

    def test_clear_selection_restores_frame(self):
        menu = make_menu()
        menu._select_key("window")

        menu._clear_selection()

        self.assertIsNone(menu._selected_key)
        self.assertEqual(menu.menu_items["window"]["frame"].options["fg_color"], "transparent")
        self.assertEqual(menu.menu_items["window"]["frame"].options["border_width"], 0)

    def test_enter_invokes_selected_item(self):
        menu = make_menu()
        menu._select_key("luker_toggle")

        result = menu._on_key_activate(None)

        self.assertEqual(result, "break")
        self.assertEqual(menu.menu_items["luker_toggle"]["btn"].invoked, 1)

    def test_enter_does_not_invoke_disabled_item(self):
        menu = make_menu()
        menu._select_key("restart")

        menu._on_key_activate(None)

        self.assertEqual(menu.menu_items["restart"]["btn"].invoked, 0)

    def test_escape_hides_menu(self):
        menu = make_menu()
        calls: list[bool] = []
        menu.hide = lambda restore_focus=True: calls.append(restore_focus)

        result = menu._on_key_escape(None)

        self.assertEqual(result, "break")
        self.assertEqual(calls, [True])


class HideFocusTests(unittest.TestCase):
    def make_hiding_menu(self) -> tuple[TrayMenu, list[object]]:
        menu = make_menu()
        menu._menu_focused = True
        menu._previous_foreground = 123
        menu._fade = None
        menu._menu_animation_id = None
        menu._mouse_poll_id = None
        menu.withdraw = lambda: None
        menu._stop_menu_animation = lambda: None
        menu._stop_mouse_poll = lambda: None
        calls: list[object] = []
        menu._set_no_activate = lambda enabled=True: calls.append(("no_activate", enabled))
        menu._restore_foreground = lambda: calls.append("restore")
        return menu, calls

    def test_hide_restores_no_activate_and_foreground(self):
        menu, calls = self.make_hiding_menu()

        menu.hide()

        self.assertEqual(calls, [("no_activate", True), "restore"])

    def test_outside_click_hide_does_not_restore_foreground(self):
        menu, calls = self.make_hiding_menu()

        menu.hide(restore_focus=False)

        self.assertEqual(calls, [("no_activate", True)])


if __name__ == "__main__":
    unittest.main()
