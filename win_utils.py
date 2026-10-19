"""Windows 窗口效果、字体探测等通用界面工具。"""

import ctypes
import logging
import sys
import tkinter.font as tkfont
from ctypes import byref, c_int, sizeof, windll

logger = logging.getLogger(__name__)


class WindowsBlur:
    """Win32 模糊/圆角效果封装；系统不支持时静默降级为普通窗口。"""

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
    def enable_blur(hwnd, color=0xCC000000):
        user32 = windll.user32
        dwmapi = windll.dwmapi
        build = sys.getwindowsversion().build

        try:
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

        except Exception as e:
            logger.warning("应用毛玻璃失败: %s", e)

    @staticmethod
    def extend_frame(hwnd):
        margins = WindowsBlur.MARGINS(-1, -1, -1, -1)
        windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, byref(margins))


def hex_to_colorref(hex_color: str, alpha: int = 0xDD) -> int:
    """把 #RRGGBB 转换成 SetWindowCompositionAttribute 使用的 0xAABBGGRR。"""
    value = hex_color.lstrip('#')
    if len(value) != 6:
        return 0xDD000000
    try:
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except ValueError:
        return 0xDD000000
    return ((alpha & 0xFF) << 24) | (b << 16) | (g << 8) | r


def apply_blur(hwnd, bg_color: str, alpha: int = 0xDD) -> None:
    """给窗口应用与当前主题背景一致的毛玻璃效果。"""
    try:
        WindowsBlur.extend_frame(hwnd)
        WindowsBlur.enable_blur(hwnd, hex_to_colorref(bg_color, alpha))
    except Exception as e:
        logger.warning("设置窗口毛玻璃失败: %s", e)


def get_ui_font():
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


def get_mono_font():
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
