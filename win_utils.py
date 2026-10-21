"""Windows 窗口效果、字体探测等通用界面工具。"""

import ctypes
import logging
import sys
import tkinter as tk
import tkinter.font as tkfont
from ctypes import byref, c_int, sizeof, windll

logger = logging.getLogger(__name__)


class WindowsBlur:
    """Win32 模糊/圆角效果封装；系统不支持时由调用者记录并降级为普通窗口。"""

    class ACCENT_POLICY(ctypes.Structure):
        _fields_ = [
            ("AccentState", c_int),
            ("AccentFlags", c_int),
            ("GradientColor", ctypes.c_uint),
            ("AnimationId", c_int),
        ]

    class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
        _fields_ = [
            ("Attrib", c_int),
            ("pvData", ctypes.c_void_p),
            ("cbData", ctypes.c_size_t),
        ]

    class MARGINS(ctypes.Structure):
        _fields_ = [
            ("cxLeftWidth", c_int),
            ("cxRightWidth", c_int),
            ("cyTopHeight", c_int),
            ("cyBottomHeight", c_int),
        ]

    @staticmethod
    def enable_blur(hwnd: int, color: int = 0xCC000000) -> None:
        """应用 DWM 模糊；失败时抛出异常，由调用者统一记录。"""
        user32 = windll.user32
        dwmapi = windll.dwmapi
        build = sys.getwindowsversion().build

        value = c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(value), sizeof(value))

        if build >= 22000:
            corner = c_int(2)
            dwmapi.DwmSetWindowAttribute(hwnd, 33, byref(corner), sizeof(corner))

        accent = WindowsBlur.ACCENT_POLICY()
        accent.AccentState = 4
        accent.AccentFlags = 2
        accent.GradientColor = color

        data = WindowsBlur.WINDOWCOMPOSITIONATTRIBDATA()
        data.Attrib = 19
        data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.cbData = sizeof(accent)

        user32.SetWindowCompositionAttribute(hwnd, byref(data))

    @staticmethod
    def extend_frame(hwnd: int) -> None:
        margins = WindowsBlur.MARGINS(-1, -1, -1, -1)
        windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, byref(margins))


def hex_to_colorref(hex_color: str, alpha: int = 0xDD) -> int:
    """把 #RRGGBB 转换成 SetWindowCompositionAttribute 使用的 0xAABBGGRR。"""
    value = hex_color.lstrip('#')
    if len(value) != 6:
        return (alpha & 0xFF) << 24
    try:
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except ValueError:
        return (alpha & 0xFF) << 24
    return ((alpha & 0xFF) << 24) | (b << 16) | (g << 8) | r


def apply_blur(hwnd: int, bg_color: str, alpha: int = 0xDD) -> None:
    """给窗口应用与当前主题背景一致的毛玻璃；失败时抛出异常。"""
    WindowsBlur.extend_frame(hwnd)
    WindowsBlur.enable_blur(hwnd, hex_to_colorref(bg_color, alpha))


def apply_window_blur(
    window: tk.Tk | tk.Toplevel,
    bg_color: str,
    alpha: int = 0xDD,
    *,
    context: str = "窗口",
) -> None:
    """给顶层窗口应用毛玻璃；失败只记录日志，不影响窗口显示。

    只接受顶层窗口；子控件会解析到错误的父句柄。
    """
    try:
        hwnd = windll.user32.GetParent(window.winfo_id())
        apply_blur(hwnd, bg_color, alpha=alpha)
    except Exception:
        logger.warning("%s毛玻璃失败", context, exc_info=True)


def bind_window_drag(window: tk.Tk | tk.Toplevel, *widgets: tk.Misc) -> None:
    """让无边框窗口可以通过标题栏等控件拖动。"""
    offset_x = 0
    offset_y = 0

    def start_drag(event: tk.Event) -> None:
        nonlocal offset_x, offset_y
        offset_x = event.x_root - window.winfo_x()
        offset_y = event.y_root - window.winfo_y()

    def drag(event: tk.Event) -> None:
        window.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    for widget in widgets:
        widget.bind('<Button-1>', start_drag)
        widget.bind('<B1-Motion>', drag)


def get_ui_font() -> str:
    """返回可用界面字体，优先 Source Han / Noto。"""
    source_han_fonts = [
        'Source Han Sans SC',
        'Source Han Sans CN',
        'Noto Sans SC',
        'Noto Sans CJK SC',
        'Source Han Sans',
    ]
    available = tkfont.families()
    for font in source_han_fonts:
        if font in available:
            return font
    return 'Microsoft YaHei'


def get_mono_font() -> str:
    """返回可用等宽字体，优先 Source Han Mono / Consolas。"""
    mono_fonts = [
        'Source Han Mono SC',
        'Noto Sans Mono CJK SC',
        'Sarasa Mono SC',
        'Consolas',
        'Cascadia Code',
    ]
    available = tkfont.families()
    for font in mono_fonts:
        if font in available:
            return font
    return 'Consolas'
