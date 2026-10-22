"""Windows 窗口效果、字体探测等通用界面工具。"""

import ctypes
import logging
import sys
import tkinter as tk
import tkinter.font as tkfont
from ctypes import byref, c_int, sizeof, windll

from theme import is_light_color

logger = logging.getLogger(__name__)

# DwmSetWindowAttribute 的窗口圆角偏好；Win11 22000 起支持
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
CORNER_PREFERENCE_MIN_BUILD = 22000


class WindowsBlur:
    """Win32 模糊/圆角效果封装；系统不支持时由调用者记录并降级为普通窗口。"""

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020

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
    def enable_blur(hwnd: int, color: int = 0xCC000000, accent_state: int = 4) -> None:
        """应用 DWM 模糊；失败时抛出异常，由调用者统一记录。"""
        user32 = windll.user32
        dwmapi = windll.dwmapi

        value = c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(value), sizeof(value))

        accent = WindowsBlur.ACCENT_POLICY()
        accent.AccentState = accent_state
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

    @staticmethod
    def disable_blur(hwnd: int) -> None:
        """关闭 DWM 毛玻璃，并移除 Tk 透明度留下的分层窗口样式。"""
        user32 = windll.user32
        dwmapi = windll.dwmapi

        value = c_int(0)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(value), sizeof(value))

        accent = WindowsBlur.ACCENT_POLICY()
        accent.AccentState = 0
        accent.AccentFlags = 0
        accent.GradientColor = 0

        data = WindowsBlur.WINDOWCOMPOSITIONATTRIBDATA()
        data.Attrib = 19
        data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.cbData = sizeof(accent)
        user32.SetWindowCompositionAttribute(hwnd, byref(data))

        margins = WindowsBlur.MARGINS(0, 0, 0, 0)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, byref(margins))

        ex_style = user32.GetWindowLongW(hwnd, WindowsBlur.GWL_EXSTYLE)
        if ex_style & WindowsBlur.WS_EX_LAYERED:
            new_style = (ex_style & ~WindowsBlur.WS_EX_LAYERED) & 0xFFFFFFFF
            user32.SetWindowLongW(hwnd, WindowsBlur.GWL_EXSTYLE, new_style)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, WindowsBlur.SWP_FLAGS)
        dwmapi.DwmFlush()


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


def apply_blur(hwnd: int, bg_color: str, alpha: int = 0xDD, accent_state: int = 4) -> None:
    """给窗口应用与当前主题背景一致的毛玻璃；失败时抛出异常。"""
    WindowsBlur.extend_frame(hwnd)
    WindowsBlur.enable_blur(
        hwnd,
        hex_to_colorref(bg_color, alpha),
        accent_state=accent_state,
    )


def apply_window_blur(
    window: tk.Tk | tk.Toplevel,
    bg_color: str,
    alpha: int = 0xDD,
    *,
    accent_state: int = 4,
    context: str = "窗口",
) -> None:
    """给顶层窗口应用毛玻璃；失败只记录日志，不影响窗口显示。

    只接受顶层窗口；子控件会解析到错误的父句柄。
    """
    try:
        hwnd = windll.user32.GetParent(window.winfo_id())
        apply_blur(hwnd, bg_color, alpha=alpha, accent_state=accent_state)
    except Exception:
        logger.warning("%s毛玻璃失败", context, exc_info=True)


def disable_window_blur(window: tk.Tk | tk.Toplevel, *, context: str = "窗口") -> None:
    """关闭顶层窗口的毛玻璃与分层透明效果。"""
    try:
        hwnd = windll.user32.GetParent(window.winfo_id())
        WindowsBlur.disable_blur(hwnd)
    except Exception:
        logger.warning("%s关闭毛玻璃失败", context, exc_info=True)


def apply_window_rounding(window: tk.Tk | tk.Toplevel, *, context: str = "窗口") -> None:
    """请求 Win11 的系统圆角，与毛玻璃开关无关；旧系统静默跳过。"""
    try:
        if sys.getwindowsversion().build < CORNER_PREFERENCE_MIN_BUILD:
            return
        hwnd = windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            return

        corner = c_int(DWMWCP_ROUND)
        result = windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, byref(corner), sizeof(corner)
        )
        if result != 0:
            logger.warning("%s圆角设置被系统拒绝: %s", context, result)
            return
        # 已经显示的窗口需要一次 frame change 才会重新取整
        windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, WindowsBlur.SWP_FLAGS)
    except Exception:
        logger.warning("%s设置圆角失败", context, exc_info=True)


def sync_window_blur(
    window: tk.Tk | tk.Toplevel,
    bg_color: str,
    *,
    enabled: bool,
    window_alpha: float,
    tint_alpha: int = 0xDD,
    context: str = "窗口",
) -> None:
    """按毛玻璃开关同步整窗透明度与 DWM 效果。"""
    if not enabled:
        window.attributes('-alpha', 1.0)
        disable_window_blur(window, context=context)
        apply_window_rounding(window, context=context)
        return

    # 先重置再设置透明度，确保从关闭状态切回时重新启用分层窗口
    window.attributes('-alpha', 1.0)
    window.attributes('-alpha', window_alpha)
    # 浅色背景用 blur-behind，避免 acrylic 的亮色 tint 冲淡文字
    accent_state = 3 if is_light_color(bg_color) else 4
    apply_window_blur(
        window,
        bg_color,
        alpha=tint_alpha,
        accent_state=accent_state,
        context=context,
    )
    apply_window_rounding(window, context=context)


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
