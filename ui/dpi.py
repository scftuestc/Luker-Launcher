"""显示器 DPI 与窗口几何工具。

进程使用 Per-Monitor V2 感知，因此 Win32 坐标、Tk 的 geometry 位置和
winfo_width/height 都是物理像素；CustomTkinter 只对窗口 width/height
应用缩放，不对 x/y 应用缩放。
"""

import contextlib
import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass
from typing import Literal

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
_get_dpi_for_window = getattr(_user32, "GetDpiForWindow", None)
if _get_dpi_for_window is not None:
    _get_dpi_for_window.argtypes = [wintypes.HWND]
    _get_dpi_for_window.restype = wintypes.UINT
_get_dpi_for_system = getattr(_user32, "GetDpiForSystem", None)
if _get_dpi_for_system is not None:
    _get_dpi_for_system.restype = wintypes.UINT
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int
_shcore.GetDpiForMonitor.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(wintypes.UINT),
]
_shcore.GetDpiForMonitor.restype = ctypes.c_long
_shcore.GetProcessDpiAwareness.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_int),
]
_shcore.GetProcessDpiAwareness.restype = ctypes.c_long


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

    def signature(self) -> tuple[int, int, int, int, int]:
        """返回用于判断显示器变化的标识。"""
        return (self.left, self.top, self.right, self.bottom, self.dpi)


def _monitor_handle(hwnd: int | None, point: tuple[int, int] | None) -> int:
    """按屏幕点、窗口或主屏选择显示器句柄。"""
    if point is not None:
        return _user32.MonitorFromPoint(wintypes.POINT(*point), MONITOR_DEFAULTTONEAREST)
    if hwnd:
        return _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    return _user32.MonitorFromPoint(wintypes.POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)


def _dpi_for(hwnd: int | None, monitor: int) -> int:
    # 窗口 DPI 最可靠；只有传屏幕点时 GetDpiForMonitor 才没有窗口可查
    if hwnd and _get_dpi_for_window is not None:
        dpi = _get_dpi_for_window(hwnd)
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
    dpi = _get_dpi_for_system() if _get_dpi_for_system is not None else BASE_DPI
    return MonitorInfo(0, 0, width, height, dpi or BASE_DPI)


def get_process_dpi_awareness() -> int | None:
    """返回进程 DPI 感知级别：0 不感知，1 系统感知，2 每显示器感知。"""
    value = ctypes.c_int()
    try:
        if _shcore.GetProcessDpiAwareness(None, ctypes.byref(value)) == 0:
            return value.value
    except AttributeError:
        pass
    return None


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


def fit_window_with_minimum(
    desired_width: int,
    desired_height: int,
    minimum_width: int,
    minimum_height: int,
    monitor: MonitorInfo,
    scale: float,
    margin: int = 0,
) -> tuple[int, int, int, int]:
    """返回当前显示器上的有效最小尺寸和受限后的窗口尺寸。

    最小尺寸也要受工作区限制，否则从大屏移到小屏时旧的 minsize
    会把已经缩小到工作区的窗口重新顶大。
    """
    min_width, min_height = fit_logical_window_size(
        minimum_width, minimum_height, monitor, scale, margin
    )
    width, height = fit_logical_window_size(
        max(min_width, desired_width),
        max(min_height, desired_height),
        monitor,
        scale,
        margin,
    )
    return min_width, min_height, width, height


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


def clamp_window_position(
    x: int,
    y: int,
    width: int,
    height: int,
    monitor: MonitorInfo,
    margin: int = 8,
) -> tuple[int, int]:
    """把普通窗口的位置限制在工作区内，不改变窗口尺寸。"""
    x = max(monitor.left + margin, min(x, monitor.right - width - margin))
    y = max(monitor.top + margin, min(y, monitor.bottom - height - margin))
    return x, y


def format_geometry(
    width: int | None,
    height: int | None,
    x: int,
    y: int,
) -> str:
    """生成 Tk geometry 字符串。

    负坐标必须写成 "+-100"：Tk 会把 "-100" 解释成距屏幕右边缘/下边缘的
    偏移（实测窗口会跑到屏幕另一端），而不是负坐标。
    """
    size = f"{width}x{height}" if width is not None and height is not None else ""
    x_part = f"+{x}" if x >= 0 else f"+-{abs(x)}"
    y_part = f"+{y}" if y >= 0 else f"+-{abs(y)}"
    return f"{size}{x_part}{y_part}"


@dataclass(frozen=True)
class WindowPlacement:
    """窗口在目标显示器上的逻辑尺寸、可选最小尺寸和物理位置。"""

    logical_width: int
    logical_height: int
    minimum_width: int | None
    minimum_height: int | None
    x: int
    y: int
    geometry: str


def plan_window_placement(
    desired_width: int,
    desired_height: int,
    monitor: MonitorInfo,
    scale: float,
    *,
    margin: int = 0,
    minimum: tuple[int, int] | None = None,
    anchor: Literal["center", "clamp"] = "center",
    current_position: tuple[int, int] | None = None,
) -> WindowPlacement:
    """按窗口策略计算尺寸和位置，不直接调用 Tk。

    minimum=None 表示固定尺寸窗口（设置窗口）；提供 minimum 时使用
    日志窗口的最小尺寸策略。anchor="center" 用于首次显示，
    anchor="clamp" 用于跨屏后保留当前位置并限制在工作区内。
    """
    if minimum is None:
        logical_width, logical_height = fit_logical_window_size(
            desired_width,
            desired_height,
            monitor,
            scale,
            margin=margin,
        )
        minimum_width: int | None = None
        minimum_height: int | None = None
    else:
        minimum_width, minimum_height, logical_width, logical_height = fit_window_with_minimum(
            desired_width,
            desired_height,
            minimum[0],
            minimum[1],
            monitor,
            scale,
            margin=margin,
        )

    physical_width = round(logical_width * scale)
    physical_height = round(logical_height * scale)
    if anchor == "center":
        x, y = centered_position(physical_width, physical_height, monitor)
    else:
        if current_position is None:
            raise ValueError("anchor='clamp' 需要 current_position")
        x, y = clamp_window_position(
            current_position[0],
            current_position[1],
            physical_width,
            physical_height,
            monitor,
        )

    return WindowPlacement(
        logical_width,
        logical_height,
        minimum_width,
        minimum_height,
        x,
        y,
        format_geometry(logical_width, logical_height, x, y),
    )


def sync_window_scaling(
    window: ctk.CTk | ctk.CTkToplevel,
    target_scale: float | None = None,
) -> float:
    """立即应用目标缩放，避免等待 CustomTkinter 的 100ms DPI 轮询。"""
    fallback = target_scale if target_scale is not None else 1.0
    try:
        tracker = ctk.ScalingTracker
        scale = target_scale if target_scale is not None else tracker.get_window_dpi_scaling(window)
        # CTk 每 100ms 才轮询一次显示器 DPI；这里提前更新，避免首帧按旧缩放绘制
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


def discard_window_scaling(window: ctk.CTk | ctk.CTkToplevel) -> None:
    """移除已销毁窗口的缩放缓存，避免反复打开 Toplevel 时泄漏。"""
    with contextlib.suppress(AttributeError):
        ctk.ScalingTracker.window_dpi_scaling_dict.pop(window, None)
