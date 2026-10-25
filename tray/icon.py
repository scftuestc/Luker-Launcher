"""基于 Win32 Shell_NotifyIcon 的系统托盘图标。"""

import ctypes
import logging
from collections.abc import Callable, Sequence
from ctypes import WINFUNCTYPE, Structure, byref, c_int, sizeof, windll, wintypes
from threading import Event, Lock, Thread, current_thread

from PIL import Image, ImageDraw

from ui.theme import LOGO_BAR_COLORS

logger = logging.getLogger(__name__)

WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
WM_TRAY_STATUS = WM_USER + 2
WM_CLOSE = 0x0010
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002
CS_DBLCLKS = 0x0008

NIM_ADD = 0x00
NIM_MODIFY = 0x01
NIM_DELETE = 0x02

NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04
SM_CXICON = 11

WNDPROC = WINFUNCTYPE(
    wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class NOTIFYICONDATA(Structure):
    # 只声明实际使用的 v1 字段：图标、回调消息和提示文本
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


# 显式声明 64 位参数/返回值类型，避免 ctypes 默认按 32 位 int 转换
_user32 = windll.user32
_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.DefWindowProcW.restype = wintypes.LPARAM
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
_user32.RegisterClassW.restype = wintypes.WORD
_user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.GetMessageW.restype = c_int
_user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
_user32.DispatchMessageW.restype = wintypes.LPARAM
_user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.PostMessageW.restype = wintypes.BOOL
_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.DestroyWindow.restype = wintypes.BOOL
_user32.PostQuitMessage.argtypes = [c_int]
_user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
_user32.RegisterWindowMessageW.restype = wintypes.UINT


class TrayIcon:
    """系统托盘图标；Win32 消息循环和所有图标/窗口操作都跑在托盘线程中。"""

    def __init__(
        self,
        on_show_window: Callable[[], None],
        on_hide_window: Callable[[], None],
        on_show_menu: Callable[[int, int], None] | None = None,
    ) -> None:
        self.on_show_window = on_show_window
        self.on_hide_window = on_hide_window
        self.on_show_menu = on_show_menu

        self._window_visible = False
        self._is_running = False
        self._state_lock = Lock()
        self._thread: Thread | None = None
        self._hwnd: int | None = None
        self._running = False
        self._hicon: wintypes.HICON | None = None
        self._nid: NOTIFYICONDATA | None = None
        self._ready = Event()
        self._icon_added = False
        self._ignore_next_up = False
        # Explorer 重启后会广播 TaskbarCreated，需要据此重新添加图标
        self._taskbar_created_msg = _user32.RegisterWindowMessageW("TaskbarCreated")

        # WNDPROC 是 ctypes 运行时生成的函数类型，mypy 不把它当类型
        self._wndproc_ref: WNDPROC | None = None  # type: ignore[valid-type]

    def _create_icon_image(self) -> Image.Image:
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        scale = size / 256

        margin = max(1, int(8 * scale))
        corner_radius = max(2, int(48 * scale))

        def draw_rounded_rect(
            coords: Sequence[float], radius: int, fill: str | tuple[int, ...]
        ) -> None:
            x1, y1, x2, y2 = coords
            if radius * 2 > min(x2 - x1, y2 - y1):
                radius = int(min(x2 - x1, y2 - y1) // 2)
            if radius < 1:
                radius = 1
            draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
            draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
            draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
            draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)

        border_color = '#3fb950' if self._is_running else '#6e7681'

        draw_rounded_rect(
            [margin, margin, size - margin, size - margin], corner_radius, border_color
        )

        inner_margin = margin + max(1, int(4 * scale))
        inner_radius = max(1, corner_radius - int(4 * scale))
        draw_rounded_rect(
            [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
            inner_radius,
            '#161b22',
        )

        bar_width = max(2, int(16 * scale))
        bar_height = max(8, int(80 * scale))
        bar_gap = max(1, int(8 * scale))
        total_width = bar_width * 4 + bar_gap * 3
        start_x = (size - total_width) // 2
        start_y = (size - bar_height) // 2

        if self._is_running:
            colors: Sequence[str] = LOGO_BAR_COLORS
        else:
            colors = ['#6e7681', '#6e7681', '#6e7681', '#6e7681']

        for i, color in enumerate(colors):
            x = start_x + i * (bar_width + bar_gap)
            y = start_y

            if bar_width >= 4:
                draw.ellipse([x, y, x + bar_width, y + bar_width], fill=color)
                draw.rectangle(
                    [x, y + bar_width // 2, x + bar_width, y + bar_height - bar_width // 2],
                    fill=color,
                )
                draw.ellipse(
                    [x, y + bar_height - bar_width, x + bar_width, y + bar_height], fill=color
                )
            else:
                draw.rectangle([x, y, x + bar_width, y + bar_height], fill=color)

        return image

    def _get_icon_size(self) -> int:
        """按系统 DPI 返回托盘图标源尺寸，失败时回退到 32px。"""
        try:
            dpi = windll.user32.GetDpiForSystem()
            # 用大图标作为源，通知区域在高缩放下缩小时更清晰
            size = windll.user32.GetSystemMetricsForDpi(SM_CXICON, dpi)
            if size:
                # 源图按 64px 绘制，再大只会被缩小
                return max(32, min(64, int(size)))
        except (AttributeError, OSError):
            pass
        return 32

    def _image_to_hicon(self, image: Image.Image, size: int = 32) -> wintypes.HICON:
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        image = image.resize((size, size), Image.Resampling.LANCZOS)

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

    def _get_cursor_pos(self) -> tuple[int, int]:
        """返回光标的物理屏幕坐标；Tk 的窗口位置也使用物理像素。"""
        pt = wintypes.POINT()
        windll.user32.GetCursorPos(byref(pt))
        return pt.x, pt.y

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        try:
            if msg == WM_TRAYICON:
                # 左键单击切换日志窗口；双击只显示，并忽略随后重复的 UP
                if lparam == WM_LBUTTONUP:
                    if self._ignore_next_up:
                        self._ignore_next_up = False
                    else:
                        self._toggle_window()
                elif lparam == WM_LBUTTONDBLCLK:
                    self._ignore_next_up = True
                    self._show_window()
                elif lparam == WM_RBUTTONUP and self.on_show_menu:
                    x, y = self._get_cursor_pos()
                    self.on_show_menu(x, y)
            elif self._taskbar_created_msg and msg == self._taskbar_created_msg:
                # Explorer 重启后通知区域会丢失图标，需要重新注册
                self._add_icon()
            elif msg == WM_TRAY_STATUS:
                self._update_icon()
            elif msg == WM_CLOSE:
                self._remove_icon()
                windll.user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                self._hwnd = None
                windll.user32.PostQuitMessage(0)
                return 0
        except Exception:
            logger.exception("托盘消息处理失败")

        return windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_window(self) -> None:
        self.on_show_window()
        self._window_visible = True

    def _toggle_window(self) -> None:
        if self._window_visible:
            self.on_hide_window()
            self._window_visible = False
        else:
            self._show_window()

    def _add_icon(self) -> bool:
        """把图标加入通知区域；也用于 Explorer 重启后的恢复。"""
        if self._nid is None:
            return False

        if windll.shell32.Shell_NotifyIconW(NIM_ADD, byref(self._nid)):
            self._icon_added = True
            return True

        self._icon_added = False
        logger.error("添加托盘图标失败: %s", ctypes.get_last_error())
        return False

    def _update_icon(self) -> None:
        """在托盘线程中替换 HICON；新图标生效后再释放旧图标。"""
        if not (self._hwnd and self._nid):
            return

        new_icon = self._image_to_hicon(self._create_icon_image(), self._get_icon_size())
        old_icon = self._hicon
        self._hicon = new_icon
        self._nid.hIcon = new_icon

        windll.shell32.Shell_NotifyIconW(NIM_MODIFY, byref(self._nid))

        if old_icon:
            windll.user32.DestroyIcon(old_icon)

    def _remove_icon(self) -> None:
        """从通知区域移除图标并释放 GDI 句柄（只能由托盘线程调用）。"""
        self._icon_added = False
        if self._nid:
            windll.shell32.Shell_NotifyIconW(NIM_DELETE, byref(self._nid))
            self._nid = None

        if self._hicon:
            windll.user32.DestroyIcon(self._hicon)
            self._hicon = None

    def update_status(self, is_running: bool) -> None:
        """更新运行状态；实际图标操作通过消息转交给托盘线程。"""
        with self._state_lock:
            if is_running == self._is_running:
                return  # 状态没变就不重建图标，避免反复调用 GDI 和 Shell
            self._is_running = is_running

        hwnd = self._hwnd
        if hwnd and self._running:
            windll.user32.PostMessageW(hwnd, WM_TRAY_STATUS, 0, 0)

    def set_window_visible(self, visible: bool) -> None:
        self._window_visible = visible

    def run(self) -> None:
        """注册窗口类、创建托盘图标并运行 Win32 消息循环。"""
        self._running = True
        try:
            hinstance = windll.kernel32.GetModuleHandleW(None)

            self._wndproc_ref = WNDPROC(self._wnd_proc)

            class_name = "LukerTrayClass"
            wc = WNDCLASSW()
            wc.style = CS_DBLCLKS
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
                logger.error("注册窗口类失败: %s", ctypes.get_last_error())
                return

            self._hwnd = windll.user32.CreateWindowExW(
                0, class_name, "Luker Tray", 0, 0, 0, 0, 0, None, None, hinstance, None
            )

            if not self._hwnd:
                logger.error("创建窗口失败: %s", ctypes.get_last_error())
                return

            self._hicon = self._image_to_hicon(self._create_icon_image(), self._get_icon_size())

            self._nid = NOTIFYICONDATA()
            self._nid.cbSize = sizeof(NOTIFYICONDATA)
            self._nid.hWnd = self._hwnd
            self._nid.uID = 1
            self._nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
            self._nid.uCallbackMessage = WM_TRAYICON
            self._nid.hIcon = self._hicon
            self._nid.szTip = "Luker 启动器"

            self._add_icon()
            self._ready.set()

            msg = MSG()
            while self._running:
                ret = windll.user32.GetMessageW(byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                windll.user32.TranslateMessage(byref(msg))
                windll.user32.DispatchMessageW(byref(msg))
        finally:
            self._ready.set()
            self._running = False
            self._remove_icon()
            if self._hwnd:
                windll.user32.DestroyWindow(self._hwnd)
                self._hwnd = None

    def run_detached(self) -> bool:
        """在后台启动托盘；返回图标是否成功加入通知区域。"""
        self._thread = Thread(target=self.run, daemon=True, name="TrayMessageLoop")
        self._thread.start()
        # 等窗口和图标创建完成，避免首次右键菜单时 hwnd 还不存在
        self._ready.wait(timeout=2)
        return bool(self._icon_added and self._thread and self._thread.is_alive())

    def stop(self) -> None:
        """请求托盘线程清理图标并退出消息循环（可从任意线程调用）。"""
        hwnd = self._hwnd
        if hwnd:
            windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        else:
            self._running = False

        thread = self._thread
        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=2)
        self._thread = None
