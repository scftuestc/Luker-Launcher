"""无边框根窗口的初始定尺、边缘拖拽缩放和跨屏 DPI 适配。"""

import tkinter as tk

import customtkinter as ctk

from dpi import (
    centered_position,
    clamp_window_position,
    fit_window_with_minimum,
    format_geometry,
    get_monitor_info,
    sync_window_scaling,
)

# 窗口的初始尺寸和最小尺寸（CTk 逻辑像素）
DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 640
MIN_WIDTH = 700
MIN_HEIGHT = 450
# 距离工作区边缘的留白（物理像素）
SCREEN_MARGIN = 24
# 边缘拖拽的命中宽度（按缩放换算，至少 4 物理像素）
EDGE_GRAB_PIXELS = 8

_EDGE_CURSORS = {
    'nw': 'size_nw_se',
    'se': 'size_nw_se',
    'ne': 'size_ne_sw',
    'sw': 'size_ne_sw',
    'n': 'size_ns',
    's': 'size_ns',
    'w': 'size_we',
    'e': 'size_we',
}


def _get_window_scale(window: tk.Misc) -> float:
    """返回窗口当前的 CTk 缩放系数。"""
    return ctk.ScalingTracker.get_window_scaling(window)


class WindowResizer:
    """维护无边框根窗口的几何：初始定尺、边缘缩放和跨屏适配。"""

    def __init__(
        self,
        window: tk.Tk,
        *,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        min_width: int = MIN_WIDTH,
        min_height: int = MIN_HEIGHT,
        margin: int = SCREEN_MARGIN,
        edge_pixels: int = EDGE_GRAB_PIXELS,
    ) -> None:
        self._window = window
        self._width = width
        self._height = height
        self._min_width = min_width
        self._min_height = min_height
        self._margin = margin
        self._edge_pixels = edge_pixels

        self._edge: str | None = None
        self._drag_start: tuple[int, int, int, int, int, int] | None = None
        self._monitor_signature: tuple[int, int, int, int, int] | None = None
        self._logical_width = width
        self._logical_height = height
        self._min_logical_width = min_width
        self._min_logical_height = min_height

    def apply_initial_geometry(self) -> None:
        """按主屏工作区设置初始尺寸并居中。"""
        monitor = get_monitor_info()
        scale = sync_window_scaling(self._window, monitor.scale)
        (
            self._min_logical_width,
            self._min_logical_height,
            self._logical_width,
            self._logical_height,
        ) = fit_window_with_minimum(
            self._width,
            self._height,
            self._min_width,
            self._min_height,
            monitor,
            scale,
            margin=self._margin,
        )
        physical_width = round(self._logical_width * scale)
        physical_height = round(self._logical_height * scale)
        x, y = centered_position(physical_width, physical_height, monitor)
        self._window.geometry(format_geometry(self._logical_width, self._logical_height, x, y))
        # 最小尺寸保存为逻辑值，拖拽时按当前缩放换算
        self._window.minsize(self._min_logical_width, self._min_logical_height)
        # 防止 CTk 在 DPI 变化后把最大尺寸锁死为当前尺寸
        self._window.maxsize(10000, 10000)
        self._monitor_signature = monitor.signature()

    def bind_events(self) -> None:
        """绑定缩放光标、拖拽和跨屏适配所需的窗口事件。"""
        self._window.bind('<Motion>', self._check_edge)
        self._window.bind('<Button-1>', self._start_resize)
        self._window.bind('<B1-Motion>', self._do_resize)
        self._window.bind('<ButtonRelease-1>', self._end_resize)
        self._window.bind('<Configure>', self._on_configure, add='+')

    def fit_to_current_monitor(self) -> None:
        """移动到不同 DPI 的显示器后重新限制尺寸和位置。"""
        if not self._window.winfo_exists() or not self._window.winfo_viewable():
            return

        monitor = get_monitor_info(hwnd=self._window.winfo_id())
        signature = monitor.signature()
        if signature == self._monitor_signature:
            return

        self._monitor_signature = signature
        scale = sync_window_scaling(self._window, monitor.scale)
        # 使用保存的逻辑尺寸，避免 CTk 自动缩放后的物理尺寸被重复缩小。
        # 最小尺寸也按当前显示器重算，否则旧的 minsize 会阻止窗口缩进工作区。
        (
            self._min_logical_width,
            self._min_logical_height,
            logical_width,
            logical_height,
        ) = fit_window_with_minimum(
            self._logical_width,
            self._logical_height,
            self._min_width,
            self._min_height,
            monitor,
            scale,
            margin=self._margin,
        )
        physical_width = round(logical_width * scale)
        physical_height = round(logical_height * scale)
        x, y = clamp_window_position(
            self._window.winfo_x(),
            self._window.winfo_y(),
            physical_width,
            physical_height,
            monitor,
        )

        self._window.minsize(self._min_logical_width, self._min_logical_height)
        self._window.maxsize(10000, 10000)
        self._window.geometry(format_geometry(logical_width, logical_height, x, y))
        self._logical_width = logical_width
        self._logical_height = logical_height

    def _on_configure(self, event: tk.Event) -> None:
        # 合并拖动过程中连续的 Configure 事件，空闲时只检查一次显示器
        if event.widget is self._window:
            self._window.after_idle(self.fit_to_current_monitor)

    def _check_edge(self, event: tk.Event) -> None:
        """根据指针位置显示缩放光标，并记录当前边缘。"""
        if event.widget is not self._window:
            self._window.configure(cursor='')
            self._edge = None
            return

        scale = _get_window_scale(self._window)
        margin = max(4, round(self._edge_pixels * scale))
        width, height = self._window.winfo_width(), self._window.winfo_height()
        x, y = event.x, event.y

        edge = None
        if x < margin and y < margin:
            edge = 'nw'
        elif x > width - margin and y < margin:
            edge = 'ne'
        elif x < margin and y > height - margin:
            edge = 'sw'
        elif x > width - margin and y > height - margin:
            edge = 'se'
        elif y < margin:
            edge = 'n'
        elif x < margin:
            edge = 'w'
        elif x > width - margin:
            edge = 'e'
        elif y > height - margin:
            edge = 's'

        self._window.configure(cursor=_EDGE_CURSORS.get(edge, '') if edge else '')
        self._edge = edge

    def _start_resize(self, event: tk.Event) -> None:
        if event.widget is not self._window or not self._edge:
            return
        self._drag_start = (
            event.x_root,
            event.y_root,
            self._window.winfo_width(),
            self._window.winfo_height(),
            self._window.winfo_x(),
            self._window.winfo_y(),
        )

    def _do_resize(self, event: tk.Event) -> None:
        if not self._edge or self._drag_start is None:
            return
        if event.widget is not self._window:
            return

        start_x, start_y, start_width, start_height, window_x, window_y = self._drag_start
        dx = event.x_root - start_x
        dy = event.y_root - start_y
        scale = _get_window_scale(self._window)
        min_width = round(self._min_logical_width * scale)
        min_height = round(self._min_logical_height * scale)

        width, height, x, y = start_width, start_height, window_x, window_y

        if 'e' in self._edge:
            width = max(min_width, start_width + dx)
        if 's' in self._edge:
            height = max(min_height, start_height + dy)
        if 'w' in self._edge:
            width = max(min_width, start_width - dx)
            if width != start_width:
                x = window_x + (start_width - width)
        if 'n' in self._edge:
            height = max(min_height, start_height - dy)
            if height != start_height:
                y = window_y + (start_height - height)

        # 物理像素先换算回 CTk 的逻辑尺寸，避免 geometry() 再次缩放
        logical_width = max(self._min_logical_width, round(width / scale))
        logical_height = max(self._min_logical_height, round(height / scale))
        self._window.geometry(format_geometry(logical_width, logical_height, x, y))
        self._logical_width = logical_width
        self._logical_height = logical_height

    def _end_resize(self, _event: tk.Event) -> None:
        self._edge = None
