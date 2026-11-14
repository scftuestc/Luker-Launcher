"""CustomTkinter 私有绘制接口的唯一适配层。

CTkSwitch 的滑块动画依赖 _canvas、_draw_engine 等私有属性；
集中在这里后，升级 CustomTkinter 时只需要回归本文件。
缺少私有接口时 supported 为 False，调用方退化为无动画切换。
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

_REQUIRED_ATTRIBUTES = (
    '_canvas',
    '_draw_engine',
    '_switch_width',
    '_switch_height',
    '_corner_radius',
    '_border_width',
    '_button_length',
    '_apply_widget_scaling',
)


def get_textbox(widget: Any) -> Any:
    """返回 CTkTextbox 内部 Text 控件；升级 CTk 时只回归这里。"""
    return widget._textbox


def get_widget_scaling(widget: Any) -> float:
    """返回 CTk 控件的逻辑缩放；私有方法不可用时回退 1.0。"""
    getter = getattr(widget, '_get_widget_scaling', None)
    if not callable(getter):
        return 1.0
    try:
        scale = float(getter())
    except (AttributeError, TypeError, ValueError, tk.TclError):
        return 1.0
    return scale if scale > 0 else 1.0


def get_window_dpi_scaling(window: Any) -> float:
    """读取 CTk 为窗口缓存的 DPI 缩放。"""
    return ctk.ScalingTracker.get_window_dpi_scaling(window)


def set_window_scaling_cache(window: Any, scale: float) -> bool:
    """更新 CTk 的窗口缩放缓存；返回是否发生变化。"""
    tracker = ctk.ScalingTracker
    if tracker.window_dpi_scaling_dict.get(window) == scale:
        return False
    tracker.window_dpi_scaling_dict[window] = scale
    tracker.update_scaling_callbacks_for_window(window)
    return True


def discard_window_scaling_cache(window: Any) -> None:
    """移除已销毁窗口的缩放缓存。"""
    ctk.ScalingTracker.window_dpi_scaling_dict.pop(window, None)


class CtkSwitchAdapter:
    """封装 CTkSwitch 私有画布和绘制引擎访问。"""

    def __init__(self, switch: ctk.CTkSwitch) -> None:
        self._switch = switch
        self._canvas: Any = getattr(switch, '_canvas', None)
        self._draw_engine: Any = getattr(switch, '_draw_engine', None)
        self._supported = (
            self._canvas is not None
            and self._draw_engine is not None
            and all(hasattr(switch, name) for name in _REQUIRED_ATTRIBUTES)
        )

    @property
    def supported(self) -> bool:
        return self._supported

    def set_track_colors(self, off: str, on: str) -> None:
        """更新轨道关闭/开启颜色。"""
        if not self._supported:
            return
        self._canvas.itemconfig('inner_parts', fill=off, outline=off)
        self._canvas.itemconfig('progress_parts', fill=on, outline=on)

    def draw_slider(self, progress: float, thumb_color: str) -> None:
        """按 0..1 的进度重绘滑块位置和填充色。"""
        if not self._supported:
            return
        switch = self._switch
        self._canvas.itemconfig('slider_parts', fill=thumb_color, outline=thumb_color)
        self._draw_engine.draw_rounded_slider_with_border_and_button(
            switch._apply_widget_scaling(switch._switch_width),
            switch._apply_widget_scaling(switch._switch_height),
            switch._apply_widget_scaling(switch._corner_radius),
            switch._apply_widget_scaling(switch._border_width),
            switch._apply_widget_scaling(switch._button_length),
            switch._apply_widget_scaling(switch._corner_radius),
            progress,
            'w',
        )
