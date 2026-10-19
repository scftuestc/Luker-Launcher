"""显示器 DPI 与窗口几何工具。

进程使用 Per-Monitor V2 感知，因此 Win32 坐标、Tk 的 geometry 位置和
winfo_width/height 都是物理像素；CustomTkinter 只对窗口 width/height
应用缩放，不对 x/y 应用缩放。
"""

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass

import customtkinter as ctk

logger = logging.getLogger(__name__)

BASE_DPI = 96
MONITOR_DEFAULTTONEAREST = 2
MONITOR_DEFAULTTOPRIMARY = 1
MDT_EFFECTIVE_DPI = 0

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_shcore = ctypes.WinDLL("shcore", use_last_error=True)


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
_user32.MonitorFromPoint.restype = wintypes.HANDLE
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.MonitorFromWindow.restype = wintypes.HANDLE
_user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]
_user32.GetMonitorInfoW.restype = wintypes.BOOL
_user32.GetDpiForWindow.argtypes = [wintypes.HWND]
_user32.GetDpiForWindow.restype = wintypes.UINT
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int
_shcore.GetDpiForMonitor.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(wintypes.UINT),
]
_shcore.GetDpiForMonitor.restype = ctypes.c_long


@dataclass(frozen=True)
class MonitorInfo:
    """显示器工作区（物理像素）和 DPI。"""

    left: int
    top: int
    right: int
    bottom: int
    dpi: int = BASE_DPI

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def scale(self) -> float:
        return self.dpi / BASE_DPI


def _monitor_handle(hwnd: int | None, point: tuple[int, int] | None) -> int:
    if point is not None:
        return _user32.MonitorFromPoint(wintypes.POINT(*point), MONITOR_DEFAULTTONEAREST)
    if hwnd:
        return _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    return _user32.MonitorFromPoint(wintypes.POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)


def _dpi_for(hwnd: int | None, monitor: int) -> int:
    if hwnd:
        dpi = _user32.GetDpiForWindow(hwnd)
        if dpi:
            return dpi

    dpi_x, dpi_y = wintypes.UINT(), wintypes.UINT()
    result = _shcore.GetDpiForMonitor(
        monitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
    )
    if result == 0 and dpi_x.value:
        return dpi_x.value
    return BASE_DPI


def get_monitor_info(
    hwnd: int | None = None,
    point: tuple[int, int] | None = None,
) -> MonitorInfo:
    """返回窗口或屏幕点所在显示器的工作区与 DPI。"""
    monitor = _monitor_handle(hwnd, point)
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(info)

    if monitor and _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        work = info.rcWork
        return MonitorInfo(
            work.left,
            work.top,
            work.right,
            work.bottom,
            _dpi_for(hwnd, monitor),
        )

    logger.warning("获取显示器工作区失败，回退到主屏")
    width = _user32.GetSystemMetrics(0)  # SM_CXSCREEN
    height = _user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return MonitorInfo(0, 0, width, height)


def fit_logical_window_size(
    desired_width: int,
    desired_height: int,
    monitor: MonitorInfo,
    scale: float,
    margin: int = 0,
) -> tuple[int, int]:
    """按工作区限制逻辑窗口尺寸；margin 为物理像素。"""
    available_width = max(1, int((monitor.width - 2 * margin) / scale))
    available_height = max(1, int((monitor.height - 2 * margin) / scale))
    return min(desired_width, available_width), min(desired_height, available_height)


def centered_position(
    width: int,
    height: int,
    monitor: MonitorInfo,
) -> tuple[int, int]:
    """把物理尺寸的窗口放在工作区中央，返回物理坐标。"""
    x = monitor.left + max(0, (monitor.width - width) // 2)
    y = monitor.top + max(0, (monitor.height - height) // 2)
    return x, y


def clamp_popup_position(
    x: int,
    y: int,
    width: int,
    height: int,
    monitor: MonitorInfo,
    margin: int = 10,
    gap: int = 10,
) -> tuple[int, int]:
    """把弹出窗口限制在工作区内；空间不足时先向上/向左翻转。"""
    if x + width > monitor.right - margin:
        x -= width + gap
    if y + height > monitor.bottom - margin:
        y -= height + gap

    max_x = monitor.right - width - margin
    max_y = monitor.bottom - height - margin
    x = max(monitor.left + margin, min(x, max_x))
    y = max(monitor.top + margin, min(y, max_y))
    return x, y


def format_geometry(
    width: int | None,
    height: int | None,
    x: int,
    y: int,
) -> str:
    """生成 Tk geometry 字符串，正确处理副屏的负坐标。"""
    size = f"{width}x{height}" if width is not None and height is not None else ""
    return f"{size}{x:+d}{y:+d}"


def sync_window_scaling(
    window: ctk.CTk | ctk.CTkToplevel,
    target_scale: float | None = None,
) -> float:
    """立即应用目标缩放，避免等待 CustomTkinter 的 100ms DPI 轮询。"""
    fallback = target_scale if target_scale is not None else 1.0
    try:
        tracker = ctk.ScalingTracker
        scale = target_scale if target_scale is not None else tracker.get_window_dpi_scaling(window)
        if tracker.window_dpi_scaling_dict.get(window) != scale:
            tracker.window_dpi_scaling_dict[window] = scale
            tracker.update_scaling_callbacks_for_window(window)
        # CTk 的 _set_scaling 会把 min/max 临时锁在当前尺寸；
        # 调用方随后还要设置最终尺寸，这里恢复为不限制。
        window.wm_minsize(1, 1)
        window.wm_maxsize(32767, 32767)
    except (AttributeError, KeyError):
        logger.warning("同步窗口 DPI 缩放失败", exc_info=True)
        return fallback

    return scale
