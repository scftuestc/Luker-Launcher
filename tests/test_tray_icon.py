import unittest
from ctypes import wintypes
from threading import Event
from unittest.mock import Mock, patch

from PIL import Image

import tray.icon as tray_icon
from tray.icon import TrayIcon


def make_tray(hicon: int | None = 111) -> TrayIcon:
    tray = object.__new__(TrayIcon)
    tray._hicon = hicon
    nid = tray_icon.NOTIFYICONDATA()
    nid.hIcon = hicon or 0
    tray._nid = nid
    tray._hwnd = 1
    tray._running = True
    tray._is_running = False
    tray._icon_added = False
    return tray


class NativeBindingTests(unittest.TestCase):
    def test_handle_return_types_are_pointer_sized(self):
        self.assertIs(tray_icon._user32.GetDC.restype, wintypes.HDC)
        self.assertIs(tray_icon._user32.CreateIconIndirect.restype, wintypes.HICON)
        self.assertIs(tray_icon._gdi32.CreateCompatibleBitmap.restype, wintypes.HBITMAP)
        self.assertIs(tray_icon._gdi32.CreateBitmap.restype, wintypes.HBITMAP)
        self.assertIs(tray_icon._kernel32.GetModuleHandleW.restype, wintypes.HMODULE)


class ImageToHiconTests(unittest.TestCase):
    def setUp(self):
        self.user32 = Mock()
        self.gdi32 = Mock()
        self.user32.GetDC.return_value = 100
        self.user32.CreateIconIndirect.return_value = 300
        self.gdi32.CreateCompatibleBitmap.return_value = 200
        self.gdi32.SetDIBits.return_value = 1
        self.gdi32.CreateBitmap.return_value = 201
        self.gdi32.DeleteObject.return_value = 1
        self.user32.ReleaseDC.return_value = 1
        self.patches = [
            patch.object(tray_icon, "_user32", self.user32),
            patch.object(tray_icon, "_gdi32", self.gdi32),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _convert(self):
        tray = object.__new__(TrayIcon)
        return tray._image_to_hicon(Image.new("RGBA", (32, 32)), 32)

    def test_missing_screen_dc_returns_none(self):
        self.user32.GetDC.return_value = 0

        self.assertIsNone(self._convert())
        self.gdi32.CreateCompatibleBitmap.assert_not_called()
        self.user32.ReleaseDC.assert_not_called()

    def test_missing_color_bitmap_releases_dc(self):
        self.gdi32.CreateCompatibleBitmap.return_value = 0

        self.assertIsNone(self._convert())
        self.user32.ReleaseDC.assert_called_once_with(None, 100)
        self.gdi32.DeleteObject.assert_not_called()

    def test_failed_dib_upload_releases_bitmap_and_dc(self):
        self.gdi32.SetDIBits.return_value = 0

        self.assertIsNone(self._convert())
        self.gdi32.DeleteObject.assert_called_once_with(200)
        self.user32.ReleaseDC.assert_called_once_with(None, 100)

    def test_missing_mask_bitmap_releases_color_and_dc(self):
        self.gdi32.CreateBitmap.return_value = 0

        self.assertIsNone(self._convert())
        self.gdi32.DeleteObject.assert_called_once_with(200)
        self.user32.ReleaseDC.assert_called_once_with(None, 100)

    def test_missing_icon_releases_both_bitmaps_and_dc(self):
        self.user32.CreateIconIndirect.return_value = 0

        self.assertIsNone(self._convert())
        self.gdi32.DeleteObject.assert_any_call(200)
        self.gdi32.DeleteObject.assert_any_call(201)
        self.user32.ReleaseDC.assert_called_once_with(None, 100)

    def test_success_returns_icon_and_releases_intermediates(self):
        self.assertEqual(self._convert(), 300)
        self.gdi32.DeleteObject.assert_any_call(200)
        self.gdi32.DeleteObject.assert_any_call(201)
        self.user32.ReleaseDC.assert_called_once_with(None, 100)


class TrayRunTests(unittest.TestCase):
    def test_initial_icon_failure_exits_without_adding_icon(self):
        tray = object.__new__(TrayIcon)
        tray._running = False
        tray._ready = Event()
        tray._hwnd = None
        tray._nid = None
        tray._hicon = None
        tray._icon_added = False
        tray._is_running = False
        user32 = Mock()
        user32.RegisterClassW.return_value = 1
        user32.CreateWindowExW.return_value = 99
        kernel32 = Mock()
        kernel32.GetModuleHandleW.return_value = 1

        with (
            patch.object(tray_icon, "_user32", user32),
            patch.object(tray_icon, "_kernel32", kernel32),
            patch.object(tray, "_get_icon_size", return_value=32),
            patch.object(tray, "_image_to_hicon", return_value=None),
            patch.object(tray, "_add_icon") as add_icon,
        ):
            tray.run()

        add_icon.assert_not_called()
        self.assertFalse(tray._running)
        self.assertIsNone(tray._hwnd)
        user32.DestroyWindow.assert_called_once_with(99)
        user32.UnregisterClassW.assert_called_once_with(tray_icon.TRAY_CLASS_NAME, 1)


class TrayStopTests(unittest.TestCase):
    def setUp(self):
        self.user32 = Mock()
        self.user32.DestroyIcon.return_value = 1
        self.user32.PostMessageW.return_value = 1
        self.user32.PostThreadMessageW.return_value = 1
        self.patcher = patch.object(tray_icon, "_user32", self.user32)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _tray_with_thread(self):
        tray = object.__new__(TrayIcon)
        tray._hwnd = 1
        tray._running = True
        tray._thread_id = 42
        tray._thread = Mock()
        tray._thread.is_alive.side_effect = [True, False]
        return tray

    def test_post_message_success_clears_thread_state(self):
        tray = self._tray_with_thread()

        tray.stop()

        self.user32.PostMessageW.assert_called_once_with(1, tray_icon.WM_CLOSE, 0, 0)
        self.user32.PostThreadMessageW.assert_not_called()
        self.assertIsNone(tray._thread)
        self.assertIsNone(tray._thread_id)

    def test_post_failure_falls_back_to_thread_message(self):
        tray = self._tray_with_thread()
        self.user32.PostMessageW.return_value = 0

        tray.stop()

        self.user32.PostThreadMessageW.assert_called_once_with(42, tray_icon.WM_QUIT, 0, 0)
        self.assertFalse(tray._running)
        self.assertIsNone(tray._thread)
        self.assertIsNone(tray._thread_id)

    def test_thread_that_stays_alive_is_kept_for_retry(self):
        tray = self._tray_with_thread()
        tray._thread.is_alive.side_effect = None
        tray._thread.is_alive.return_value = True
        self.user32.PostMessageW.return_value = 0
        self.user32.PostThreadMessageW.return_value = 0

        tray.stop()

        self.assertFalse(tray._running)
        self.assertIsNotNone(tray._thread)
        self.assertEqual(tray._thread_id, 42)


class UpdateIconTests(unittest.TestCase):
    def setUp(self):
        self.shell32 = Mock()
        self.user32 = Mock()
        self.shell32.Shell_NotifyIconW.return_value = 1
        self.user32.DestroyIcon.return_value = 1
        self.patches = [
            patch.object(tray_icon, "_shell32", self.shell32),
            patch.object(tray_icon, "_user32", self.user32),
            patch.object(TrayIcon, "_get_icon_size", return_value=32),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_missing_new_icon_keeps_old_icon(self):
        tray = make_tray()
        with patch.object(tray, "_image_to_hicon", return_value=None):
            tray._update_icon()

        self.assertEqual(tray._hicon, 111)
        self.assertEqual(tray._nid.hIcon, 111)
        self.shell32.Shell_NotifyIconW.assert_not_called()
        self.user32.DestroyIcon.assert_not_called()

    def test_modify_failure_keeps_old_icon_and_releases_new_icon(self):
        tray = make_tray()
        self.shell32.Shell_NotifyIconW.return_value = 0
        with patch.object(tray, "_image_to_hicon", return_value=222):
            tray._update_icon()

        self.assertEqual(tray._hicon, 111)
        self.assertEqual(tray._nid.hIcon, 111)
        self.user32.DestroyIcon.assert_called_once_with(222)
        self.assertNotIn(111, [call.args[0] for call in self.user32.DestroyIcon.call_args_list])

    def test_modify_success_swaps_icon_and_releases_old_icon(self):
        tray = make_tray()
        with patch.object(tray, "_image_to_hicon", return_value=222):
            tray._update_icon()

        self.assertEqual(tray._hicon, 222)
        self.assertEqual(tray._nid.hIcon, 222)
        self.user32.DestroyIcon.assert_called_once_with(111)


if __name__ == "__main__":
    unittest.main()
