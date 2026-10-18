from PIL import Image, ImageDraw
from typing import Callable, Optional
from threading import Thread
import ctypes
from ctypes import wintypes, windll, byref, sizeof, Structure, c_int, WINFUNCTYPE
import time


WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002
WM_QUIT = 0x0012

NIM_ADD = 0x00
NIM_MODIFY = 0x01
NIM_DELETE = 0x02

NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04

WNDPROC = WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class NOTIFYICONDATA(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
    ]


class WNDCLASSW(Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class MSG(Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class TrayIcon:
    def __init__(
        self,
        on_show_window: Callable[[], None],
        on_hide_window: Callable[[], None],
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_restart: Callable[[], None],
        on_exit: Callable[[], None],
        on_settings: Optional[Callable[[], None]] = None,
        on_show_menu: Optional[Callable[[int, int], None]] = None,
    ):
        self.on_show_window = on_show_window
        self.on_hide_window = on_hide_window
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_restart = on_restart
        self.on_exit = on_exit
        self.on_settings = on_settings
        self.on_show_menu = on_show_menu

        self._window_visible = False
        self._is_running = False
        self._thread: Optional[Thread] = None
        self._hwnd = None
        self._running = False
        self._hicon = None
        self._nid = None

        self._wndproc_ref = None

    def _create_icon_image(self) -> Image.Image:
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        scale = size / 256

        margin = max(1, int(8 * scale))
        corner_radius = max(2, int(48 * scale))

        def draw_rounded_rect(coords, radius, fill):
            x1, y1, x2, y2 = coords
            if radius * 2 > min(x2-x1, y2-y1):
                radius = min(x2-x1, y2-y1) // 2
            if radius < 1:
                radius = 1
            draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
            draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)
            draw.ellipse([x1, y1, x1+radius*2, y1+radius*2], fill=fill)
            draw.ellipse([x2-radius*2, y1, x2, y1+radius*2], fill=fill)
            draw.ellipse([x1, y2-radius*2, x1+radius*2, y2], fill=fill)
            draw.ellipse([x2-radius*2, y2-radius*2, x2, y2], fill=fill)

        if self._is_running:
            border_color = '#3fb950'
        else:
            border_color = '#6e7681'

        draw_rounded_rect([margin, margin, size-margin, size-margin], corner_radius, border_color)

        inner_margin = margin + max(1, int(4 * scale))
        inner_radius = max(1, corner_radius - int(4*scale))
        draw_rounded_rect([inner_margin, inner_margin, size-inner_margin, size-inner_margin],
                         inner_radius, '#161b22')

        bar_width = max(2, int(16 * scale))
        bar_height = max(8, int(80 * scale))
        bar_gap = max(1, int(8 * scale))
        total_width = bar_width * 4 + bar_gap * 3
        start_x = (size - total_width) // 2
        start_y = (size - bar_height) // 2

        if self._is_running:
            colors = ['#ff6b6b', '#feca57', '#48dbfb', '#1dd1a1']
        else:
            colors = ['#6e7681', '#6e7681', '#6e7681', '#6e7681']

        for i, color in enumerate(colors):
            x = start_x + i * (bar_width + bar_gap)
            y = start_y

            if bar_width >= 4:
                draw.ellipse([x, y, x + bar_width, y + bar_width], fill=color)
                draw.rectangle([x, y + bar_width//2, x + bar_width, y + bar_height - bar_width//2], fill=color)
                draw.ellipse([x, y + bar_height - bar_width, x + bar_width, y + bar_height], fill=color)
            else:
                draw.rectangle([x, y, x + bar_width, y + bar_height], fill=color)

        return image

    def _image_to_hicon(self, image: Image.Image) -> wintypes.HICON:
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        image = image.resize((32, 32), Image.LANCZOS)

        width, height = image.size
        pixels = image.tobytes()

        class BITMAPINFOHEADER(Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        class BITMAPINFO(Structure):
            _fields_ = [
                ("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3),
            ]

        hdc = windll.user32.GetDC(0)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        hbmColor = windll.gdi32.CreateCompatibleBitmap(hdc, width, height)

        bgra_pixels = bytearray(len(pixels))
        for i in range(0, len(pixels), 4):
            bgra_pixels[i] = pixels[i + 2]
            bgra_pixels[i + 1] = pixels[i + 1]
            bgra_pixels[i + 2] = pixels[i]
            bgra_pixels[i + 3] = pixels[i + 3]

        windll.gdi32.SetDIBits(hdc, hbmColor, 0, height, bytes(bgra_pixels), byref(bmi), 0)

        hbmMask = windll.gdi32.CreateBitmap(width, height, 1, 1, None)

        class ICONINFO(Structure):
            _fields_ = [
                ("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP),
                ("hbmColor", wintypes.HBITMAP),
            ]

        iconinfo = ICONINFO()
        iconinfo.fIcon = True
        iconinfo.xHotspot = 0
        iconinfo.yHotspot = 0
        iconinfo.hbmMask = hbmMask
        iconinfo.hbmColor = hbmColor

        hicon = windll.user32.CreateIconIndirect(byref(iconinfo))

        windll.gdi32.DeleteObject(hbmColor)
        windll.gdi32.DeleteObject(hbmMask)
        windll.user32.ReleaseDC(0, hdc)

        return hicon

    def _get_cursor_pos(self) -> tuple:
        """获取鼠标位置，处理 DPI 缩放"""
        pt = wintypes.POINT()
        windll.user32.GetCursorPos(byref(pt))

        # 获取主显示器的 DPI 缩放比例
        try:
            # 获取屏幕 DC
            hdc = windll.user32.GetDC(0)
            # LOGPIXELSX = 88，标准 DPI 是 96
            dpi = windll.gdi32.GetDeviceCaps(hdc, 88)
            windll.user32.ReleaseDC(0, hdc)

            # 计算缩放比例
            scale = dpi / 96.0

            # 将物理像素坐标转换为逻辑像素坐标
            # customtkinter 使用的是逻辑像素
            logical_x = int(pt.x / scale)
            logical_y = int(pt.y / scale)

            return (logical_x, logical_y)
        except Exception as e:
            print(f"获取 DPI 缩放失败: {e}")
            return (pt.x, pt.y)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAYICON:
                if lparam == WM_LBUTTONUP:
                    self._toggle_window()
                elif lparam == WM_RBUTTONUP:
                    if self.on_show_menu:
                        x, y = self._get_cursor_pos()
                        self.on_show_menu(x, y)
            elif msg == WM_DESTROY:
                windll.user32.PostQuitMessage(0)
                return 0
        except Exception as e:
            print(f"托盘消息处理错误: {e}")

        return windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _toggle_window(self) -> None:
        if self._window_visible:
            self.on_hide_window()
            self._window_visible = False
        else:
            self.on_show_window()
            self._window_visible = True

    def _update_icon(self) -> None:
        if self._hwnd and self._nid:
            if self._hicon:
                windll.user32.DestroyIcon(self._hicon)

            self._hicon = self._image_to_hicon(self._create_icon_image())
            self._nid.hIcon = self._hicon

            windll.shell32.Shell_NotifyIconW(NIM_MODIFY, byref(self._nid))

    def update_status(self, is_running: bool) -> None:
        if is_running == self._is_running and self._hicon is not None:
            return
        self._is_running = is_running
        self._update_icon()

    def set_window_visible(self, visible: bool) -> None:
        self._window_visible = visible

    def run(self) -> None:
        self._running = True

        hinstance = windll.kernel32.GetModuleHandleW(None)

        self._wndproc_ref = WNDPROC(self._wnd_proc)

        class_name = "LukerTrayClass"
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._wndproc_ref
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinstance
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = class_name

        atom = windll.user32.RegisterClassW(byref(wc))
        if not atom:
            print(f"注册窗口类失败: {ctypes.get_last_error()}")
            return

        self._hwnd = windll.user32.CreateWindowExW(
            0,
            class_name,
            "Luker Tray",
            0,
            0, 0, 0, 0,
            None,
            None,
            hinstance,
            None
        )

        if not self._hwnd:
            print(f"创建窗口失败: {ctypes.get_last_error()}")
            return

        self._hicon = self._image_to_hicon(self._create_icon_image())

        self._nid = NOTIFYICONDATA()
        self._nid.cbSize = sizeof(NOTIFYICONDATA)
        self._nid.hWnd = self._hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.hIcon = self._hicon
        self._nid.szTip = "Luker 启动器"

        result = windll.shell32.Shell_NotifyIconW(NIM_ADD, byref(self._nid))
        if not result:
            print(f"添加托盘图标失败: {ctypes.get_last_error()}")

        msg = MSG()
        while self._running:
            ret = windll.user32.GetMessageW(byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            windll.user32.TranslateMessage(byref(msg))
            windll.user32.DispatchMessageW(byref(msg))

    def run_detached(self) -> None:
        self._thread = Thread(target=self.run, daemon=True)
        self._thread.start()
        time.sleep(0.1)

    def stop(self) -> None:
        self._running = False

        if self._nid and self._hwnd:
            windll.shell32.Shell_NotifyIconW(NIM_DELETE, byref(self._nid))

        if self._hicon:
            windll.user32.DestroyIcon(self._hicon)
            self._hicon = None

        if self._hwnd:
            windll.user32.DestroyWindow(self._hwnd)
            self._hwnd = None
