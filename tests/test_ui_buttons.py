import unittest

from ui.buttons import button_colors
from ui.theme import PRESET_THEMES, get_theme_colors, mix_color, shade_color


class ButtonColorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.colors = get_theme_colors('summer')

    def test_primary_uses_accent_fill(self):
        self.assertEqual(
            button_colors('primary', self.colors),
            {
                'fg_color': self.colors['accent'],
                'hover_color': shade_color(self.colors['accent'], 0.85),
                'text_color': self.colors['on_accent'],
                'border_width': 0,
            },
        )

    def test_secondary_uses_card_fill_and_border(self):
        self.assertEqual(
            button_colors('secondary', self.colors),
            {
                'fg_color': self.colors['card'],
                'hover_color': self.colors['card_hover'],
                'text_color': self.colors['text'],
                'text_color_disabled': self.colors['text_dim'],
                'border_width': 1,
                'border_color': self.colors['border'],
            },
        )

    def test_outline_is_unfilled_with_readable_disabled_text(self):
        self.assertEqual(
            button_colors('outline', self.colors),
            {
                'fg_color': 'transparent',
                'hover_color': mix_color(self.colors['card'], self.colors['accent'], 0.12),
                'text_color': self.colors['accent'],
                'text_color_disabled': self.colors['text_dim'],
                'border_width': 1,
                'border_color': self.colors['border'],
            },
        )

    def test_danger_outline_is_quiet_until_hover(self):
        self.assertEqual(
            button_colors('danger_outline', self.colors),
            {
                'fg_color': 'transparent',
                'hover_color': mix_color(self.colors['card'], self.colors['error'], 0.14),
                'text_color': self.colors['text'],
                'text_color_disabled': self.colors['text_dim'],
                'border_width': 1,
                'border_color': self.colors['border'],
            },
        )

    def test_ghost_is_transparent(self):
        self.assertEqual(
            button_colors('ghost', self.colors),
            {
                'fg_color': 'transparent',
                'hover_color': self.colors['card_hover'],
                'text_color': self.colors['text_dim'],
                'text_color_disabled': self.colors['text_muted'],
                'border_width': 0,
            },
        )

    def test_danger_ghost_uses_soft_red_hover(self):
        self.assertEqual(
            button_colors('danger_ghost', self.colors),
            {
                'fg_color': 'transparent',
                'hover_color': mix_color(self.colors['card'], self.colors['error'], 0.18),
                'text_color': self.colors['text_dim'],
                'text_color_disabled': self.colors['text_muted'],
                'border_width': 0,
            },
        )

    def test_danger_uses_error_fill(self):
        self.assertEqual(
            button_colors('danger', self.colors),
            {
                'fg_color': self.colors['error'],
                'hover_color': shade_color(self.colors['error'], 0.85),
                'text_color': self.colors['bg'],
                'border_width': 0,
            },
        )

    def test_menu_uses_body_text(self):
        self.assertEqual(
            button_colors('menu', self.colors),
            {
                'fg_color': 'transparent',
                'hover_color': self.colors['card_hover'],
                'text_color': self.colors['text'],
                'border_width': 0,
            },
        )

    def test_every_theme_has_visible_fill_and_hover(self):
        for name in PRESET_THEMES:
            with self.subTest(theme=name):
                colors = get_theme_colors(name)
                self.assertNotEqual(
                    button_colors('primary', colors)['fg_color'],
                    button_colors('primary', colors)['hover_color'],
                )
                self.assertNotEqual(
                    button_colors('secondary', colors)['fg_color'],
                    button_colors('secondary', colors)['hover_color'],
                )


if __name__ == '__main__':
    unittest.main()
