import unittest
from types import SimpleNamespace
from unittest.mock import patch

import dialogs
from core.readiness import LukerState
from dialogs import (
    DIALOG_HEIGHT,
    DIALOG_WIDTH,
    CloseChoiceDialog,
    close_dialog_message,
    dialog_position,
    select_luker_path,
)
from ui.dpi import format_geometry


class DialogPositionTests(unittest.TestCase):
    def test_centers_dialog_on_parent(self):
        self.assertEqual(
            dialog_position(100, 200, 900, 600, DIALOG_WIDTH, DIALOG_HEIGHT),
            (310, 300),
        )

    def test_keeps_negative_secondary_monitor_coordinates(self):
        x, y = dialog_position(-1920, 0, 900, 900, DIALOG_WIDTH, DIALOG_HEIGHT)

        self.assertEqual((x, y), (-1710, 200))
        self.assertEqual(
            format_geometry(DIALOG_WIDTH, DIALOG_HEIGHT, x, y),
            "480x300+-1710+200",
        )


class CloseDialogMessageTests(unittest.TestCase):
    def test_without_tray_only_explains_exit(self):
        self.assertEqual(
            close_dialog_message(LukerState.READY, allow_hide=False),
            "系统托盘不可用。\n关闭窗口将退出 Luker Launcher。",
        )

    def test_stopped_state_asks_hide_or_exit(self):
        self.assertEqual(
            close_dialog_message(LukerState.STOPPED, allow_hide=True),
            "Luker 当前未运行。\n关闭窗口后要隐藏到系统托盘，还是退出 Luker Launcher？",
        )

    def test_running_state_explains_consequences(self):
        message = close_dialog_message(LukerState.READY, allow_hide=True)

        self.assertIn("Luker 正在运行。", message)
        self.assertIn("隐藏到托盘会保持 Luker 继续运行", message)
        self.assertIn("退出程序会停止 Luker", message)


class CloseChoiceDialogTests(unittest.TestCase):
    def make_dialog(self, remember: int = 1):
        dialog = object.__new__(CloseChoiceDialog)
        dialog._closed = False
        dialog._remember_var = SimpleNamespace(get=lambda: remember)
        calls: list[object] = []
        dialog._close_window = lambda: calls.append('close')
        dialog._on_hide = lambda remember: calls.append(('hide', remember))
        dialog._on_exit = lambda remember: calls.append(('exit', remember))
        dialog._on_cancel = lambda: calls.append('cancel')
        return dialog, calls

    def test_hide_closes_before_callback_and_passes_remember(self):
        dialog, calls = self.make_dialog(remember=1)

        dialog._hide()

        self.assertEqual(calls, ['close', ('hide', True)])

    def test_exit_closes_before_callback_and_passes_remember(self):
        dialog, calls = self.make_dialog(remember=1)

        dialog._exit()

        self.assertEqual(calls, ['close', ('exit', True)])

    def test_hide_without_remember_passes_false(self):
        dialog, calls = self.make_dialog(remember=0)

        dialog._hide()

        self.assertEqual(calls, ['close', ('hide', False)])

    def test_cancel_does_not_pass_remember(self):
        dialog, calls = self.make_dialog(remember=1)

        dialog._cancel()

        self.assertEqual(calls, ['close', 'cancel'])

    def test_second_action_is_ignored(self):
        dialog, calls = self.make_dialog(remember=1)

        dialog._hide()
        dialog._exit()
        dialog._cancel()

        self.assertEqual(calls, ['close', ('hide', True)])


class SelectLukerPathTests(unittest.TestCase):
    def test_uses_root_directory_wording_and_saves_valid_path(self):
        owner = object()
        fake_config = SimpleNamespace(is_valid_luker_path=lambda _path: True, luker_path=None)

        with (
            patch.object(dialogs, 'config', fake_config),
            patch.object(dialogs, '_dialog_owner', lambda _parent: (owner, None)),
            patch.object(dialogs.messagebox, 'showinfo') as showinfo,
            patch.object(dialogs.messagebox, 'showerror') as showerror,
            patch.object(dialogs.filedialog, 'askdirectory', return_value='C:/Luker') as ask,
        ):
            result = select_luker_path(object())

        self.assertEqual(result, 'C:/Luker')
        self.assertEqual(fake_config.luker_path, 'C:/Luker')
        showinfo.assert_called_once_with(
            'Luker 启动器',
            '请选择 Luker 的安装根目录\n该目录应包含 Start.bat 和 server.js。',
            parent=owner,
        )
        ask.assert_called_once_with(title='选择 Luker 安装根目录', parent=owner)
        showerror.assert_not_called()

    def test_invalid_path_shows_root_directory_error(self):
        owner = object()
        fake_config = SimpleNamespace(is_valid_luker_path=lambda _path: False, luker_path=None)

        with (
            patch.object(dialogs, 'config', fake_config),
            patch.object(dialogs, '_dialog_owner', lambda _parent: (owner, None)),
            patch.object(dialogs.messagebox, 'showinfo'),
            patch.object(dialogs.messagebox, 'showerror') as showerror,
            patch.object(dialogs.filedialog, 'askdirectory', return_value='C:/NotLuker'),
        ):
            result = select_luker_path(object())

        self.assertIsNone(result)
        self.assertIsNone(fake_config.luker_path)
        self.assertIn('安装根目录', showerror.call_args.args[1])

    def test_cancelled_dialog_does_not_write_config(self):
        fake_config = SimpleNamespace(is_valid_luker_path=lambda _path: True, luker_path=None)

        with (
            patch.object(dialogs, 'config', fake_config),
            patch.object(dialogs, '_dialog_owner', lambda _parent: (object(), None)),
            patch.object(dialogs.messagebox, 'showinfo'),
            patch.object(dialogs.messagebox, 'showerror') as showerror,
            patch.object(dialogs.filedialog, 'askdirectory', return_value=''),
        ):
            result = select_luker_path(object())

        self.assertIsNone(result)
        self.assertIsNone(fake_config.luker_path)
        showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
