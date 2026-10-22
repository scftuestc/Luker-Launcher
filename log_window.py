"""主日志窗口：UI 构建、主题切换和日志泵调度。"""

import contextlib
import logging
import math
import os
import tkinter as tk
from collections.abc import Callable, Sequence
from ctypes import windll
from types import TracebackType

import customtkinter as ctk

from config import APP_VERSION, config
from log_controller import LogController
from log_display import LogDisplay
from log_search import LogSearch
from log_store import LogEntry
from log_tags import configure_log_tags
from theme import (
    LOGO_BAR_COLORS,
    LOGO_BAR_GLOW_RGB,
    LOGO_BAR_RGB,
    blend_color,
    logo_bar_brightness,
    shade_color,
)
from win_utils import apply_window_blur, bind_window_drag, get_mono_font, get_ui_font
from window_resize import WindowResizer

logger = logging.getLogger(__name__)

# 搜索输入防抖时间（毫秒）
SEARCH_DEBOUNCE_MS = 250


class LogWindow(ctk.CTk):
    """Tk 根窗口，负责日志显示、搜索和主题切换；几何由 WindowResizer 管理。"""

    def __init__(
        self,
        on_hide_callback: Callable[[], None] | None = None,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()

        # Tk 回调里的未捕获异常默认只打印到不可见的 stderr，
        # 交给 logging 写入文件（并在日志窗口显示警告/错误）
        self.report_callback_exception = self._report_callback_exception

        self.on_hide_callback = on_hide_callback
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self._tray_available = True
        # 最小化状态同时用于 <Map> 恢复和托盘点击的状态同步
        self._minimized = False
        self._was_minimized = False
        self._icon_photo: object | None = None

        self.COLORS = config.get_theme_colors()

        config.add_theme_change_callback(self._on_theme_change)

        self.UI_FONT = get_ui_font()
        self.MONO_FONT = get_mono_font()

        self.withdraw()

        self.overrideredirect(True)

        self.title("Luker 日志")
        # 按主屏工作区和当前缩放限制初始尺寸，避免 150% 下落入任务栏
        self._resizer = WindowResizer(self)
        self._resizer.apply_initial_geometry()

        self._set_window_icon()

        self.configure(fg_color=self.COLORS['bg'])
        self.attributes('-alpha', 0.97)

        self.after(150, self._setup_blur)

        self.bind('<Map>', self._on_map)

        self._animation_phase = 0.0
        self._glow_intensity = 0.0
        self._glow_direction = 1

        self._search_job: str | None = None

        self._build_ui()
        self._search_var.trace_add('write', self._on_search_change)

        self._auto_scroll = True
        self._is_running = False

        self._logs.start()

        self._resizer.bind_events()

        self._check_window_state()

        self._start_animations()

    def _report_callback_exception(
        self,
        exc: type[BaseException],
        val: BaseException,
        tb: TracebackType | None,
    ) -> None:
        logger.error("界面回调异常", exc_info=(exc, val, tb))

    def _set_window_icon(self) -> None:
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            else:
                png_path = os.path.join(os.path.dirname(__file__), 'icon.png')
                if os.path.exists(png_path):
                    from PIL import Image, ImageTk

                    img = Image.open(png_path)
                    photo = ImageTk.PhotoImage(img)
                    self.iconphoto(True, photo)
                    self._icon_photo = photo
        except Exception:
            logger.warning("设置窗口图标失败", exc_info=True)

    def _setup_blur(self) -> None:
        apply_window_blur(self, self.COLORS['bg'], alpha=0xDD, context="日志窗口")
        self.update()

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        self.COLORS = new_colors
        self._apply_theme()

    def _apply_theme(self) -> None:
        try:
            self.configure(fg_color=self.COLORS['bg'])

            self._setup_blur()

            if hasattr(self, '_titlebar'):
                self._titlebar.configure(fg_color=self.COLORS['card'])
            if hasattr(self, '_title_label'):
                self._title_label.configure(text_color=self.COLORS['text'])
            if (
                hasattr(self, '_log_source_btn')
                and hasattr(self, '_title_label')
                and hasattr(self, '_logs')
            ):
                self._apply_log_source_ui()
            if hasattr(self, '_min_btn'):
                self._min_btn.configure(
                    hover_color=self.COLORS['card_hover'], text_color=self.COLORS['text_dim']
                )
            if hasattr(self, '_close_btn'):
                self._close_btn.configure(
                    hover_color=self.COLORS['error'], text_color=self.COLORS['text_dim']
                )

            if hasattr(self, '_clear_btn'):
                self._clear_btn.configure(
                    fg_color=self.COLORS['card'],
                    hover_color=self.COLORS['card_hover'],
                    text_color=self.COLORS['text'],
                )
            if hasattr(self, 'scroll_btn'):
                self.scroll_btn.configure(
                    fg_color=self.COLORS['card'],
                    hover_color=self.COLORS['card_hover'],
                    text_color=self.COLORS['text'],
                )

            if hasattr(self, '_search_frame'):
                self._search_frame.configure(fg_color=self.COLORS['card'])
            if hasattr(self, '_search_icon'):
                self._search_icon.configure(text_color=self.COLORS['text_muted'])
            if hasattr(self, '_search_entry'):
                self._search_entry.configure(
                    text_color=self.COLORS['text'], placeholder_text_color=self.COLORS['text_muted']
                )
            if hasattr(self, '_search_count_label'):
                self._search_count_label.configure(text_color=self.COLORS['text_muted'])
            if hasattr(self, '_search_prev_btn'):
                self._search_prev_btn.configure(
                    hover_color=self.COLORS['card_hover'], text_color=self.COLORS['text_dim']
                )
            if hasattr(self, '_search_next_btn'):
                self._search_next_btn.configure(
                    hover_color=self.COLORS['card_hover'], text_color=self.COLORS['text_dim']
                )
            if hasattr(self, '_search_clear_btn'):
                self._search_clear_btn.configure(
                    hover_color=self.COLORS['error'], text_color=self.COLORS['text_dim']
                )

            if hasattr(self, '_status_card'):
                self._status_card.configure(fg_color=self.COLORS['card'])

            if hasattr(self, '_log_card'):
                self._log_card.configure(fg_color=self.COLORS['card'])
            if hasattr(self, 'log_text'):
                self.log_text.configure(
                    text_color=self.COLORS['text'],
                    scrollbar_button_color=self.COLORS['border'],
                    scrollbar_button_hover_color=self.COLORS['accent'],
                )
                configure_log_tags(self._get_textbox(), self.COLORS)
                if hasattr(self, '_search'):
                    self._search.refresh_colors()

            if hasattr(self, '_statusbar'):
                self._statusbar.configure(fg_color=self.COLORS['card'])
            if hasattr(self, 'count_label'):
                self.count_label.configure(text_color=self.COLORS['text_muted'])
            if hasattr(self, '_version_label'):
                self._version_label.configure(text_color=self.COLORS['text_muted'])

            self.update_status(self._is_running)

        except Exception:
            logger.exception("应用主题时出错")

    def _start_animations(self) -> None:
        self._animate_glow()
        self._animate_status_pulse()

    def _animate_glow(self) -> None:
        # 窗口隐藏时降低刷新频率，避免常驻托盘时空转
        if not self.winfo_viewable():
            self.after(500, self._animate_glow)
            return

        self._glow_intensity += 0.03 * self._glow_direction
        if self._glow_intensity >= 1:
            self._glow_direction = -1
        elif self._glow_intensity <= 0:
            self._glow_direction = 1

        if hasattr(self, '_logo_bars'):
            for index, bar in enumerate(self._logo_bars):
                brightness = logo_bar_brightness(index, self._glow_intensity)
                bar.configure(
                    fg_color=blend_color(
                        LOGO_BAR_RGB[index],
                        LOGO_BAR_GLOW_RGB[index],
                        brightness,
                    )
                )

        self.after(50, self._animate_glow)

    def _animate_status_pulse(self) -> None:
        # 窗口隐藏时降低刷新频率
        if not self.winfo_viewable():
            self.after(500, self._animate_status_pulse)
            return

        if hasattr(self, 'status_dot') and self._is_running:
            self._animation_phase = (self._animation_phase + 0.1) % (2 * 3.14159)
            alpha = 0.5 + 0.5 * math.sin(self._animation_phase)
            pulse_color = shade_color(self.COLORS['success'], 1.0 - 0.25 * alpha)

            with contextlib.suppress(tk.TclError):
                self.status_dot.configure(text_color=pulse_color)

        self.after(100, self._animate_status_pulse)

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_titlebar(main)
        self._build_toolbar(main)
        self._build_log_area(main)
        self._build_statusbar(main)

        self._search = LogSearch(
            self._get_textbox,
            self._search_count_label,
            self._search_nav,
            lambda: self.COLORS,
        )
        self._display = LogDisplay(self._get_textbox, self.count_label)
        self._logs = LogController(
            schedule=self.after,
            cancel=self._cancel_after_job,
            exists=self.winfo_exists,
            viewable=self.winfo_viewable,
            reset_display=self._reset_log_display,
            add_entries=self._add_log_lines,
            adjust_search=self._search.adjust,
            has_query=lambda: bool(self._search_var.get().strip()),
            on_search_rerun=self._run_search,
        )
        self._apply_log_source_ui()

    def _build_titlebar(self, parent: tk.Misc) -> None:
        self._titlebar = ctk.CTkFrame(
            parent, height=52, fg_color=self.COLORS['card'], corner_radius=14
        )
        self._titlebar.pack(fill="x", pady=(0, 10))
        self._titlebar.pack_propagate(False)

        left = ctk.CTkFrame(self._titlebar, fg_color="transparent")
        left.pack(side="left", padx=16, pady=12)

        logo = ctk.CTkFrame(left, fg_color="transparent")
        logo.pack(side="left")

        self._logo_bars = []
        for c in LOGO_BAR_COLORS:
            bar_item = ctk.CTkFrame(logo, width=4, height=22, fg_color=c, corner_radius=2)
            bar_item.pack(side="left", padx=1)
            self._logo_bars.append(bar_item)

        self._title_label = ctk.CTkLabel(
            left,
            text="Luker 日志",
            font=ctk.CTkFont(family=self.UI_FONT, size=16, weight="bold"),
            text_color=self.COLORS['text'],
        )
        self._title_label.pack(side="left", padx=(14, 0))

        bind_window_drag(self, self._titlebar, left, logo, self._title_label)

        right = ctk.CTkFrame(self._titlebar, fg_color="transparent")
        right.pack(side="right", padx=10)

        # 日志源切换按钮（仅在 GCL 启用时显示）
        self._log_source_btn = ctk.CTkButton(
            right,
            text="📊 Luker 日志",
            width=110,
            height=32,
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            corner_radius=8,
            command=self._toggle_log_source,
        )

        self._min_btn = ctk.CTkButton(
            right,
            text="─",
            width=40,
            height=32,
            fg_color="transparent",
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_dim'],
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=8,
            command=self._on_minimize,
        )
        self._min_btn.pack(side="left", padx=2)

        self._close_btn = ctk.CTkButton(
            right,
            text="✕",
            width=40,
            height=32,
            fg_color="transparent",
            hover_color=self.COLORS['error'],
            text_color=self.COLORS['text_dim'],
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=8,
            command=self._on_close,
        )
        self._close_btn.pack(side="left", padx=2)

    def _on_minimize(self) -> None:
        if not self._tray_available:
            return

        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            SW_MINIMIZE = 6
            windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
            self._minimized = True
            # 同步托盘状态，避免下一次左键点击先执行“隐藏”
            if self.on_hide_callback:
                self.on_hide_callback()
        except Exception:
            logger.warning("最小化窗口失败", exc_info=True)

    def _on_map(self, event: tk.Event) -> None:
        if self._minimized:
            self._minimized = False
            self.lift()
            self.focus_force()
        # 显示/恢复后再检查一次，处理隐藏期间切换显示器的情况
        self.after_idle(self._resizer.fit_to_current_monitor)

    def _check_window_state(self) -> None:
        with contextlib.suppress(Exception):
            hwnd = windll.user32.GetParent(self.winfo_id())
            is_minimized = windll.user32.IsIconic(hwnd)

            if self._was_minimized and not is_minimized:
                self.after(50, self._restore_window)

            self._was_minimized = is_minimized

        # 隐藏到托盘时降到 1 秒一次，减少空转
        interval = 300 if self.winfo_viewable() else 1000
        self.after(interval, self._check_window_state)

    def _restore_window(self) -> None:
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            SW_RESTORE = 9
            windll.user32.ShowWindow(hwnd, SW_RESTORE)
            self.lift()
            self.focus_force()
        except Exception:
            logger.warning("恢复窗口失败", exc_info=True)

    def _on_close(self) -> None:
        if not self._tray_available:
            # 没有托盘时不能隐藏到不可恢复的位置，交给主程序退出
            if self.on_hide_callback:
                self.on_hide_callback()
            return

        self.hide()
        if self.on_hide_callback:
            self.on_hide_callback()

    def set_tray_available(self, available: bool) -> None:
        """托盘不可用时禁用最小化，避免窗口隐藏后无法恢复。"""
        self._tray_available = available
        if not available:
            self._min_btn.configure(state="disabled")

    def _build_toolbar(self, parent: tk.Misc) -> None:
        self._toolbar = ctk.CTkFrame(parent, fg_color="transparent", height=48)
        self._toolbar.pack(fill="x", pady=(0, 10))

        left = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        left.pack(side="left")

        self._clear_btn = ctk.CTkButton(
            left,
            text="🗑️ 清除",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            fg_color=self.COLORS['card'],
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text'],
            corner_radius=10,
            width=100,
            height=40,
            command=self.clear_logs,
        )
        self._clear_btn.pack(side="left", padx=(0, 8))

        self.scroll_btn = ctk.CTkButton(
            left,
            text="📜 自动滚动",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            fg_color=self.COLORS['card'],
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text'],
            corner_radius=10,
            width=130,
            height=40,
            command=self._toggle_scroll,
        )
        self.scroll_btn.pack(side="left", padx=(0, 8))

        # 搜索框与结果导航
        self._search_frame = ctk.CTkFrame(left, fg_color=self.COLORS['card'], corner_radius=10)
        self._search_frame.pack(side="left")

        search_inner = ctk.CTkFrame(self._search_frame, fg_color="transparent")
        search_inner.pack(padx=8, pady=4)

        self._search_icon = ctk.CTkLabel(
            search_inner, text="🔍", font=ctk.CTkFont(size=14), text_color=self.COLORS['text_muted']
        )
        self._search_icon.pack(side="left", padx=(4, 4))

        self._search_var = ctk.StringVar()

        self._search_entry = ctk.CTkEntry(
            search_inner,
            placeholder_text="搜索日志...",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            fg_color="transparent",
            border_width=0,
            text_color=self.COLORS['text'],
            placeholder_text_color=self.COLORS['text_muted'],
            width=150,
            height=32,
            textvariable=self._search_var,
        )
        self._search_entry.pack(side="left")

        self._search_nav = ctk.CTkFrame(search_inner, fg_color="transparent")
        self._search_nav.pack(side="left", padx=(4, 0))

        self._search_count_label = ctk.CTkLabel(
            self._search_nav,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=11),
            text_color=self.COLORS['text_muted'],
            width=50,
        )
        self._search_count_label.pack(side="left")

        self._search_prev_btn = ctk.CTkButton(
            self._search_nav,
            text="▲",
            width=24,
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_dim'],
            corner_radius=4,
            command=self._search_prev,
        )
        self._search_prev_btn.pack(side="left", padx=1)

        self._search_next_btn = ctk.CTkButton(
            self._search_nav,
            text="▼",
            width=24,
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_dim'],
            corner_radius=4,
            command=self._search_next,
        )
        self._search_next_btn.pack(side="left", padx=1)

        self._search_clear_btn = ctk.CTkButton(
            self._search_nav,
            text="✕",
            width=24,
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=self.COLORS['error'],
            text_color=self.COLORS['text_dim'],
            corner_radius=4,
            command=self._clear_search,
        )
        self._search_clear_btn.pack(side="left", padx=1)

        self._search_nav.pack_forget()

        right = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        right.pack(side="right")

        self._status_card = ctk.CTkFrame(right, fg_color=self.COLORS['card'], corner_radius=10)
        self._status_card.pack()

        inner = ctk.CTkFrame(self._status_card, fg_color="transparent")
        inner.pack(padx=16, pady=10)

        self.play_btn = ctk.CTkButton(
            inner,
            text="▶",
            width=36,
            height=36,
            font=ctk.CTkFont(size=16),
            fg_color=self.COLORS['success'],
            hover_color=shade_color(self.COLORS['success'], 0.85),
            text_color="#ffffff",
            corner_radius=18,
            command=self._toggle_running,
        )
        self.play_btn.pack(side="left", padx=(0, 12))

        self.status_dot = ctk.CTkLabel(
            inner, text="●", font=ctk.CTkFont(size=18), text_color=self.COLORS['error']
        )
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_text = ctk.CTkLabel(
            inner,
            text="已停止",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['error'],
        )
        self.status_text.pack(side="left")

    def _build_log_area(self, parent: tk.Misc) -> None:
        self._log_card = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=14)
        self._log_card.pack(fill="both", expand=True, pady=(0, 10))

        self.log_text = ctk.CTkTextbox(
            self._log_card,
            fg_color="transparent",
            text_color=self.COLORS['text'],
            font=ctk.CTkFont(family=self.MONO_FONT, size=13),
            corner_radius=10,
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent'],
        )
        self.log_text.pack(fill="both", expand=True, padx=12, pady=12)

        configure_log_tags(self._get_textbox(), self.COLORS)

    def _get_textbox(self) -> tk.Text:
        """返回 CTkTextbox 内部的 Text 控件；私有属性只在这里访问。"""
        return self.log_text._textbox

    def _build_statusbar(self, parent: tk.Misc) -> None:
        self._statusbar = ctk.CTkFrame(
            parent, height=42, fg_color=self.COLORS['card'], corner_radius=10
        )
        self._statusbar.pack(fill="x")
        self._statusbar.pack_propagate(False)

        self.count_label = ctk.CTkLabel(
            self._statusbar,
            text="📝 0 条日志",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text_muted'],
        )
        self.count_label.pack(side="left", padx=16, pady=10)

        self._version_label = ctk.CTkLabel(
            self._statusbar,
            text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text_muted'],
        )
        self._version_label.pack(side="right", padx=16, pady=10)

    def add_log(self, line: str) -> None:
        """添加 Luker 日志。"""
        self._logs.add_log(line)

    def add_gcl_log(self, line: str) -> None:
        """添加 GCL 日志。"""
        self._logs.add_gcl_log(line)

    def _toggle_log_source(self) -> None:
        """切换日志源"""
        self._logs.toggle_source()
        self._apply_log_source_ui()

    def _apply_log_source_ui(self) -> None:
        """按当前日志源更新切换按钮和标题。"""
        if self._logs.source == 'gcl':
            text, color, title = "🚀 GCL 日志", self.COLORS['warning'], "GCL 日志"
        else:
            text, color, title = "📊 Luker 日志", self.COLORS['accent'], "Luker 日志"

        self._log_source_btn.configure(
            text=text,
            fg_color=color,
            hover_color=self.COLORS['card_hover'],
        )
        self._title_label.configure(text=title)

    def _cancel_after_job(self, job: str) -> None:
        """取消 Tk after 任务；任务已执行时忽略 TclError。"""
        with contextlib.suppress(tk.TclError):
            self.after_cancel(job)

    def _reset_log_display(self) -> None:
        """清空文本和搜索状态，供 LogController 重建显示。"""
        if self._search_job is not None:
            self._cancel_after_job(self._search_job)
            self._search_job = None
        self._search.clear_state()

        tb = self._get_textbox()
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")
        self._display.reset()

    def set_gcl_enabled(self, enabled: bool) -> None:
        """设置 GCL 功能是否启用，控制切换按钮的显示"""
        if enabled:
            self._log_source_btn.pack(side="left", padx=2, before=self._min_btn)
        else:
            self._log_source_btn.pack_forget()
            self._logs.set_gcl_enabled(False)
            self._apply_log_source_ui()

    def _add_log_lines(self, entries: Sequence[LogEntry]) -> int:
        """批量插入日志，返回被裁剪的文本行数。"""
        return self._display.add_entries(entries, auto_scroll=self._auto_scroll)

    def clear_logs(self) -> None:
        self._logs.clear()
        self._clear_search()

    def _toggle_scroll(self) -> None:
        self._auto_scroll = not self._auto_scroll
        self.scroll_btn.configure(text="📜 自动滚动" if self._auto_scroll else "📜 已暂停")

    def _toggle_running(self) -> None:
        if self._is_running:
            if self.on_stop_callback:
                self.on_stop_callback()
        else:
            if self.on_start_callback:
                self.on_start_callback()

    def update_status(self, is_running: bool) -> None:
        self._is_running = is_running
        if is_running:
            self.status_dot.configure(text_color=self.COLORS['success'])
            self.status_text.configure(text="运行中", text_color=self.COLORS['success'])
            self.play_btn.configure(
                text="⏸",
                fg_color=self.COLORS['error'],
                hover_color=shade_color(self.COLORS['error'], 0.85),
            )
        else:
            self.status_dot.configure(text_color=self.COLORS['error'])
            self.status_text.configure(text="已停止", text_color=self.COLORS['error'])
            self.play_btn.configure(
                text="▶",
                fg_color=self.COLORS['success'],
                hover_color=shade_color(self.COLORS['success'], 0.85),
            )

    def show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self._logs.on_show()

    def hide(self) -> None:
        self._logs.on_hide()
        self.withdraw()

    def is_visible(self) -> bool:
        return self.winfo_viewable()

    # ===== 搜索功能 =====

    def _on_search_change(self, *args: str) -> None:
        """输入时防抖，避免每敲一个字都对全部日志重新搜索。"""
        if self._search_job is not None:
            self._cancel_after_job(self._search_job)
            self._search_job = None

        if not self._search_var.get().strip():
            self._search.clear_state()
            return

        self._search_job = self.after(SEARCH_DEBOUNCE_MS, self._run_search)

    def _run_search(self) -> None:
        """执行搜索并显示结果导航。"""
        self._search_job = None
        search_text = self._search_var.get().strip()
        if not search_text:
            self._search.clear_state()
            return

        self._search_nav.pack(side="left", padx=(4, 0))

        self._search.perform(search_text)

    def _search_next(self) -> None:
        """跳转到下一个搜索结果"""
        self._search.next()

    def _search_prev(self) -> None:
        """跳转到上一个搜索结果"""
        self._search.prev()

    def _clear_search(self) -> None:
        """清除搜索"""
        if self._search_job is not None:
            self._cancel_after_job(self._search_job)
            self._search_job = None
        self._search_var.set("")
        self._search.clear_state()
        self._search_entry.focus_set()
