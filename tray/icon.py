"""基于 Win32 Shell_NotifyIcon 的系统托盘图标。"""

import ctypes
import logging
from collections.abc import Callable, Sequence
from ctypes import WINFUNCTYPE, Structure, WinDLL, byref, c_int, sizeof, wintypes
from threading import Event, Lock, Thread, current_thread

from PIL import Image, ImageDraw

from ui.theme import LOGO_BAR_COLORS

logger = logging.getLogger(__name__)

WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
WM_TRAY_STATUS = WM_USER + 2
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002
CS_DBLCLKS = 0x0008
TRAY_CLASS_NAME = "LukerTrayClass"

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


class ICONINFO(Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


# 显式声明 64 位参数/返回值类型，避免 ctypes 默认按 32 位 int 转换。
# use_last_error=True 让 ctypes.get_last_error() 能读到这些调用失败的原因。
_user32 = WinDLL('user32', use_last_error=True)
_gdi32 = WinDLL('gdi32', use_last_error=True)
_shell32 = WinDLL('shell32', use_last_error=True)
_kernel32 = WinDLL('kernel32', use_last_error=True)

_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.DefWindowProcW.restype = wintypes.LPARAM
_user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    c_int,
    c_int,
    c_int,
    c_int,
    wintypes.HWND,
    wintypes.HANDLE,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
_user32.RegisterClassW.restype = wintypes.WORD
_user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
_user32.UnregisterClassW.restype = wintypes.BOOL
_user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
_user32.PostThreadMessageW.restype = wintypes.BOOL
_user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.GetMessageW.restype = c_int
_user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
_user32.TranslateMessage.restype = wintypes.BOOL
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
_user32.DispatchMessageW.restype = wintypes.LPARAM
_user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.PostMessageW.restype = wintypes.BOOL
_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.DestroyWindow.restype = wintypes.BOOL
_user32.PostQuitMessage.argtypes = [c_int]
_user32.PostQuitMessage.restype = None
_user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
_user32.RegisterWindowMessageW.restype = wintypes.UINT
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = c_int
_user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
_user32.CreateIconIndirect.restype = wintypes.HICON
_user32.DestroyIcon.argtypes = [wintypes.HICON]
_user32.DestroyIcon.restype = wintypes.BOOL
_user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
_user32.GetCursorPos.restype = wintypes.BOOL
_user32.GetDpiForSystem.argtypes = []
_user32.GetDpiForSystem.restype = wintypes.UINT
_user32.GetSystemMetricsForDpi.argtypes = [c_int, wintypes.UINT]
_user32.GetSystemMetricsForDpi.restype = c_int

_gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, c_int, c_int]
_gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi32.SetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
]
_gdi32.SetDIBits.restype = c_int
_gdi32.CreateBitmap.argtypes = [
    c_int,
    c_int,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
]
_gdi32.CreateBitmap.restype = wintypes.HBITMAP
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteObject.restype = wintypes.BOOL

_shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]
_shell32.Shell_NotifyIconW.restype = wintypes.BOOL

_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE
_kernel32.GetCurrentThreadId.argtypes = []
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD


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
        self._thread_id: int | None = None
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
            dpi = _user32.GetDpiForSystem()
            # 用大图标作为源，通知区域在高缩放下缩小时更清晰
            size = _user32.GetSystemMetricsForDpi(SM_CXICON, dpi)
            if size:
                # 源图按 64px 绘制，再大只会被缩小
                return max(32, min(64, int(size)))
        except (AttributeError, OSError):
            pass
        return 32

    def _image_to_hicon(self, image: Image.Image, size: int = 32) -> wintypes.HICON | None:
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        image = image.resize((size, size), Image.Resampling.LANCZOS)

        width, height = image.size
        pixels = image.tobytes()

        hdc = _user32.GetDC(None)
        if not hdc:
            logger.warning("获取屏幕 DC 失败: %s", ctypes.get_last_error())
            return None

        hbm_color: wintypes.HBITMAP | None = None
        hbm_mask: wintypes.HBITMAP | None = None
        try:
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0

            hbm_color = _gdi32.CreateCompatibleBitmap(hdc, width, height)
            if not hbm_color:
                logger.warning("创建彩色位图失败: %s", ctypes.get_last_error())
                return None

            bgra_pixels = bytearray(len(pixels))
            for i in range(0, len(pixels), 4):
                bgra_pixels[i] = pixels[i + 2]
                bgra_pixels[i + 1] = pixels[i + 1]
                bgra_pixels[i + 2] = pixels[i]
                bgra_pixels[i + 3] = pixels[i + 3]

            if not _gdi32.SetDIBits(hdc, hbm_color, 0, height, bytes(bgra_pixels), byref(bmi), 0):
                logger.warning("写入位图像素失败: %s", ctypes.get_last_error())
                return None

            # 32bpp 图标使用 alpha 通道，掩码必须明确清零，不能依赖未初始化内存。
            mask_stride = ((width + 31) // 32) * 4
            hbm_mask = _gdi32.CreateBitmap(width, height, 1, 1, bytes(mask_stride * height))
            if not hbm_mask:
                logger.warning("创建掩码位图失败: %s", ctypes.get_last_error())
                return None

            iconinfo = ICONINFO()
            iconinfo.fIcon = True
            iconinfo.xHotspot = 0
            iconinfo.yHotspot = 0
            iconinfo.hbmMask = hbm_mask
            iconinfo.hbmColor = hbm_color

            hicon = _user32.CreateIconIndirect(byref(iconinfo))
            if not hicon:
                logger.warning("创建托盘图标句柄失败: %s", ctypes.get_last_error())
                return None
            return hicon
        finally:
            if hbm_mask:
                _gdi32.DeleteObject(hbm_mask)
            if hbm_color:
                _gdi32.DeleteObject(hbm_color)
            _user32.ReleaseDC(None, hdc)

    def _get_cursor_pos(self) -> tuple[int, int]:
        """返回光标的物理屏幕坐标；Tk 的窗口位置也使用物理像素。"""
        pt = wintypes.POINT()
        _user32.GetCursorPos(byref(pt))
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
                _user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                self._hwnd = None
                _user32.PostQuitMessage(0)
                return 0
        except Exception:
            logger.exception("托盘消息处理失败")

        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

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

        if _shell32.Shell_NotifyIconW(NIM_ADD, byref(self._nid)):
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
        if not new_icon:
            logger.error("创建新托盘图标失败，保留当前图标")
            return

        old_icon = self._hicon
        self._nid.hIcon = new_icon
        try:
            if not _shell32.Shell_NotifyIconW(NIM_MODIFY, byref(self._nid)):
                logger.error("更新托盘图标失败: %s", ctypes.get_last_error())
                self._nid.hIcon = old_icon
                _user32.DestroyIcon(new_icon)
                return
        except Exception:
            self._nid.hIcon = old_icon
            _user32.DestroyIcon(new_icon)
            logger.exception("更新托盘图标失败")
            return

        self._hicon = new_icon
        if old_icon and not _user32.DestroyIcon(old_icon):
            logger.warning("释放旧托盘图标失败: %s", ctypes.get_last_error())

    def _remove_icon(self) -> None:
        """从通知区域移除图标并释放 GDI 句柄（只能由托盘线程调用）。"""
        self._icon_added = False
        if self._nid:
            if not _shell32.Shell_NotifyIconW(NIM_DELETE, byref(self._nid)):
                logger.warning("移除托盘图标失败: %s", ctypes.get_last_error())
            self._nid = None

        if self._hicon:
            if not _user32.DestroyIcon(self._hicon):
                logger.warning("释放托盘图标句柄失败: %s", ctypes.get_last_error())
            self._hicon = None

    def update_status(self, is_running: bool) -> None:
        """更新运行状态；实际图标操作通过消息转交给托盘线程。"""
        with self._state_lock:
            if is_running == self._is_running:
                return  # 状态没变就不重建图标，避免反复调用 GDI 和 Shell
            self._is_running = is_running

        hwnd = self._hwnd
        if hwnd and self._running:
            _user32.PostMessageW(hwnd, WM_TRAY_STATUS, 0, 0)

    def set_window_visible(self, visible: bool) -> None:
        self._window_visible = visible

    def run(self) -> None:
        """注册窗口类、创建托盘图标并运行 Win32 消息循环。"""
        self._running = True
        self._thread_id = _kernel32.GetCurrentThreadId()
        hinstance: wintypes.HMODULE | None = None
        registered_class = False
        try:
            hinstance = _kernel32.GetModuleHandleW(None)
            if not hinstance:
                logger.error("获取模块句柄失败: %s", ctypes.get_last_error())
                return

            self._wndproc_ref = WNDPROC(self._wnd_proc)

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
            wc.lpszClassName = TRAY_CLASS_NAME

            atom = _user32.RegisterClassW(byref(wc))
            if not atom:
                logger.error("注册窗口类失败: %s", ctypes.get_last_error())
                return
            registered_class = True

            self._hwnd = _user32.CreateWindowExW(
                0, TRAY_CLASS_NAME, "Luker Tray", 0, 0, 0, 0, 0, None, None, hinstance, None
            )

            if not self._hwnd:
                logger.error("创建窗口失败: %s", ctypes.get_last_error())
                return

            self._hicon = self._image_to_hicon(self._create_icon_image(), self._get_icon_size())
            if not self._hicon:
                logger.error("创建初始托盘图标失败")
                return

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
                ret = _user32.GetMessageW(byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                _user32.TranslateMessage(byref(msg))
                _user32.DispatchMessageW(byref(msg))
        finally:
            self._ready.set()
            self._running = False
            try:
                self._remove_icon()
            finally:
                if self._hwnd:
                    _user32.DestroyWindow(self._hwnd)
                    self._hwnd = None
                if (
                    registered_class
                    and hinstance
                    and not _user32.UnregisterClassW(TRAY_CLASS_NAME, hinstance)
                ):
                    logger.warning("注销托盘窗口类失败: %s", ctypes.get_last_error())
                self._thread_id = None

    def run_detached(self) -> bool:
        """在后台启动托盘；返回图标是否成功加入通知区域。"""
        self._ready.clear()
        self._icon_added = False
        self._thread_id = None
        self._thread = Thread(target=self.run, daemon=True, name="TrayMessageLoop")
        self._thread.start()
        # 等窗口和图标创建完成，避免首次右键菜单时 hwnd 还不存在
        self._ready.wait(timeout=2)
        return bool(self._icon_added and self._thread and self._thread.is_alive())

    def stop(self) -> None:
        """请求托盘线程清理图标并退出消息循环（可从任意线程调用）。"""
        thread = self._thread
        hwnd = self._hwnd
        if hwnd:
            if not _user32.PostMessageW(hwnd, WM_CLOSE, 0, 0):
                logger.warning("请求托盘线程退出失败: %s", ctypes.get_last_error())
                self._running = False
                thread_id = self._thread_id
                if thread_id and not _user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0):
                    logger.warning("向托盘线程发送退出消息失败: %s", ctypes.get_last_error())
        else:
            self._running = False

        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=2)
        if thread and thread.is_alive():
            logger.warning("托盘线程未在超时内退出")
            return
        self._thread = None
        self._thread_id = None
