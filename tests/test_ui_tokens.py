import unittest

import dialogs
import log.search
import settings_window
import ui.buttons
import ui.icons
import ui.resizing
import ui.switch
import ui.tokens
from luker_launcher.tray import menu


class TokenValueTests(unittest.TestCase):
    def test_spacing_scale_and_semantic_aliases(self):
        self.assertEqual(ui.tokens.SPACE_12, 12)
        self.assertEqual(ui.tokens.PAD_WINDOW, 12)
        self.assertEqual(ui.tokens.PAD_CARD, 16)
        self.assertEqual(ui.tokens.GAP_SECTION, 12)
        self.assertEqual(ui.tokens.GAP_SECTION_HEADER, 12)
        self.assertEqual(ui.tokens.GAP_WINDOW, 10)

    def test_radii_and_typography(self):
        self.assertEqual(ui.tokens.RADIUS_CARD, 10)
        self.assertEqual(ui.tokens.RADIUS_CARD_LG, 14)
        self.assertEqual(ui.tokens.RADIUS_BUTTON, 12)
        self.assertEqual(ui.tokens.FONT_BODY, 13)
        self.assertEqual(ui.tokens.FONT_TITLE, 16)
        self.assertEqual(ui.tokens.FONT_MENU_TITLE, 18)

    def test_window_and_control_sizes(self):
        self.assertEqual(ui.tokens.WINDOW_MAIN_WIDTH, 960)
        self.assertEqual(ui.tokens.WINDOW_MAIN_MIN_WIDTH, 700)
        self.assertEqual(ui.tokens.WINDOW_SETTINGS_WIDTH, 600)
        self.assertEqual(ui.tokens.WINDOW_DIALOG_WIDTH, 480)
        self.assertEqual(ui.tokens.CONTROL_HEIGHT_XL, 40)
        self.assertEqual(ui.tokens.SWITCH_WIDTH, 44)


class LegacyConstantTests(unittest.TestCase):
    def test_legacy_constants_still_importable(self):
        self.assertEqual(ui.buttons.BUTTON_RADIUS['primary'], 12)
        self.assertEqual(ui.buttons.BUTTON_HEIGHT['primary'], 40)
        self.assertEqual(ui.switch.SWITCH_WIDTH, 44)
        self.assertEqual(ui.switch.SWITCH_ANIMATION_STEPS, 6)
        self.assertEqual(ui.resizing.DEFAULT_WIDTH, 960)
        self.assertEqual(ui.resizing.MIN_HEIGHT, 450)
        self.assertEqual(dialogs.DIALOG_WIDTH, 480)
        self.assertEqual(settings_window.SETTINGS_WIDTH, 600)
        self.assertEqual(menu.MENU_WIDTH, 240)
        self.assertEqual(log.search.COUNT_LABEL_WIDTH, 64)

    def test_icon_defaults_use_tokens(self):
        self.assertEqual(ui.icons.ICON_RENDER, 64)
        self.assertEqual(ui.icons.ICON_TOOLBAR, 16)
        self.assertEqual(ui.icons.ICON_MENU, 18)

    def test_brand_colors_are_shared(self):
        from luker_launcher.theme import LOGO_STOPPED_COLOR, TRAY_ACTIVE_COLOR, TRAY_ICON_BG

        self.assertEqual(LOGO_STOPPED_COLOR, '#6e7681')
        self.assertEqual(TRAY_ACTIVE_COLOR, '#3fb950')
        self.assertEqual(TRAY_ICON_BG, '#161b22')


if __name__ == '__main__':
    unittest.main()
