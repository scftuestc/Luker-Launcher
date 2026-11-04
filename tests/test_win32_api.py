import unittest
from ctypes import wintypes

import win32_api


class NativeBindingTests(unittest.TestCase):
    def test_handle_arguments_are_declared(self):
        self.assertIs(win32_api.user32.GetParent.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.GetWindowLongW.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.SetWindowLongW.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.GetWindowThreadProcessId.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.SetForegroundWindow.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.IsWindow.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.IsWindowVisible.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.IsIconic.argtypes[0], wintypes.HWND)
        self.assertIs(win32_api.user32.ShowWindow.argtypes[0], wintypes.HWND)

    def test_handle_return_types_are_pointer_sized(self):
        self.assertIs(win32_api.user32.GetParent.restype, wintypes.HWND)
        self.assertIs(win32_api.user32.GetForegroundWindow.restype, wintypes.HWND)
        self.assertIs(win32_api.user32.GetWindowLongW.restype, wintypes.LONG)
        self.assertIs(win32_api.user32.SetWindowLongW.restype, wintypes.LONG)
        self.assertIs(win32_api.user32.GetAsyncKeyState.restype, wintypes.SHORT)
        self.assertIs(win32_api.user32.SetForegroundWindow.restype, wintypes.BOOL)
        self.assertIs(win32_api.user32.IsWindow.restype, wintypes.BOOL)
        self.assertIs(win32_api.user32.IsIconic.restype, wintypes.BOOL)
        self.assertIs(win32_api.user32.ShowWindow.restype, wintypes.BOOL)
        self.assertIs(win32_api.kernel32.GetCurrentThreadId.restype, wintypes.DWORD)

    def test_thread_attach_uses_dword_thread_ids(self):
        self.assertEqual(
            win32_api.user32.AttachThreadInput.argtypes,
            [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL],
        )
        self.assertIs(win32_api.user32.AttachThreadInput.restype, wintypes.BOOL)


if __name__ == '__main__':
    unittest.main()
