import unittest
from types import SimpleNamespace
from unittest.mock import patch

import tray.menu as tray_menu
from core.readiness import LukerState
from tray.menu import TrayMenu
from ui.theme import LOGO_STOPPED_COLOR


class BlurChangeTests(unittest.TestCase):
    def test_blur_change_applies_when_window_exists(self):
        window = object.__new__(TrayMenu)
        window.winfo_exists = lambda: True
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(False)

        self.assertEqual(calls, [True])

    def test_blur_change_ignored_when_window_destroyed(self):
        window = object.__new__(TrayMenu)
        window.winfo_exists = lambda: False
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(False)

        self.assertEqual(calls, [])

    def test_setup_blur_reads_config(self):
        window = object.__new__(TrayMenu)
        window.COLORS = {'bg': '#112233'}
        fake_config = SimpleNamespace(blur_enabled=False)

        with (
            patch.object(tray_menu, 'config', fake_config),
            patch.object(tray_menu, 'sync_window_blur') as sync_mock,
        ):
            window._setup_blur()

        sync_mock.assert_called_once_with(
            window,
            '#112233',
            enabled=False,
            window_alpha=0.95,
            tint_alpha=0xEE,
            context='托盘菜单',
        )


class HideTests(unittest.TestCase):
    def test_hide_cancels_animation_and_mouse_poll(self):
        menu = object.__new__(TrayMenu)
        menu._menu_animation_id = 'anim'
        menu._menu_animation_active = True
        menu._mouse_poll_id = 'poll'
        canceled: list[object] = []
        menu.after_cancel = canceled.append
        withdrawn: list[bool] = []
        menu.withdraw = lambda: withdrawn.append(True)

        menu.hide()

        self.assertEqual(canceled, ['anim', 'poll'])
        self.assertIsNone(menu._menu_animation_id)
        self.assertIsNone(menu._mouse_poll_id)
        self.assertFalse(menu._menu_animation_active)
        self.assertEqual(withdrawn, [True])


class FakePack:
    def __init__(self) -> None:
        self.options: dict[str, object] | None = None

    def pack(self, **options: object) -> None:
        self.options = options

    def pack_forget(self) -> None:
        self.options = None


class GclVisibilityTests(unittest.TestCase):
    def make_menu(self) -> TrayMenu:
        menu = object.__new__(TrayMenu)
        menu._gcl_separator = FakePack()
        menu._bottom_separator = object()
        menu.menu_items = {
            'gcl_toggle': {'frame': FakePack()},
            'gcl_browser': {'frame': FakePack()},
        }
        return menu

    def test_visible_items_are_inserted_before_bottom_separator(self):
        menu = self.make_menu()

        menu._set_gcl_items_visible(True)

        self.assertIs(menu._gcl_separator.options['before'], menu._bottom_separator)
        self.assertIs(
            menu.menu_items['gcl_toggle']['frame'].options['before'],
            menu._bottom_separator,
        )
        self.assertIs(
            menu.menu_items['gcl_browser']['frame'].options['before'],
            menu._bottom_separator,
        )

    def test_hidden_items_are_forgotten(self):
        menu = self.make_menu()
        menu._set_gcl_items_visible(True)

        menu._set_gcl_items_visible(False)

        self.assertIsNone(menu._gcl_separator.options)
        self.assertIsNone(menu.menu_items['gcl_toggle']['frame'].options)
        self.assertIsNone(menu.menu_items['gcl_browser']['frame'].options)


class FakeBar:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class FakeButton(FakeBar):
    pass


class MenuLogoStateTests(unittest.TestCase):
    def make_menu(self, state: LukerState) -> TrayMenu:
        menu = object.__new__(TrayMenu)
        menu._luker_state = state
        menu._menu_logo_bars = [FakeBar() for _ in range(4)]
        menu._menu_logo_gray = True
        menu._menu_animation_id = None
        menu._menu_animation_active = False
        menu._animation_phase = 0.0
        menu.winfo_viewable = lambda: True
        menu.after = lambda _delay, _callback: 'job'
        return menu

    def test_stopped_sets_gray_and_stops_animation(self):
        menu = self.make_menu(LukerState.STOPPED)
        menu._menu_logo_gray = False

        menu._animate_menu()

        for bar in menu._menu_logo_bars:
            self.assertEqual(bar.options['fg_color'], LOGO_STOPPED_COLOR)
        self.assertFalse(menu._menu_animation_active)
        self.assertIsNone(menu._menu_animation_id)

    def test_ready_animates_with_shared_glow_color(self):
        menu = self.make_menu(LukerState.READY)

        with patch.object(tray_menu, 'logo_bar_glow_color', return_value='#123456'):
            menu._start_menu_animation()

        for bar in menu._menu_logo_bars:
            self.assertEqual(bar.options['fg_color'], '#123456')
        self.assertEqual(menu._menu_animation_id, 'job')
        self.assertTrue(menu._menu_animation_active)

    def test_set_ready_updates_toggle_text_and_icon(self):
        menu = self.make_menu(LukerState.STOPPED)
        button = FakeButton()
        menu.menu_items = {'luker_toggle': {'btn': button}}
        menu.COLORS = {
            'text_dim': '#111111',
            'error': '#222222',
            'success': '#333333',
            'accent': '#444444',
            'text_muted': '#555555',
        }
        menu.winfo_viewable = lambda: False

        with patch.object(
            tray_menu,
            'menu_icon',
            side_effect=lambda kind, color, **_kwargs: f'{kind}:{color}',
        ):
            menu.set_luker_state(LukerState.READY)

        self.assertEqual(button.options['text'], '停止 Luker')
        self.assertEqual(button.options['image'], 'stop:#222222')
        self.assertEqual(button.options['text_color'], '#222222')
        self.assertTrue(menu._is_running)

    def test_set_stopped_updates_toggle_text_and_icon(self):
        menu = self.make_menu(LukerState.READY)
        button = FakeButton()
        menu.menu_items = {'luker_toggle': {'btn': button}}
        menu.COLORS = {
            'text_dim': '#111111',
            'error': '#222222',
            'success': '#333333',
            'accent': '#444444',
            'text_muted': '#555555',
        }
        menu.winfo_viewable = lambda: False

        with patch.object(
            tray_menu,
            'menu_icon',
            side_effect=lambda kind, color, **_kwargs: f'{kind}:{color}',
        ):
            menu.set_luker_state(LukerState.STOPPED)

        self.assertEqual(button.options['text'], '启动 Luker')
        self.assertEqual(button.options['image'], 'play:#333333')
        self.assertEqual(button.options['text_color'], '#333333')
        self.assertFalse(menu._is_running)

    def test_restart_icon_and_disabled_text_share_muted_color(self):
        menu = self.make_menu(LukerState.STOPPED)
        toggle = FakeButton()
        restart = FakeButton()
        menu._is_running = False
        menu.menu_items = {
            'luker_toggle': {'btn': toggle},
            'restart': {'btn': restart},
        }
        menu.COLORS = {
            'text_dim': '#111111',
            'error': '#222222',
            'success': '#333333',
            'accent': '#444444',
            'text_muted': '#555555',
        }

        with patch.object(
            tray_menu,
            'menu_icon',
            side_effect=lambda kind, color, **_kwargs: f'{kind}:{color}',
        ):
            menu._apply_luker_toggle()

        self.assertEqual(restart.options['state'], 'disabled')
        self.assertEqual(restart.options['image'], 'refresh:#555555')
        self.assertEqual(restart.options['text_color'], '#555555')
        self.assertEqual(restart.options['text_color_disabled'], '#555555')

    def test_restart_icon_matches_accent_when_enabled(self):
        menu = self.make_menu(LukerState.READY)
        toggle = FakeButton()
        restart = FakeButton()
        menu._is_running = True
        menu.menu_items = {
            'luker_toggle': {'btn': toggle},
            'restart': {'btn': restart},
        }
        menu.COLORS = {
            'text_dim': '#111111',
            'error': '#222222',
            'success': '#333333',
            'accent': '#444444',
            'text_muted': '#555555',
        }

        with patch.object(
            tray_menu,
            'menu_icon',
            side_effect=lambda kind, color, **_kwargs: f'{kind}:{color}',
        ):
            menu._apply_luker_toggle()

        self.assertEqual(restart.options['state'], 'normal')
        self.assertEqual(restart.options['image'], 'refresh:#444444')
        self.assertEqual(restart.options['text_color'], '#444444')


if __name__ == '__main__':
    unittest.main()
