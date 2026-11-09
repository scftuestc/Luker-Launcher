import unittest
from types import SimpleNamespace
from unittest.mock import patch

from luker_launcher.services.readiness import LukerState
from luker_launcher.theme import PRESET_THEMES
from luker_launcher.ui import log_window
from luker_launcher.ui.buttons import button_colors
from luker_launcher.ui.log_window import LogWindow
from luker_launcher.ui.tokens import CHARACTER_MOTTO_WRAP, FONT_MOTTO

COLORS = {
    'bg': '#000001',
    'card': '#000002',
    'card_hover': '#000003',
    'border': '#000004',
    'text': '#000005',
    'text_dim': '#000006',
    'text_muted': '#000007',
    'accent': '#000008',
    'on_accent': '#00000d',
    'success': '#000009',
    'error': '#00000a',
    'warning': '#00000b',
    'info': '#00000c',
}


class FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class BrokenWidget:
    def configure(self, **options: object) -> None:
        raise RuntimeError("控件已销毁")


class FakeTextbox:
    def __init__(self) -> None:
        self.tags: dict[str, dict[str, object]] = {}

    def tag_configure(self, tag: str, **options: object) -> None:
        self.tags[tag] = options


class FakeSearch:
    def __init__(self) -> None:
        self.refresh_count = 0

    def refresh_colors(self) -> None:
        self.refresh_count += 1


class FakePanel:
    def __init__(self) -> None:
        self.removed = 0
        self.shown = 0
        self.width = 320
        self.height = 400
        self.scaling = 1.0

    def grid_remove(self) -> None:
        self.removed += 1

    def grid(self) -> None:
        self.shown += 1

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def _get_widget_scaling(self) -> float:
        return self.scaling


class FakeLabel:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}
        self.mapped = True
        self.reqheight = 20
        self.removed = 0
        self.shown = 0

    def configure(self, **options: object) -> None:
        self.options.update(options)

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def winfo_reqheight(self) -> int:
        return self.reqheight

    def grid(self) -> None:
        self.shown += 1

    def grid_remove(self) -> None:
        self.removed += 1


class FakeCTkImage:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class ThemeArtTests(unittest.TestCase):
    def make_window(self) -> tuple[LogWindow, FakePanel, FakeLabel, FakeLabel]:
        window = object.__new__(LogWindow)
        panel = FakePanel()
        label = FakeLabel()
        motto = FakeLabel()
        window._character_panel = panel
        window._character_label = label
        window._motto_label = motto
        window._character_source = None
        window._character_display_size = None
        window._character_display_scale = None
        window._character_fit_job = None
        window._character_image = None
        return window, panel, label, motto

    def test_deepseek_theme_shows_character_and_motto(self):
        window, panel, label, motto = self.make_window()
        source = SimpleNamespace(size=(528, 704))

        with (
            patch.object(log_window, 'config', SimpleNamespace(theme_name='deepseek')),
            patch.object(log_window, 'theme_log_image', return_value=source),
            patch.object(
                log_window,
                'render_character',
                side_effect=lambda image, _size, _scale: image,
            ),
            patch.object(log_window.ctk, 'CTkImage', FakeCTkImage),
        ):
            window._apply_theme_art()

        self.assertEqual(panel.shown, 1)
        self.assertIsNotNone(window._character_image)
        self.assertIn('image', label.options)
        self.assertEqual(motto.options['text'], PRESET_THEMES['deepseek']['motto'])
        self.assertEqual(motto.shown, 1)
        self.assertEqual(window._character_display_size, (267, 356))

    def test_motto_fits_in_one_line(self):
        motto = PRESET_THEMES['deepseek']['motto']

        self.assertNotIn('，', motto)
        self.assertNotIn('。', motto)
        self.assertLessEqual(len(motto) * FONT_MOTTO, CHARACTER_MOTTO_WRAP)

    def test_theme_without_art_hides_character_panel(self):
        window, panel, _, motto = self.make_window()

        with (
            patch.object(log_window, 'config', SimpleNamespace(theme_name='summer')),
            patch.object(log_window, 'theme_log_image', return_value=None),
        ):
            window._apply_theme_art()

        self.assertEqual(panel.removed, 1)
        self.assertIsNone(window._character_image)
        self.assertEqual(motto.options['text'], '')
        self.assertEqual(motto.removed, 1)


class CharacterFitTests(unittest.TestCase):
    def test_fits_native_aspect_into_panel(self):
        self.assertEqual(
            log_window.fit_character_size((528, 704), 264, 400, 56, 4),
            (252, 336),
        )

    def test_shrinks_when_panel_is_short(self):
        self.assertEqual(
            log_window.fit_character_size((528, 704), 264, 188, 56, 4),
            (93, 124),
        )

    def test_zero_native_size_is_clamped(self):
        self.assertEqual(log_window.fit_character_size((0, 0), 264, 400, 56, 4), (1, 1))


class WidgetScalingTests(unittest.TestCase):
    def test_missing_getter_falls_back_to_one(self):
        self.assertEqual(log_window.widget_scaling(object()), 1.0)

    def test_non_positive_scaling_falls_back_to_one(self):
        class Panel:
            def _get_widget_scaling(self) -> float:
                return 0

        self.assertEqual(log_window.widget_scaling(Panel()), 1.0)


class CharacterScalingTests(unittest.TestCase):
    """winfo_* 返回物理像素，CTkImage 的尺寸是逻辑像素，不能混用。"""

    def make_window(
        self,
        *,
        scaling: float,
        panel_size: tuple[int, int],
        motto_height: int,
    ) -> tuple[LogWindow, FakePanel, FakeLabel]:
        window = object.__new__(LogWindow)
        panel = FakePanel()
        panel.scaling = scaling
        panel.width, panel.height = panel_size
        label = FakeLabel()
        motto = FakeLabel()
        motto.reqheight = motto_height
        window._character_panel = panel
        window._character_label = label
        window._motto_label = motto
        window._character_source = SimpleNamespace(size=(528, 704))
        window._character_display_size = None
        window._character_display_scale = None
        window._character_fit_job = None
        window._character_image = None
        return window, panel, motto

    def test_150_percent_converts_physical_panel_to_logical(self):
        window, _, _ = self.make_window(
            scaling=1.5,
            panel_size=(480, 618),
            motto_height=30,
        )

        with (
            patch.object(
                log_window,
                'render_character',
                side_effect=lambda image, _size, _scale: image,
            ),
            patch.object(log_window.ctk, 'CTkImage', FakeCTkImage),
        ):
            window._fit_character_art()

        self.assertEqual(window._character_display_size, (276, 368))

    def test_125_percent_converts_physical_panel_to_logical(self):
        window, _, _ = self.make_window(
            scaling=1.25,
            panel_size=(400, 515),
            motto_height=25,
        )

        with (
            patch.object(
                log_window,
                'render_character',
                side_effect=lambda image, _size, _scale: image,
            ),
            patch.object(log_window.ctk, 'CTkImage', FakeCTkImage),
        ):
            window._fit_character_art()

        self.assertEqual(window._character_display_size, (276, 368))

    def test_scaling_change_rebuilds_image_when_logical_size_is_unchanged(self):
        window, panel, motto = self.make_window(
            scaling=1.0,
            panel_size=(320, 400),
            motto_height=20,
        )
        created: list[FakeCTkImage] = []

        def make_image(**kwargs: object) -> FakeCTkImage:
            image = FakeCTkImage(**kwargs)
            created.append(image)
            return image

        with (
            patch.object(
                log_window,
                'render_character',
                side_effect=lambda image, _size, _scale: image,
            ),
            patch.object(log_window.ctk, 'CTkImage', make_image),
        ):
            window._fit_character_art()
            self.assertEqual(window._character_display_size, (267, 356))
            self.assertEqual(len(created), 1)

            panel.scaling = 2.0
            panel.width, panel.height = 640, 800
            motto.reqheight = 40
            window._fit_character_art()

        self.assertEqual(window._character_display_size, (267, 356))
        self.assertEqual(len(created), 2)


class ThemeBindingTests(unittest.TestCase):
    def make_window(self) -> tuple[LogWindow, FakeWidget, FakeTextbox, FakeSearch, list[str]]:
        window = object.__new__(LogWindow)
        root = FakeWidget()
        textbox = FakeTextbox()
        search = FakeSearch()
        calls: list[str] = []

        def configure(**options: object) -> None:
            root.configure(**options)

        def setup_blur() -> None:
            calls.append('blur')

        def update_status(state: LukerState) -> None:
            calls.append(f'status:{state.value}')

        def refresh_toolbar_icons() -> None:
            calls.append('icons')

        def get_textbox() -> FakeTextbox:
            return textbox

        window.configure = configure
        window._setup_blur = setup_blur
        window.update_status = update_status
        window._refresh_toolbar_icons = refresh_toolbar_icons
        window._get_textbox = get_textbox
        window.search = search
        window._clear_btn = FakeWidget()
        window.scroll_btn = FakeWidget()
        window._auto_scroll = True
        window._is_running = False
        window._luker_state = LukerState.STOPPED
        window.COLORS = COLORS.copy()
        window._theme_bindings = []
        window._styled_buttons = []
        window._ui_ready = True
        return window, root, textbox, search, calls

    def test_bind_theme_records_widget_and_keys(self):
        window, _, _, _, _ = self.make_window()
        widget = FakeWidget()

        window._bind_theme(widget, fg_color='card', text_color='accent')

        self.assertEqual(
            window._theme_bindings,
            [(widget, {'fg_color': 'card', 'text_color': 'accent'})],
        )

    def test_apply_theme_resolves_every_binding(self):
        window, root, _, _, _ = self.make_window()
        widget = FakeWidget()
        window._bind_theme(
            widget,
            fg_color='card',
            hover_color='card_hover',
            text_color='text',
        )

        window._apply_theme()

        self.assertEqual(root.options, {'fg_color': COLORS['bg']})
        self.assertEqual(
            widget.options,
            {
                'fg_color': COLORS['card'],
                'hover_color': COLORS['card_hover'],
                'text_color': COLORS['text'],
            },
        )

    def test_apply_theme_uses_new_colors_on_next_change(self):
        window, _, _, _, _ = self.make_window()
        widget = FakeWidget()
        window._bind_theme(widget, fg_color='card')
        window._apply_theme()

        window.COLORS = {**COLORS, 'card': '#abcdef'}
        window._apply_theme()

        self.assertEqual(widget.options, {'fg_color': '#abcdef'})

    def test_apply_theme_does_nothing_before_ui_is_ready(self):
        window, root, _, _, calls = self.make_window()
        widget = FakeWidget()
        window._bind_theme(widget, fg_color='card')
        window._ui_ready = False

        window._apply_theme()

        self.assertEqual(root.options, {})
        self.assertEqual(widget.options, {})
        self.assertEqual(calls, [])

    def test_apply_theme_refreshes_dynamic_state_after_bindings(self):
        window, _, textbox, search, calls = self.make_window()
        window._is_running = True
        window._luker_state = LukerState.READY
        window._bind_theme(FakeWidget(), fg_color='card')

        window._apply_theme()

        self.assertEqual(calls, ['blur', 'icons', 'status:ready'])
        self.assertEqual(search.refresh_count, 1)
        self.assertEqual(textbox.tags['error']['foreground'], COLORS['error'])
        self.assertEqual(textbox.tags['separator']['foreground'], COLORS['accent'])

    def test_apply_theme_refreshes_theme_art_after_bindings(self):
        window, _, _, _, calls = self.make_window()
        window._is_running = True
        window._luker_state = LukerState.READY
        window._apply_theme_art = lambda: calls.append('art')

        window._apply_theme()

        self.assertEqual(calls, ['blur', 'art', 'icons', 'status:ready'])

    def test_apply_theme_reapplies_button_roles(self):
        window, _, _, _, _ = self.make_window()
        primary = FakeWidget()
        secondary = FakeWidget()
        window._styled_buttons = [(primary, 'primary'), (secondary, 'secondary')]

        window._apply_theme()

        self.assertEqual(primary.options, button_colors('primary', COLORS))
        self.assertEqual(secondary.options, button_colors('secondary', COLORS))

    def test_apply_theme_logs_widget_failures(self):
        window, _, _, _, _ = self.make_window()
        window._bind_theme(BrokenWidget(), fg_color='card')

        with self.assertLogs('luker_launcher.ui.log_window', level='ERROR'):
            window._apply_theme()

    def test_blur_change_reruns_setup(self):
        window = object.__new__(LogWindow)
        calls = []
        window._setup_blur = lambda: calls.append('blur')

        window._on_blur_change(False)

        self.assertEqual(calls, ['blur'])


if __name__ == '__main__':
    unittest.main()
