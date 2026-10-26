"""控件悬停提示：轻量 Toplevel，不抢占焦点，不参与布局。"""

import contextlib
import logging
import tkinter as tk

import customtkinter as ctk

from ui.dpi import MonitorInfo, get_monitor_info

logger = logging.getLogger(__name__)

TOOLTIP_MARGIN = 8
TOOLTIP_PADDING = 20


def tooltip_wraplength(
    preferred: int,
    monitor: MonitorInfo,
    *,
    margin: int = TOOLTIP_MARGIN,
    padding: int = TOOLTIP_PADDING,
) -> int:
    """按工作区宽度限制提示文字换行宽度，避免提示框横向溢出。"""
    physical = monitor.width - 2 * margin - padding
    available = max(40, int(physical / max(monitor.scale, 1.0)))
    return min(preferred, available)


def tooltip_position(
    anchor: tuple[int, int, int, int],
    size: tuple[int, int],
    monitor: MonitorInfo,
    *,
    gap: int = 6,
    margin: int = 8,
) -> tuple[int, int]:
    """优先放在锚点下方并水平居中；下方不够时翻到上方，再限制在工作区内。"""
    anchor_x, anchor_y, anchor_width, anchor_height = anchor
    tip_width, tip_height = size
    x = anchor_x + anchor_width // 2 - tip_width // 2
    y = anchor_y + anchor_height + gap
    if y + tip_height > monitor.bottom - margin:
        y = anchor_y - tip_height - gap
    x = max(monitor.left + margin, min(x, monitor.right - tip_width - margin))
    y = max(monitor.top + margin, min(y, monitor.bottom - tip_height - margin))
    return x, y


class Tooltip:
    """悬停提示；首次显示时才创建窗口，主题重建时随父控件一起销毁。"""

    def __init__(
        self,
        master: tk.Misc,
        colors: dict[str, str],
        font_family: str,
        *,
        wraplength: int = 280,
    ) -> None:
        self._master = master
        self._colors = colors
        self._font_family = font_family
        self._wraplength = wraplength
        self._window: ctk.CTkToplevel | None = None
        self._label: ctk.CTkLabel | None = None
        self._anchor: tk.Misc | None = None

    def attach(self, widget: tk.Misc, text: str) -> None:
        """绑定悬停、点击、滚动和销毁事件。"""
        widget.bind('<Enter>', lambda _event: self.show(widget, text), add='+')
        widget.bind('<Leave>', lambda _event: self.hide(widget), add='+')
        widget.bind('<Button-1>', lambda _event: self.hide(widget), add='+')
        widget.bind('<Configure>', lambda _event: self.hide(widget), add='+')
        widget.bind('<Destroy>', lambda _event: self.hide(widget), add='+')

    def show(self, widget: tk.Misc, text: str) -> None:
        if not self._master_alive() or not self._widget_alive(widget):
            return
        self._anchor = widget
        if not self._ensure_window():
            return

        window = self._window
        label = self._label
        if window is None or label is None:
            return

        monitor = get_monitor_info(hwnd=self._master.winfo_id())
        label.configure(
            text=text,
            wraplength=tooltip_wraplength(self._wraplength, monitor),
        )
        window.update_idletasks()
        x, y = tooltip_position(
            (
                widget.winfo_rootx(),
                widget.winfo_rooty(),
                widget.winfo_width(),
                widget.winfo_height(),
            ),
            (window.winfo_reqwidth(), window.winfo_reqheight()),
            monitor,
        )
        window.geometry(f'+{x}+{y}')
        window.deiconify()
        window.lift()

    def hide(self, widget: tk.Misc | None = None) -> None:
        if widget is not None and widget is not self._anchor:
            return
        self._anchor = None
        if self._window is None:
            return
        if not self._window_alive():
            self._window = None
            self._label = None
            return
        with contextlib.suppress(tk.TclError):
            self._window.withdraw()

    def destroy(self) -> None:
        window = self._window
        self._window = None
        self._label = None
        self._anchor = None
        if window is not None:
            with contextlib.suppress(tk.TclError):
                window.destroy()

    def _ensure_window(self) -> bool:
        if self._window is not None and self._window_alive():
            return True

        self._window = None
        self._label = None
        try:
            window = ctk.CTkToplevel(self._master)
            window.withdraw()
            window.overrideredirect(True)
            window.attributes('-topmost', True)
            window.attributes('-alpha', 1.0)
            window.configure(fg_color=self._colors['card_hover'])

            frame = ctk.CTkFrame(
                window,
                fg_color=self._colors['card_hover'],
                border_width=1,
                border_color=self._colors['border'],
                corner_radius=8,
            )
            frame.pack(fill='both', expand=True)

            label = ctk.CTkLabel(
                frame,
                text='',
                font=ctk.CTkFont(family=self._font_family, size=12),
                text_color=self._colors['text'],
                justify='left',
                anchor='w',
                wraplength=self._wraplength,
            )
            label.pack(padx=10, pady=8)
        except tk.TclError:
            logger.warning("创建悬停提示失败", exc_info=True)
            return False

        self._window = window
        self._label = label
        return True

    def _master_alive(self) -> bool:
        try:
            return bool(self._master.winfo_exists())
        except tk.TclError:
            return False

    @staticmethod
    def _widget_alive(widget: tk.Misc) -> bool:
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _window_alive(self) -> bool:
        if self._window is None:
            return False
        try:
            return bool(self._window.winfo_exists())
        except tk.TclError:
            return False
