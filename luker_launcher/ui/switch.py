"""带平滑滑块动画的开关。"""

import contextlib
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from luker_launcher.theme import mix_color
from luker_launcher.ui.ctk_adapter import CtkSwitchAdapter
from luker_launcher.ui.tokens import (
    MOTION_SWITCH_INTERVAL_MS as SWITCH_ANIMATION_INTERVAL_MS,
)
from luker_launcher.ui.tokens import (
    MOTION_SWITCH_STEPS as SWITCH_ANIMATION_STEPS,
)
from luker_launcher.ui.tokens import (
    MOTION_SWITCH_THUMB_HOVER_MIX as SWITCH_THUMB_HOVER_MIX,
)
from luker_launcher.ui.tokens import (
    MOTION_SWITCH_TRACK_HOVER_MIX as SWITCH_TRACK_HOVER_MIX,
)
from luker_launcher.ui.tokens import (
    SWITCH_BORDER_WIDTH,
    SWITCH_CORNER_RADIUS,
    SWITCH_HEIGHT,
    SWITCH_WIDTH,
)


def _clamp_progress(progress: float) -> float:
    return max(0.0, min(1.0, progress))


def switch_track_colors(colors: dict[str, str], hovering: bool) -> tuple[str, str]:
    """返回轨道关闭/开启颜色；悬停时向正文色轻微偏移。"""
    if hovering:
        off = mix_color(colors['border'], colors['text'], SWITCH_TRACK_HOVER_MIX)
        on = mix_color(colors['accent'], colors['text'], SWITCH_TRACK_HOVER_MIX)
    else:
        off = colors['border']
        on = colors['accent']
    return off, on


def switch_thumb_color(colors: dict[str, str], progress: float) -> str:
    """滑块颜色随开关进度在 text 与 on_accent 间过渡。"""
    return mix_color(colors['text'], colors['on_accent'], _clamp_progress(progress))


def switch_thumb_hover_color(colors: dict[str, str], progress: float) -> str:
    """悬停时滑块再向 on_accent 偏移，避免在强调色轨道上消失。"""
    return mix_color(
        switch_thumb_color(colors, progress),
        colors['on_accent'],
        SWITCH_THUMB_HOVER_MIX,
    )


class AnimatedSwitch(ctk.CTkSwitch):
    """CTkSwitch 的平滑滑块版本；get/select/deselect 接口保持不变。

    复用 CTkSwitch 的绘制引擎，让滑块位置可以取 0..1 的中间值；
    升级 CustomTkinter 时需要回归开关动画。
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        colors: dict[str, str],
        selected: bool = False,
        command: Callable[[], None] | None = None,
        text: str = "",
        font: ctk.CTkFont | None = None,
        **kwargs: object,
    ) -> None:
        options: dict[str, object] = {
            'text': text,
            'font': font,
            'text_color': colors['text_dim'] if text else colors['text'],
            'fg_color': colors['border'],
            'progress_color': colors['accent'],
            'button_color': colors['text'],
            'button_hover_color': colors['on_accent'],
            'switch_width': SWITCH_WIDTH,
            'switch_height': SWITCH_HEIGHT,
            'corner_radius': SWITCH_CORNER_RADIUS,
            'border_width': SWITCH_BORDER_WIDTH,
            'command': command,
        }
        if not text:
            # 空文本时 CTkSwitch 仍按默认宽度占位，会让开关右侧留白
            options['width'] = SWITCH_WIDTH
        options.update(kwargs)
        super().__init__(parent, **options)

        self._adapter = CtkSwitchAdapter(self)
        self._colors = colors
        self._slider_value = 1.0 if selected else 0.0
        self._animation_target = self._slider_value
        self._animation_job: str | None = None
        self._hovering = False
        self._destroyed = False
        self.set_immediate(selected)

    def set_immediate(self, state: bool) -> None:
        """立即切到目标状态，不播放动画；用于窗口初始化。"""
        super().set(state)
        self._slider_value = 1.0 if state else 0.0
        self._animation_target = self._slider_value
        self._redraw_slider()

    def set(self, state: bool, from_variable_callback: bool = False) -> None:
        """切换状态并播放过渡动画。"""
        previous = self._slider_value
        super().set(state, from_variable_callback)
        self._slider_value = previous
        if self._hovering:
            self._apply_track_colors()
        else:
            self._redraw_slider()
        self._animate_to(1.0 if state else 0.0)

    def _animate_to(self, target: float) -> None:
        self._animation_target = target
        if not self._adapter.supported:
            # 缺少 CTk 私有绘制接口时直接切到目标状态，不播放半程动画
            self._slider_value = target
            return
        if self._destroyed or self._animation_job is not None:
            return
        if self._slider_value == target:
            return
        try:
            self._animation_job = self.after(0, self._tick_animation)
        except tk.TclError:
            self._animation_job = None

    def _tick_animation(self) -> None:
        self._animation_job = None
        if self._destroyed:
            return

        target = self._animation_target
        step = 1.0 / SWITCH_ANIMATION_STEPS
        difference = target - self._slider_value
        if abs(difference) <= step + 1e-9:
            self._slider_value = target
        elif difference > 0:
            self._slider_value += step
        else:
            self._slider_value -= step

        try:
            self._redraw_slider()
        except tk.TclError:
            return

        if self._slider_value == target:
            return
        try:
            self._animation_job = self.after(
                SWITCH_ANIMATION_INTERVAL_MS,
                self._tick_animation,
            )
        except tk.TclError:
            self._animation_job = None

    def _redraw_slider(self) -> None:
        """按当前进度重绘滑块位置和颜色，只改几何与滑块填充。"""
        thumb = switch_thumb_color(self._colors, self._slider_value)
        if self._hovering:
            thumb = switch_thumb_hover_color(self._colors, self._slider_value)
        self._adapter.draw_slider(self._slider_value, thumb)

    def _apply_track_colors(self) -> None:
        off, on = switch_track_colors(self._colors, self._hovering)
        self._adapter.set_track_colors(off, on)
        self._redraw_slider()

    def _on_enter(self, event: object = 0) -> None:
        super()._on_enter(event)
        self._hovering = True
        with contextlib.suppress(tk.TclError):
            self._apply_track_colors()

    def _on_leave(self, event: object = 0) -> None:
        super()._on_leave(event)
        self._hovering = False
        with contextlib.suppress(tk.TclError):
            self._apply_track_colors()

    def destroy(self) -> None:
        self._destroyed = True
        if self._animation_job is not None:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._animation_job)
            self._animation_job = None
        super().destroy()
