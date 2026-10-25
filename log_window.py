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
from log.display import LogDisplay, configure_log_tags
from log.pipeline import LogController
from log.search import SearchBar
from log.store import LogEntry
from luker_readiness import LukerState
from ui.buttons import ButtonRole, button_colors, make_button
from ui.icons import TransportIcon, toolbar_icon, transport_icon
from ui.theme import (
    LOGO_GLOW_INTERVAL_MS,
    LOGO_GLOW_STEP,
    LOGO_STOPPED_COLOR,
    ThemeColorKey,
    logo_bar_glow_color,
    shade_color,
)
from win_utils import (
    apply_window_rounding,
    bind_window_drag,
    get_mono_font,
    get_ui_font,
    sync_window_blur,
)
from window_resize import WindowResizer

logger = logging.getLogger(__name__)

# Luker 三态对应的状态点、文字、播放按钮和 logo 表现
_STATUS_PRESENTATION: dict[LukerState, tuple[str, str, str, TransportIcon, str, bool]] = {
    LukerState.READY: ('success', '运行中', 'success', 'stop', 'error', False),
    LukerState.STARTING: ('warning', '启动中', 'warning', 'stop', 'error', True),
    LukerState.STOPPED: ('error', '已停止', 'error', 'play', 'success', True),
}


class LogWindow(ctk.CTk):
    """Tk 根窗口，负责日志显示、搜索和主题切换；几何由 WindowResizer 管理。"""

    def __init__(
        self,
        on_hide_callback: Callable[[], None] | None = None,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()

        # Tk 回调里的未捕获异常默认只打印到不可见的 stderr，
        # 交给 logging 写入文件（并在日志窗口显示警告/错误）
        self.report_callback_exception = self._report_callback_exception

        self._init_callbacks(on_hide_callback, on_start, on_stop, on_exit)
        self._init_theme()
        self._init_window()
        self._init_runtime_state()

        self._build_ui()
        self._ui_ready = True
        self._logs.start()
        self._resizer.bind_events()

        self._check_window_state()
        self._start_animations()

    def _init_callbacks(
        self,
        on_hide: Callable[[], None] | None,
        on_start: Callable[[], None] | None,
        on_stop: Callable[[], None] | None,
        on_exit: Callable[[], None] | None,
    ) -> None:
        self.on_hide_callback = on_hide
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self.on_exit_callback = on_exit
        self._tray_available = True
        # 记录系统级最小化，恢复到前台时重新聚焦
        self._was_minimized = False
        self._icon_photo: object | None = None
        self._play_icon: ctk.CTkImage | None = None

        # 控件创建时登记主题选项，主题切换只遍历这一份绑定
        self._theme_bindings: list[tuple[tk.Misc, dict[str, ThemeColorKey]]] = []
        # 按钮按角色登记，主题切换时统一重算颜色和描边
        self._styled_buttons: list[tuple[ctk.CTkButton, ButtonRole]] = []
        self._ui_ready = False

    def _init_theme(self) -> None:
        self.COLORS = config.get_theme_colors()
        config.add_theme_change_callback(self._on_theme_change)
        config.add_blur_change_callback(self._on_blur_change)
        self.UI_FONT = get_ui_font()
        self.MONO_FONT = get_mono_font()

    def _init_window(self) -> None:
        self.withdraw()

        self.overrideredirect(True)
        apply_window_rounding(self, context="日志窗口")

        self.title("Luker 日志")
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.bind('<Alt-F4>', lambda _event: self._on_close())
        # 按主屏工作区和当前缩放限制初始尺寸，避免 150% 下落入任务栏
        self._resizer = WindowResizer(self)
        self._resizer.apply_initial_geometry()

        self._set_window_icon()

        self.configure(fg_color=self.COLORS['bg'])
        self.attributes('-alpha', 0.95 if config.blur_enabled else 1.0)

        self.after(150, self._setup_blur)

        self.bind('<Map>', self._on_map)

    def _init_runtime_state(self) -> None:
        self._pulse_phase = 0.0
        self._glow_phase = 0.0
        self._glow_job: str | None = None
        self._pulse_job: str | None = None

        self._auto_scroll = True

        self._is_running = False
        self._luker_state = LukerState.STOPPED
        self._logo_is_gray = True

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
        sync_window_blur(
            self,
            self.COLORS['bg'],
            enabled=config.blur_enabled,
            window_alpha=0.95,
            tint_alpha=0xDD,
            context="日志窗口",
        )
        self.update()

    def _on_blur_change(self, _enabled: bool) -> None:
        self._setup_blur()

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        self.COLORS = new_colors
        self._apply_theme()

    def _bind_theme(self, widget: tk.Misc, **options: ThemeColorKey) -> None:
        """登记控件在主题切换时需要更新的选项，值为 COLORS 的键名。"""
        self._theme_bindings.append((widget, options))

    def _register_button(self, button: ctk.CTkButton, role: ButtonRole) -> ctk.CTkButton:
        """登记按钮角色，主题切换时按新颜色重算。"""
        self._styled_buttons.append((button, role))
        return button

    def _apply_theme(self) -> None:
        if not self._ui_ready:
            return
        try:
            self.configure(fg_color=self.COLORS['bg'])

            self._setup_blur()

            for widget, options in self._theme_bindings:
                widget.configure(**{option: self.COLORS[key] for option, key in options.items()})

            for button, role in self._styled_buttons:
                button.configure(**button_colors(role, self.COLORS))

            self._refresh_toolbar_icons()

            # 动态状态依赖静态颜色，必须放在绑定之后
            self._apply_log_source_ui()
            configure_log_tags(self._get_textbox(), self.COLORS)
            self.search.refresh_colors()
            self.update_status(self._luker_state)

        except Exception:
            logger.exception("应用主题时出错")

    def _start_animations(self) -> None:
        self._animate_glow()
        self._animate_status_pulse()

    def _restart_glow(self) -> None:
        """窗口显示时立即接上呼吸链，不必等隐藏期间的 500ms 轮询。"""
        if self._glow_job is not None:
            self._cancel_after_job(self._glow_job)
            self._glow_job = None
        self._animate_glow()

    def _set_logo_stopped(self) -> None:
        if self._logo_is_gray:
            return
        for bar in self._logo_bars:
            bar.configure(fg_color=LOGO_STOPPED_COLOR)
        self._logo_is_gray = True

    def _animate_glow(self) -> None:
        self._glow_job = None
        # 窗口隐藏时降低刷新频率，避免常驻托盘时空转
        if not self.winfo_viewable():
            self._glow_job = self.after(500, self._animate_glow)
            return

        # 启动中/已停止不播放呼吸，只保留灰色静止状态
        if self._luker_state is not LukerState.READY:
            self._set_logo_stopped()
            self._glow_job = self.after(300, self._animate_glow)
            return

        self._logo_is_gray = False
        self._glow_phase = (self._glow_phase + LOGO_GLOW_STEP) % 1.0

        for index, bar in enumerate(self._logo_bars):
            bar.configure(fg_color=logo_bar_glow_color(index, self._glow_phase))

        self._glow_job = self.after(LOGO_GLOW_INTERVAL_MS, self._animate_glow)

    def _animate_status_pulse(self) -> None:
        self._pulse_job = None
        # 窗口隐藏时降低刷新频率
        if not self.winfo_viewable():
            self._pulse_job = self.after(500, self._animate_status_pulse)
            return

        if self._luker_state is LukerState.READY:
            self._pulse_phase = (self._pulse_phase + 0.1) % (2 * math.pi)
            alpha = 0.5 + 0.5 * math.sin(self._pulse_phase)
            pulse_color = shade_color(self.COLORS['success'], 1.0 - 0.25 * alpha)

            with contextlib.suppress(tk.TclError):
                self.status_dot.configure(text_color=pulse_color)

        self._pulse_job = self.after(100, self._animate_status_pulse)

    def _cancel_animation_jobs(self) -> None:
        """销毁前取消所有定时任务，避免回调落到已销毁的控件。"""
        if self._glow_job is not None:
            self._cancel_after_job(self._glow_job)
            self._glow_job = None
        if self._pulse_job is not None:
            self._cancel_after_job(self._pulse_job)
            self._pulse_job = None
        self.search.cancel_pending()

    def destroy(self) -> None:
        self._cancel_animation_jobs()
        super().destroy()

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_titlebar(main)
        self._build_toolbar(main)
        self._build_log_area(main)
        self._build_statusbar(main)

        self._display = LogDisplay(self._get_textbox, self.count_label)
        self._logs = LogController(
            schedule=self.after,
            cancel=self._cancel_after_job,
            exists=self.winfo_exists,
            viewable=self.winfo_viewable,
            reset_display=self._reset_log_display,
            add_entries=self._add_log_lines,
            adjust_search=self.search.adjust,
            has_query=self.search.has_query,
            on_search_rerun=self.search.rerun,
        )
        self._apply_log_source_ui()

    def _make_card(self, parent: tk.Misc, **kwargs: object) -> ctk.CTkFrame:
        """创建主题卡片并登记背景色，避免每个调用点重复绑定。"""
        card = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], **kwargs)
        self._bind_theme(card, fg_color='card')
        return card

    def _make_muted_label(
        self,
        parent: tk.Misc,
        text: str,
        *,
        size: int = 13,
        **kwargs: object,
    ) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family=self.UI_FONT, size=size),
            text_color=self.COLORS['text_muted'],
            **kwargs,
        )
        self._bind_theme(label, text_color='text_muted')
        return label

    def _build_titlebar(self, parent: tk.Misc) -> None:
        self._titlebar = self._make_card(parent, height=52, corner_radius=14)
        self._titlebar.pack(fill="x", pady=(0, 10))
        self._titlebar.pack_propagate(False)

        self._build_brand_area(self._titlebar)
        self._build_window_buttons(self._titlebar)

    def _build_brand_area(self, parent: tk.Misc) -> None:
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.pack(side="left", padx=16, pady=12)

        logo = ctk.CTkFrame(left, fg_color="transparent")
        logo.pack(side="left")

        self._logo_bars = []
        for _ in range(4):
            bar_item = ctk.CTkFrame(
                logo,
                width=4,
                height=22,
                fg_color=LOGO_STOPPED_COLOR,
                corner_radius=2,
            )
            bar_item.pack(side="left", padx=1)
            self._logo_bars.append(bar_item)

        self._title_label = ctk.CTkLabel(
            left,
            text="Luker 日志",
            font=ctk.CTkFont(family=self.UI_FONT, size=16, weight="bold"),
            text_color=self.COLORS['text'],
        )
        self._title_label.pack(side="left", padx=(14, 0))
        self._bind_theme(self._title_label, text_color='text')

        # Tk 鼠标事件只发给指针下的控件，不会冒泡到父控件，标题栏内可拖拽区域要各自绑定
        bind_window_drag(self, self._titlebar, left, logo, self._title_label)

    def _build_window_buttons(self, parent: tk.Misc) -> None:
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.pack(side="right", padx=10)

        # 日志源切换按钮（仅在 GCL 启用时显示）
        self._log_source_btn = make_button(
            right,
            'primary',
            self.COLORS,
            text="📊 Luker 日志",
            width=110,
            height=32,
            corner_radius=10,
            font_family=self.UI_FONT,
            font_size=12,
            font_weight='bold',
            command=self._toggle_log_source,
        )
        self._register_button(self._log_source_btn, 'primary')

        self._min_btn = make_button(
            right,
            'ghost',
            self.COLORS,
            text="─",
            width=40,
            height=32,
            corner_radius=8,
            font_size=16,
            font_weight='bold',
            command=self._on_minimize,
        )
        self._min_btn.pack(side="left", padx=2)
        self._register_button(self._min_btn, 'ghost')

        self._close_btn = make_button(
            right,
            'danger_ghost',
            self.COLORS,
            text="✕",
            width=40,
            height=32,
            corner_radius=8,
            font_size=15,
            font_weight='bold',
            command=self._on_close,
        )
        self._close_btn.pack(side="left", padx=2)
        self._register_button(self._close_btn, 'danger_ghost')

    def _hide_to_tray(self) -> None:
        """隐藏窗口并通知托盘同步可见状态。"""
        self.hide()
        if self.on_hide_callback:
            self.on_hide_callback()

    def _on_minimize(self) -> None:
        """最小化按钮：收进系统托盘，Luker 和启动器继续运行。"""
        if not self._tray_available:
            return

        self._hide_to_tray()

    def _on_map(self, event: tk.Event) -> None:
        # 窗口显示后 DWM 不一定会重新取整，这里补一次
        apply_window_rounding(self, context="日志窗口")
        # 显示/恢复后再检查一次，处理隐藏期间切换显示器的情况
        self.after_idle(self._resizer.fit_to_current_monitor)
        # 立即恢复呼吸，避免隐藏期的 500ms 轮询造成可见延迟
        self._restart_glow()
        # 缩放此时已注册，重新对齐搜索 hint
        self.search.on_map()

    def _check_window_state(self) -> None:
        with contextlib.suppress(Exception):
            hwnd = windll.user32.GetParent(self.winfo_id())
            is_minimized = windll.user32.IsIconic(hwnd)

            if self._was_minimized and not is_minimized:
                self.after(50, self._restore_window)

            self._was_minimized = is_minimized

        # 隐藏到托盘时降到 1 秒一次，减少空转；窗口销毁后停止轮询
        try:
            interval = 300 if self.winfo_viewable() else 1000
            self.after(interval, self._check_window_state)
        except tk.TclError:
            logger.debug("窗口已销毁，停止状态轮询")

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
        """关闭按钮：交给主程序确认并退出启动器。"""
        if self.on_exit_callback is not None:
            self.on_exit_callback()
            return

        # 兼容未注入退出回调的调用方：无托盘时保持原来的退出行为
        if not self._tray_available:
            if self.on_hide_callback:
                self.on_hide_callback()
            return

        self._hide_to_tray()

    def set_tray_available(self, available: bool) -> None:
        """托盘不可用时禁用最小化，避免窗口隐藏后无法恢复。"""
        self._tray_available = available
        if not available:
            self._min_btn.configure(state="disabled")

    def _build_toolbar(self, parent: tk.Misc) -> None:
        self._toolbar = ctk.CTkFrame(parent, fg_color="transparent", height=48)
        self._toolbar.pack(fill="x", pady=(0, 10))

        left = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._build_toolbar_actions(left)
        self.search = SearchBar(
            left,
            host=self,
            ui_font=self.UI_FONT,
            get_colors=lambda: self.COLORS,
            get_textbox=self._get_textbox,
            get_scaling=self._get_widget_scaling,
        )
        self.search.frame.pack(side="left", fill="x", expand=True, padx=(0, 8))

        right = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        right.pack(side="right")
        self._build_status_card(right)

        # 先让右侧状态卡占位，左侧再拿剩余宽度，搜索框才能随窗口拉伸
        left.pack(side="left", fill="x", expand=True)

    def _build_toolbar_actions(self, parent: tk.Misc) -> None:
        self._clear_btn = make_button(
            parent,
            'secondary',
            self.COLORS,
            text="清除",
            image=toolbar_icon('trash', self.COLORS['text']),
            compound='left',
            font_family=self.UI_FONT,
            font_size=14,
            width=100,
            height=40,
            command=self.clear_logs,
        )
        self._clear_btn.pack(side="left", padx=(0, 8))
        self._register_button(self._clear_btn, 'secondary')

        self.scroll_btn = make_button(
            parent,
            'secondary',
            self.COLORS,
            text="自动滚动",
            image=toolbar_icon('scroll', self.COLORS['text']),
            compound='left',
            font_family=self.UI_FONT,
            font_size=14,
            width=130,
            height=40,
            command=self._toggle_scroll,
        )
        self.scroll_btn.pack(side="left", padx=(0, 8))
        self._register_button(self.scroll_btn, 'secondary')

    def _build_status_card(self, parent: tk.Misc) -> None:
        self._status_card = self._make_card(parent, corner_radius=10)
        self._status_card.pack()

        inner = ctk.CTkFrame(self._status_card, fg_color="transparent")
        inner.pack(padx=16, pady=10)

        self._play_icon = transport_icon('play', self.COLORS['bg'])
        self.play_btn = ctk.CTkButton(
            inner,
            text="",
            image=self._play_icon,
            width=36,
            height=36,
            fg_color=self.COLORS['success'],
            hover_color=shade_color(self.COLORS['success'], 0.85),
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
        self._log_card = self._make_card(parent, corner_radius=14)
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
        self._bind_theme(
            self.log_text,
            text_color='text',
            scrollbar_button_color='border',
            scrollbar_button_hover_color='accent',
        )

        configure_log_tags(self._get_textbox(), self.COLORS)

    def _get_textbox(self) -> tk.Text:
        """返回 CTkTextbox 内部的 Text 控件；私有属性只在这里访问。"""
        return self.log_text._textbox

    def _build_statusbar(self, parent: tk.Misc) -> None:
        self._statusbar = self._make_card(parent, height=42, corner_radius=10)
        self._statusbar.pack(fill="x")
        self._statusbar.pack_propagate(False)

        self.count_label = self._make_muted_label(self._statusbar, "📝 0 条日志")
        self.count_label.pack(side="left", padx=16, pady=10)

        self._version_label = self._make_muted_label(self._statusbar, f"v{APP_VERSION}")
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
            text_color = self.COLORS['bg']
        else:
            text, color, title = "📊 Luker 日志", self.COLORS['accent'], "Luker 日志"
            text_color = self.COLORS['on_accent']

        self._log_source_btn.configure(
            text=text,
            fg_color=color,
            hover_color=shade_color(color, 0.85),
            text_color=text_color,
        )
        self._title_label.configure(text=title)

    def _cancel_after_job(self, job: str) -> None:
        """取消 Tk after 任务；任务已执行时忽略 TclError。"""
        with contextlib.suppress(tk.TclError):
            self.after_cancel(job)

    def _reset_log_display(self) -> None:
        """清空文本和搜索状态，供 LogController 重建显示。"""
        self.search.reset()

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
        self._apply_auto_scroll_ui()

    def _apply_auto_scroll_ui(self) -> None:
        """按自动滚动状态同步文字、图标和警示色。"""
        color = self.COLORS['text'] if self._auto_scroll else self.COLORS['warning']
        self.scroll_btn.configure(
            text="自动滚动" if self._auto_scroll else "已暂停",
            text_color=color,
            image=toolbar_icon(
                'scroll' if self._auto_scroll else 'pause',
                color,
                size=16,
            ),
        )

    def _refresh_toolbar_icons(self) -> None:
        """按当前主题重新生成工具栏图标。"""
        self._clear_btn.configure(image=toolbar_icon('trash', self.COLORS['text']))
        self._apply_auto_scroll_ui()

    def _toggle_running(self) -> None:
        if self._is_running:
            if self.on_stop_callback:
                self.on_stop_callback()
        else:
            if self.on_start_callback:
                self.on_start_callback()

    def _set_play_icon(self, kind: TransportIcon, color: str) -> None:
        self._play_icon = transport_icon(kind, self.COLORS['bg'])
        self.play_btn.configure(
            image=self._play_icon,
            fg_color=color,
            hover_color=shade_color(color, 0.85),
        )

    def update_status(self, state: LukerState) -> None:
        self._luker_state = state
        self._is_running = state is not LukerState.STOPPED
        dot_key, text, text_key, icon, icon_key, gray_logo = _STATUS_PRESENTATION[state]
        self.status_dot.configure(text_color=self.COLORS[dot_key])
        self.status_text.configure(text=text, text_color=self.COLORS[text_key])
        self._set_play_icon(icon, self.COLORS[icon_key])
        if gray_logo:
            self._set_logo_stopped()

    def show(self) -> None:
        # 从托盘恢复后不再按“系统最小化”处理，避免下一次轮询重复抢焦点
        self._was_minimized = False
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

    def _search_next(self) -> None:
        """跳转到下一个搜索结果。"""
        self.search.next()

    def _search_prev(self) -> None:
        """跳转到上一个搜索结果。"""
        self.search.prev()

    def _clear_search(self) -> None:
        """清除搜索；保留薄委托供窗口内部调用。"""
        self.search.clear_and_focus()
