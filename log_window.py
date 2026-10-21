"""主日志窗口：UI 构建、窗口交互和日志泵调度。"""

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
from dpi import (
    centered_position,
    clamp_window_position,
    fit_window_with_minimum,
    format_geometry,
    get_monitor_info,
    sync_window_scaling,
)
from log_display import LogDisplay
from log_queue import BoundedLogQueue
from log_replay import LogReplay
from log_search import LogSearch
from log_store import MAX_LOG_BYTES, LogEntry, LogStore
from theme import LOGO_BAR_COLORS, LOGO_BAR_RGB
from win_utils import apply_window_blur, bind_window_drag, get_mono_font, get_ui_font

logger = logging.getLogger(__name__)

# 每条队列每轮最多处理的日志行数
MAX_LOG_LINES_PER_CYCLE = 10
# 等待渲染的日志队列上限，超出条数或字节时丢弃最旧的行
MAX_LOG_QUEUE_SIZE = 5000
# 搜索输入防抖时间（毫秒）
SEARCH_DEBOUNCE_MS = 250


class LogWindow(ctk.CTk):
    """Tk 根窗口，负责日志显示、搜索、主题切换和窗口边框交互。"""

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

        self.COLORS = config.get_theme_colors()

        config.add_theme_change_callback(self._on_theme_change)

        self.UI_FONT = get_ui_font()
        self.MONO_FONT = get_mono_font()

        self.withdraw()

        self.overrideredirect(True)

        self.title("Luker 日志")
        # 按主屏工作区和当前缩放限制初始尺寸，避免 150% 下落入任务栏
        monitor = get_monitor_info()
        scale = sync_window_scaling(self, monitor.scale)
        self._desired_min_logical_width = 700
        self._desired_min_logical_height = 450
        (
            self._min_logical_width,
            self._min_logical_height,
            self._logical_width,
            self._logical_height,
        ) = fit_window_with_minimum(
            960,
            640,
            self._desired_min_logical_width,
            self._desired_min_logical_height,
            monitor,
            scale,
            margin=24,
        )
        physical_width = round(self._logical_width * scale)
        physical_height = round(self._logical_height * scale)
        x, y = centered_position(physical_width, physical_height, monitor)
        self.geometry(format_geometry(self._logical_width, self._logical_height, x, y))
        # 最小尺寸保存为逻辑值，拖拽时按当前缩放换算
        self.minsize(self._min_logical_width, self._min_logical_height)
        # 防止 CTk 在 DPI 变化后把最大尺寸锁死为当前尺寸
        self.maxsize(10000, 10000)
        self._monitor_signature = (
            monitor.left,
            monitor.top,
            monitor.right,
            monitor.bottom,
            monitor.dpi,
        )

        self._set_window_icon()

        self.configure(fg_color=self.COLORS['bg'])
        self.attributes('-alpha', 0.97)

        self.after(150, self._setup_blur)

        self.bind('<Map>', self._on_map)

        self._resize_edge: str | None = None

        self._animation_phase = 0.0
        self._glow_intensity = 0.0
        self._glow_direction = 1

        # 日志源切换状态：'luker' 或 'gcl'
        self._log_source = 'luker'
        # 分别存储两个日志源的历史记录，容量由 LogStore 统一限制
        self._luker_store = LogStore()
        self._gcl_store = LogStore()
        self._display_dirty = False
        self._search_job: str | None = None

        self._build_ui()
        self._search_var.trace_add('write', self._on_search_change)

        self._auto_scroll = True
        self._is_running = False

        self.log_queue: BoundedLogQueue = BoundedLogQueue(MAX_LOG_QUEUE_SIZE, MAX_LOG_BYTES)
        self.gcl_log_queue: BoundedLogQueue = BoundedLogQueue(MAX_LOG_QUEUE_SIZE, MAX_LOG_BYTES)

        self._process_logs()

        self._setup_resize()

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
            if hasattr(self, '_log_source_btn'):
                self._log_source_btn.configure(
                    fg_color=self.COLORS['warning']
                    if self._log_source == 'gcl'
                    else self.COLORS['accent']
                )
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
                tb = self._get_textbox()
                tb.tag_configure('time', foreground=self.COLORS['text_muted'])
                tb.tag_configure('info', foreground=self.COLORS['info'])
                tb.tag_configure('success', foreground=self.COLORS['success'])
                tb.tag_configure('error', foreground=self.COLORS['error'])
                tb.tag_configure('warn', foreground=self.COLORS['warning'])
                tb.tag_configure('accent', foreground=self.COLORS['accent'])
                tb.tag_configure('dim', foreground=self.COLORS['text_dim'])
                tb.tag_configure('separator', foreground=self.COLORS['accent'], elide=False)

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
            colors_start = LOGO_BAR_RGB
            colors_end = [
                (0xF8, 0x71, 0x71),
                (0xFF, 0xB7, 0x4D),
                (0x22, 0xD3, 0xEE),
                (0x4A, 0xDE, 0x80),
            ]

            for i, bar in enumerate(self._logo_bars):
                phase = (self._glow_intensity + i * 0.25) % 1.0
                brightness = 0.7 + 0.3 * math.sin(phase * 2 * 3.14159)

                sr, sg, sb = colors_start[i]
                er, eg, eb = colors_end[i]
                r = int(sr + (er - sr) * brightness)
                g = int(sg + (eg - sg) * brightness)
                b = int(sb + (eb - sb) * brightness)
                bar.configure(fg_color=f"#{r:02x}{g:02x}{b:02x}")

        self.after(50, self._animate_glow)

    def _animate_status_pulse(self) -> None:
        # 窗口隐藏时降低刷新频率
        if not self.winfo_viewable():
            self.after(500, self._animate_status_pulse)
            return

        if hasattr(self, 'status_dot') and self._is_running:
            self._animation_phase = (self._animation_phase + 0.1) % (2 * 3.14159)
            alpha = 0.5 + 0.5 * math.sin(self._animation_phase)

            r = int(0x3F + (0x2E - 0x3F) * alpha)
            g = int(0xB9 + (0xA0 - 0xB9) * alpha)
            b = int(0x50 + (0x43 - 0x50) * alpha)
            pulse_color = f"#{r:02x}{g:02x}{b:02x}"

            with contextlib.suppress(tk.TclError):
                self.status_dot.configure(text_color=pulse_color)

        self.after(100, self._animate_status_pulse)

    def _setup_resize(self) -> None:
        self.bind('<Motion>', self._check_resize_edge)
        self.bind('<Button-1>', self._start_resize)
        self.bind('<B1-Motion>', self._do_resize)
        self.bind('<ButtonRelease-1>', self._end_resize)
        self.bind('<Configure>', self._on_configure)

    def _on_configure(self, event: tk.Event) -> None:
        # 合并拖动过程中连续的 Configure 事件，空闲时只检查一次显示器
        if event.widget == self:
            self.after_idle(self._fit_to_current_monitor)

    def _fit_to_current_monitor(self) -> None:
        """移动到不同 DPI 的显示器后重新限制尺寸和位置。"""
        if not self.winfo_exists() or not self.winfo_viewable():
            return

        monitor = get_monitor_info(hwnd=self.winfo_id())
        signature = (
            monitor.left,
            monitor.top,
            monitor.right,
            monitor.bottom,
            monitor.dpi,
        )
        if signature == self._monitor_signature:
            return

        self._monitor_signature = signature
        scale = sync_window_scaling(self, monitor.scale)
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
            self._desired_min_logical_width,
            self._desired_min_logical_height,
            monitor,
            scale,
            margin=24,
        )
        physical_width = round(logical_width * scale)
        physical_height = round(logical_height * scale)
        x, y = clamp_window_position(
            self.winfo_x(),
            self.winfo_y(),
            physical_width,
            physical_height,
            monitor,
        )

        self.minsize(self._min_logical_width, self._min_logical_height)
        self.maxsize(10000, 10000)
        self.geometry(format_geometry(logical_width, logical_height, x, y))
        self._logical_width = logical_width
        self._logical_height = logical_height

    def _check_resize_edge(self, e: tk.Event) -> None:
        # 距离窗口边缘 8px（按当前缩放换算）内显示缩放光标
        if e.widget != self:
            self.configure(cursor='')
            self._resize_edge = None
            return

        scale = ctk.ScalingTracker.get_window_scaling(self)
        margin = max(4, round(8 * scale))
        w, h = self.winfo_width(), self.winfo_height()
        x, y = e.x, e.y

        edge = None
        if x < margin and y < margin:
            edge = 'nw'
        elif x > w - margin and y < margin:
            edge = 'ne'
        elif x < margin and y > h - margin:
            edge = 'sw'
        elif x > w - margin and y > h - margin:
            edge = 'se'
        elif y < margin:
            edge = 'n'
        elif x < margin:
            edge = 'w'
        elif x > w - margin:
            edge = 'e'
        elif y > h - margin:
            edge = 's'

        cursors = {
            'nw': 'size_nw_se',
            'se': 'size_nw_se',
            'ne': 'size_ne_sw',
            'sw': 'size_ne_sw',
            'n': 'size_ns',
            's': 'size_ns',
            'w': 'size_we',
            'e': 'size_we',
        }

        if edge:
            self.configure(cursor=cursors.get(edge, ''))
        else:
            self.configure(cursor='')

        self._resize_edge = edge

    def _start_resize(self, e: tk.Event) -> None:
        if e.widget != self or not self._resize_edge:
            return
        self._resize_start = (
            e.x_root,
            e.y_root,
            self.winfo_width(),
            self.winfo_height(),
            self.winfo_x(),
            self.winfo_y(),
        )

    def _do_resize(self, e: tk.Event) -> None:
        if not self._resize_edge or not hasattr(self, '_resize_start'):
            return
        if e.widget != self:
            return

        sx, sy, sw, sh, wx, wy = self._resize_start
        dx = e.x_root - sx
        dy = e.y_root - sy
        scale = ctk.ScalingTracker.get_window_scaling(self)
        min_width = round(self._min_logical_width * scale)
        min_height = round(self._min_logical_height * scale)

        nw, nh, nx, ny = sw, sh, wx, wy

        if 'e' in self._resize_edge:
            nw = max(min_width, sw + dx)
        if 's' in self._resize_edge:
            nh = max(min_height, sh + dy)
        if 'w' in self._resize_edge:
            nw = max(min_width, sw - dx)
            if nw != sw:
                nx = wx + (sw - nw)
        if 'n' in self._resize_edge:
            nh = max(min_height, sh - dy)
            if nh != sh:
                ny = wy + (sh - nh)

        # 物理像素先换算回 CTk 的逻辑尺寸，避免 geometry() 再次缩放
        logical_width = max(self._min_logical_width, round(nw / scale))
        logical_height = max(self._min_logical_height, round(nh / scale))
        self.geometry(format_geometry(logical_width, logical_height, nx, ny))
        self._logical_width = logical_width
        self._logical_height = logical_height

    def _end_resize(self, e: tk.Event) -> None:
        self._resize_edge = None

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
        self._replay = LogReplay(
            schedule=self.after,
            cancel=self._cancel_after_job,
            add_entries=self._add_log_lines,
            exists=self.winfo_exists,
            on_finished=self._on_replay_finished,
        )

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
        if hasattr(self, '_minimized') and self._minimized:
            self._minimized = False
            self.lift()
            self.focus_force()
        # 显示/恢复后再检查一次，处理隐藏期间切换显示器的情况
        self.after_idle(self._fit_to_current_monitor)

    def _check_window_state(self) -> None:
        with contextlib.suppress(Exception):
            hwnd = windll.user32.GetParent(self.winfo_id())
            is_minimized = windll.user32.IsIconic(hwnd)

            if getattr(self, '_was_minimized', False) and not is_minimized:
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
            pass

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

        ctk.CTkLabel(
            search_inner, text="🔍", font=ctk.CTkFont(size=14), text_color=self.COLORS['text_muted']
        ).pack(side="left", padx=(4, 4))

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
            hover_color="#2ea043",
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

        tb = self._get_textbox()
        tb.tag_configure('time', foreground=self.COLORS['text_muted'])
        tb.tag_configure('info', foreground=self.COLORS['info'])
        tb.tag_configure('success', foreground=self.COLORS['success'])
        tb.tag_configure('error', foreground=self.COLORS['error'])
        tb.tag_configure('warn', foreground=self.COLORS['warning'])
        tb.tag_configure('accent', foreground=self.COLORS['accent'])
        tb.tag_configure('dim', foreground=self.COLORS['text_dim'])
        tb.tag_configure('separator', foreground=self.COLORS['accent'], elide=False)

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

    def _enqueue_log(self, log_queue: BoundedLogQueue, line: str) -> None:
        """入队；超出限行或限字节时由队列丢弃最旧的一行。"""
        log_queue.put(line)

    def add_log(self, line: str) -> None:
        """添加 Luker 日志。"""
        self._enqueue_log(self.log_queue, line)

    def add_gcl_log(self, line: str) -> None:
        """添加 GCL 日志的便捷方法"""
        self._enqueue_log(self.gcl_log_queue, line)

    def _drain_log_queue(
        self,
        log_queue: BoundedLogQueue,
        log_store: LogStore,
        source: str,
    ) -> None:
        """从队列取一批日志写入存储；仅当前日志源且窗口可见时渲染。"""
        entries = []
        for _ in range(MAX_LOG_LINES_PER_CYCLE):
            line = log_queue.get_nowait()
            if line is None:
                break

            entry = log_store.append(line)
            if self._log_source == source:
                if self._replay.active:
                    # 重放的是开始时的快照，新日志留到快照结束后再插入
                    self._replay.append(entry)
                else:
                    entries.append(entry)

        if not entries:
            return

        if self.winfo_viewable():
            self._add_log_lines(entries)
        else:
            # 隐藏时只存不渲染，显示时分批补上
            self._display_dirty = True

    def _process_logs(self) -> None:
        if self._display_dirty and self.winfo_viewable():
            self._refresh_log_display()

        # 两个队列各自限额，避免一个日志源刷屏时另一个被饿死
        self._drain_log_queue(self.log_queue, self._luker_store, 'luker')
        self._drain_log_queue(self.gcl_log_queue, self._gcl_store, 'gcl')

        if not self.log_queue.empty() or not self.gcl_log_queue.empty():
            self.after(10, self._process_logs)
        else:
            # 隐藏到托盘时降低轮询频率
            self.after(100 if self.winfo_viewable() else 500, self._process_logs)

    def _toggle_log_source(self) -> None:
        """切换日志源"""
        if self._log_source == 'luker':
            self._log_source = 'gcl'
            self._log_source_btn.configure(text="🚀 GCL 日志", fg_color=self.COLORS['warning'])
            self._title_label.configure(text="GCL 日志")
        else:
            self._log_source = 'luker'
            self._log_source_btn.configure(text="📊 Luker 日志", fg_color=self.COLORS['accent'])
            self._title_label.configure(text="Luker 日志")

        self._refresh_log_display()

    def _cancel_after_job(self, job: str) -> None:
        """取消 Tk after 任务；任务已执行时忽略 TclError。"""
        with contextlib.suppress(tk.TclError):
            self.after_cancel(job)

    def _on_replay_finished(self) -> None:
        """重放结束；有搜索词时重建高亮。"""
        self._display_dirty = False
        if self._search_var.get().strip():
            self._run_search()

    def _refresh_log_display(self) -> None:
        """刷新日志显示，按批插入历史，避免阻塞 Tk 主线程。"""
        if self._search_job is not None:
            self.after_cancel(self._search_job)
            self._search_job = None

        self._replay.cancel()
        self._search.clear_state()

        tb = self._get_textbox()
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")

        self._display.reset()
        self._display_dirty = False

        # 只重放当前日志源，容量由 LogStore 限制
        store = self._luker_store if self._log_source == 'luker' else self._gcl_store
        logs = store.snapshot()
        if not logs:
            if self._search_var.get().strip():
                self._run_search()
            return

        self._replay.start(logs)

    def set_gcl_enabled(self, enabled: bool) -> None:
        """设置 GCL 功能是否启用，控制切换按钮的显示"""
        if enabled:
            self._log_source_btn.pack(side="left", padx=2, before=self._min_btn)
        else:
            self._log_source_btn.pack_forget()
            # 如果当前显示的是 GCL 日志，切换回 Luker 日志
            if self._log_source == 'gcl':
                self._log_source = 'luker'
                self._log_source_btn.configure(text="📊 Luker 日志", fg_color=self.COLORS['accent'])
                self._title_label.configure(text="Luker 日志")
                self._refresh_log_display()

    def _add_log_lines(self, entries: Sequence[LogEntry]) -> None:
        """批量插入日志，并在裁剪后同步搜索结果位置。"""
        removed_lines = self._display.add_entries(entries, auto_scroll=self._auto_scroll)
        if removed_lines:
            self._search.adjust(removed_lines)

    def clear_logs(self) -> None:
        self._replay.cancel()
        tb = self._get_textbox()
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")

        # 同步清空底层存储，否则切换日志源后已清除的内容会重新出现
        self._luker_store.clear()
        self._gcl_store.clear()
        self._display.reset()

        # 丢弃尚未处理的日志，避免清除后旧日志又冒出来
        for log_queue in (self.log_queue, self.gcl_log_queue):
            log_queue.clear()

        self._display_dirty = False

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
            self.play_btn.configure(text="⏸", fg_color=self.COLORS['error'], hover_color="#da3633")
        else:
            self.status_dot.configure(text_color=self.COLORS['error'])
            self.status_text.configure(text="已停止", text_color=self.COLORS['error'])
            self.play_btn.configure(
                text="▶", fg_color=self.COLORS['success'], hover_color="#2ea043"
            )

    def show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        # 隐藏期间只存不渲染，显示时分批补上
        if self._display_dirty and not self._replay.active:
            self._refresh_log_display()

    def hide(self) -> None:
        if self._replay.active:
            # 显示到一半被隐藏，下次显示时重新构建
            self._display_dirty = True
        self._replay.cancel()
        self.withdraw()

    def is_visible(self) -> bool:
        return self.winfo_viewable()

    # ===== 搜索功能 =====

    def _on_search_change(self, *args: str) -> None:
        """输入时防抖，避免每敲一个字都对全部日志重新搜索。"""
        if self._search_job is not None:
            self.after_cancel(self._search_job)
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

    def _adjust_search_positions(self, removed_lines: int) -> None:
        """文本头部被裁剪后，同步平移已保存的搜索结果位置。"""
        self._search.adjust(removed_lines)

    def _search_next(self) -> None:
        """跳转到下一个搜索结果"""
        self._search.next()

    def _search_prev(self) -> None:
        """跳转到上一个搜索结果"""
        self._search.prev()

    def _clear_search(self) -> None:
        """清除搜索"""
        if self._search_job is not None:
            self.after_cancel(self._search_job)
            self._search_job = None
        self._search_var.set("")
        self._search.clear_state()
        self._search_entry.focus_set()
