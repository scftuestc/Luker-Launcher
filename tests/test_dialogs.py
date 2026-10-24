import unittest

from dialogs import DIALOG_HEIGHT, DIALOG_WIDTH, dialog_position
from dpi import format_geometry


class DialogPositionTests(unittest.TestCase):
    def test_centers_dialog_on_parent(self):
        self.assertEqual(
            dialog_position(100, 200, 900, 600, DIALOG_WIDTH, DIALOG_HEIGHT),
            (330, 323),
        )

    def test_keeps_negative_secondary_monitor_coordinates(self):
        x, y = dialog_position(-1920, 0, 900, 900, DIALOG_WIDTH, DIALOG_HEIGHT)

        self.assertEqual((x, y), (-1690, 223))
        self.assertEqual(
            format_geometry(DIALOG_WIDTH, DIALOG_HEIGHT, x, y),
            "440x230+-1690+223",
        )


if __name__ == "__main__":
    unittest.main()
