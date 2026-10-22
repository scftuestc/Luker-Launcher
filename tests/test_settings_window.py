import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import main
import settings_window
from main import LukerLauncher
from settings_window import (
    _SCROLL_BINDING_SEQUENCES,
    SettingsWindow,
    bind_click_recursive,
    clear_scroll_bindings,
)


class FakeTkInterpreter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def call(self, *args: str) -> None:
        self.calls.append(args)


class FakeWidget:
    def __init__(self) -> None:
        self.tk = FakeTkInterpreter()


class ClickWidget:
    def __init__(self, children: list["ClickWidget"] | None = None) -> None:
        self.children = children or []
        self.bindings: list[tuple[str, object]] = []

    def bind(self, sequence: str, callback: object) -> None:
        self.bindings.append((sequence, callback))

    def winfo_children(self) -> list["ClickWidget"]:
        return self.children


class FakeSettingsWindow:
    instances: ClassVar[list["FakeSettingsWindow"]] = []

    def __init__(
        self,
        parent: object,
        anchor_point: tuple[int, int] | None = None,
        on_close: object = None,
    ) -> None:
        self.parent = parent
        self.anchor_point = anchor_point
        self.on_close = on_close
        self.focused = 0
        self.alive = True
        type(self).instances.append(self)

    def focus_force(self) -> None:
        self.focused += 1

    def is_alive(self) -> bool:
        return self.alive


class FakeTrayMenu:
    def __init__(self) -> None:
        self.state: tuple[bool, bool, bool, bool] | None = None
        self.point: tuple[int, int] | None = None

    def update_state(self, *args: bool) -> None:
        self.state = args

    def show_at(self, x: int, y: int) -> None:
        self.point = (x, y)


class FakeLogWindow:
    def is_visible(self) -> bool:
        return False


class ScrollBindingTests(unittest.TestCase):
    def test_clears_all_known_global_sequences(self):
        widget = FakeWidget()

        clear_scroll_bindings(widget)

        self.assertEqual(
            [call[2] for call in widget.tk.calls],
            list(_SCROLL_BINDING_SEQUENCES),
        )
        self.assertTrue(all(call[:2] == ("bind", "all") for call in widget.tk.calls))
        self.assertTrue(all(call[3] == "" for call in widget.tk.calls))


class ClickBindingTests(unittest.TestCase):
    def test_binds_widget_and_all_descendants(self):
        leaf = ClickWidget()
        middle = ClickWidget([leaf])
        root = ClickWidget([middle])

        def on_click(_event: object) -> None:
            pass

        bind_click_recursive(root, on_click)

        for widget in (root, middle, leaf):
            self.assertEqual(widget.bindings, [('<Button-1>', on_click)])


class FakeSwitch:
    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.selected = False

    def get(self) -> int:
        return self.value

    def select(self) -> None:
        self.selected = True

    def deselect(self) -> None:
        self.selected = False


class BlurToggleTests(unittest.TestCase):
    def test_toggle_writes_config_and_repaints(self):
        window = object.__new__(SettingsWindow)
        window.blur_switch = FakeSwitch(1)
        updates = []
        window.update = lambda: updates.append(True)
        fake_config = SimpleNamespace(blur_enabled=False)

        with patch.object(settings_window, 'config', fake_config):
            window._on_blur_toggle()

        self.assertTrue(fake_config.blur_enabled)
        self.assertEqual(updates, [True])

    def test_toggle_off_writes_false(self):
        window = object.__new__(SettingsWindow)
        window.blur_switch = FakeSwitch(0)
        window.update = lambda: None
        fake_config = SimpleNamespace(blur_enabled=True)

        with patch.object(settings_window, 'config', fake_config):
            window._on_blur_toggle()

        self.assertFalse(fake_config.blur_enabled)

    def test_blur_change_applies_when_alive(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window.blur_switch = FakeSwitch()
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(True)

        self.assertTrue(window.blur_switch.selected)
        self.assertEqual(calls, [True])

    def test_blur_change_ignored_after_destroy(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = True
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(False)

        self.assertEqual(calls, [])


class FakeChild:
    def __init__(self, calls: list[tuple[str, ...]]) -> None:
        self.calls = calls

    def destroy(self) -> None:
        self.calls.append(('destroy',))


class RebuildOrderTests(unittest.TestCase):
    def test_root_background_updates_before_rebuilding_children(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window.COLORS = {'bg': '#123456'}
        calls = []
        window.winfo_exists = lambda: True
        window.winfo_children = lambda: [FakeChild(calls)]
        window.configure = lambda **options: calls.append(('configure', options))
        window._build_ui = lambda: calls.append(('build',))
        window._setup_blur = lambda: calls.append(('blur',))

        with patch.object(
            settings_window,
            'clear_scroll_bindings',
            lambda _widget: calls.append(('clear',)),
        ):
            window._rebuild_ui()

        self.assertEqual(
            calls,
            [
                ('destroy',),
                ('clear',),
                ('configure', {'fg_color': '#123456'}),
                ('build',),
                ('blur',),
            ],
        )


class SettingsWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSettingsWindow.instances.clear()

    @staticmethod
    def _make_launcher() -> LukerLauncher:
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher.log_window = object()
        launcher.settings_window = None
        launcher._tray_anchor = (100, 200)
        return launcher

    def test_open_uses_tray_anchor_and_reuses_alive_window(self):
        launcher = self._make_launcher()

        with patch.object(main, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()
            launcher._open_settings_window()

        self.assertEqual(len(FakeSettingsWindow.instances), 1)
        window = FakeSettingsWindow.instances[0]
        self.assertIs(window.parent, launcher.log_window)
        self.assertEqual(window.anchor_point, (100, 200))
        self.assertEqual(window.focused, 2)
        self.assertEqual(window.on_close, launcher._on_settings_closed)

    def test_closed_window_is_recreated(self):
        launcher = self._make_launcher()

        with patch.object(main, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()
            FakeSettingsWindow.instances[0].alive = False
            launcher._tray_anchor = (300, 400)
            launcher._open_settings_window()

        self.assertEqual(len(FakeSettingsWindow.instances), 2)
        self.assertEqual(FakeSettingsWindow.instances[1].anchor_point, (300, 400))

    def test_close_callback_clears_reference(self):
        launcher = self._make_launcher()
        window = object()
        launcher.settings_window = window

        launcher._on_settings_closed()

        self.assertIsNone(launcher.settings_window)

    def test_exiting_does_not_open_window(self):
        launcher = self._make_launcher()
        launcher._exiting = True

        with patch.object(main, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()

        self.assertEqual(FakeSettingsWindow.instances, [])

    def test_show_tray_menu_stores_anchor(self):
        launcher = self._make_launcher()
        launcher.tray_menu = FakeTrayMenu()
        launcher.log_window = FakeLogWindow()
        launcher.process_manager = None
        launcher.gcl_process_manager = None

        launcher._show_tray_menu(12, 34)

        self.assertEqual(launcher._tray_anchor, (12, 34))
        self.assertEqual(launcher.tray_menu.point, (12, 34))


if __name__ == "__main__":
    unittest.main()
