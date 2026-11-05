"""共享的缓动、窗口淡入和调色板过渡。

这里的动画都只依赖 Tk 的 after/attributes，不引入额外依赖；
调用方负责在窗口销毁、隐藏或主题重建时取消任务。
"""

from __future__ import annotations

import contextlib
import logging
import tkinter as tk
from collections.abc import Callable, Mapping

from luker_launcher.theme import mix_color
from luker_launcher.ui.tokens import MOTION_FADE_DURATION_MS, MOTION_FADE_INTERVAL_MS

logger = logging.getLogger(__name__)

ColorMap = Mapping[str, str]


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def ease_out_cubic(t: float) -> float:
    """先快后慢，适合窗口淡入。"""
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    """两端慢、中间快，适合颜色过渡。"""
    t = clamp01(t)
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0


def fade_palette(start: ColorMap, end: ColorMap, t: float) -> dict[str, str]:
    """按进度混合两套主题色；键集合以目标主题为准。"""
    progress = clamp01(t)
    return {key: mix_color(start[key], end[key], progress) for key in end}


class StepTicker:
    """按固定帧数执行 on_step(0..1)，完成时调用 on_done。

    只持有一个 after 任务；cancel 后用 generation 让旧回调失效。
    """

    def __init__(
        self,
        widget: tk.Misc,
        *,
        steps: int,
        interval_ms: int,
        on_step: Callable[[float], None],
        on_done: Callable[[], None] | None = None,
    ) -> None:
        self._widget = widget
        self._steps = max(1, steps)
        self._interval_ms = max(1, interval_ms)
        self._on_step = on_step
        self._on_done = on_done
        self._job: str | None = None
        self._generation = 0
        self._step = 0
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self, *, immediate: bool = True) -> None:
        """启动动画；immediate 为 True 时先回调一次 0。"""
        self.cancel()
        self._generation += 1
        generation = self._generation
        self._step = 0
        self._running = True
        if immediate:
            with contextlib.suppress(tk.TclError):
                self._on_step(0.0)
        self._schedule(generation)

    def cancel(self) -> None:
        self._generation += 1
        self._running = False
        if self._job is not None:
            with contextlib.suppress(tk.TclError):
                self._widget.after_cancel(self._job)
            self._job = None

    def _schedule(self, generation: int) -> None:
        try:
            self._job = self._widget.after(0, self._tick, generation)
        except tk.TclError:
            self._running = False
            self._job = None

    def _tick(self, generation: int) -> None:
        if generation != self._generation:
            return
        self._job = None
        if not self._alive():
            self._running = False
            return

        self._step += 1
        progress = 1.0 if self._step >= self._steps else self._step / self._steps
        try:
            self._on_step(progress)
        except tk.TclError:
            self._running = False
            return
        except Exception:
            # 单帧失败不应让动画永久停在中间状态
            logger.exception("动画步骤执行失败")
            self._running = False
            return

        if self._step >= self._steps:
            self._running = False
            if self._on_done is not None:
                self._on_done()
            return
        try:
            self._job = self._widget.after(self._interval_ms, self._tick, generation)
        except tk.TclError:
            self._running = False

    def _alive(self) -> bool:
        try:
            return bool(self._widget.winfo_exists())
        except tk.TclError:
            return False


class WindowFade:
    """整窗 alpha 淡入/淡出；只操作 -alpha，不碰 DWM 毛玻璃。"""

    def __init__(
        self,
        window: tk.Tk | tk.Toplevel,
        *,
        interval_ms: int = MOTION_FADE_INTERVAL_MS,
    ) -> None:
        self._window = window
        self._interval_ms = max(1, interval_ms)
        self._ticker: StepTicker | None = None
        self._start_alpha = 1.0
        self._end_alpha = 1.0
        self._current_alpha = 1.0
        self._on_done: Callable[[], None] | None = None

    @property
    def running(self) -> bool:
        return self._ticker is not None and self._ticker.running

    @property
    def current_alpha(self) -> float:
        return self._current_alpha

    def start(
        self,
        start: float,
        end: float,
        *,
        duration_ms: int = MOTION_FADE_DURATION_MS,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        """从 start 淡到 end；调用后立即设置起始 alpha，便于先设值再 deiconify。"""
        self.cancel()
        self._start_alpha = clamp01(start)
        self._end_alpha = clamp01(end)
        self._on_done = on_done
        self._apply(self._start_alpha)
        if self._start_alpha == self._end_alpha:
            self._finish()
            return

        steps = max(1, round(duration_ms / self._interval_ms))
        self._ticker = StepTicker(
            self._window,
            steps=steps,
            interval_ms=self._interval_ms,
            on_step=self._step,
            on_done=self._finish,
        )
        self._ticker.start(immediate=False)

    def cancel(self, *, reset: float | None = None) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
            self._ticker = None
        if reset is not None:
            self._apply(clamp01(reset))

    def _step(self, progress: float) -> None:
        eased = ease_out_cubic(progress)
        value = self._start_alpha + (self._end_alpha - self._start_alpha) * eased
        if progress >= 1.0:
            value = self._end_alpha
        self._apply(value)

    def _finish(self) -> None:
        self._ticker = None
        self._apply(self._end_alpha)
        callback = self._on_done
        self._on_done = None
        if callback is not None:
            callback()

    def _apply(self, alpha: float) -> None:
        self._current_alpha = clamp01(alpha)
        with contextlib.suppress(tk.TclError):
            self._window.attributes('-alpha', self._current_alpha)
