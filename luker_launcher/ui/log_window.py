"""主日志窗口：UI 构建、主题切换和日志泵调度。"""

import contextlib
import logging
import math
import tkinter as tk
from collections.abc import Callable, Sequence
from types import TracebackType

import customtkinter as ctk
from PIL import Image

from luker_launcher.config import APP_VERSION, config
from luker_launcher.infrastructure import win32 as win32_api
from luker_launcher.log.pipeline import LogController
from luker_launcher.log.store import LogEntry
from luker_launcher.paths import resource_path
from luker_launcher.services.readiness import LukerState
from luker_launcher.theme import (
    LOGO_GLOW_INTERVAL_MS,
    LOGO_GLOW_STEP,
    LOGO_STOPPED_COLOR,
    PRESET_THEMES,
    ThemeColorKey,
    logo_bar_glow_color,
    mix_color,
    shade_color,
)
from luker_launcher.ui.buttons import ButtonRole, button_colors, make_button
from luker_launcher.ui.icons import TransportIcon, toolbar_icon, transport_icon
from luker_launcher.ui.log_view.display import LogDisplay, configure_log_tags
from luker_launcher.ui.log_view.search import SearchBar
from luker_launcher.ui.motion import StepTicker, WindowFade, ease_in_out_cubic, fade_palette
from luker_launcher.ui.resizing import WindowResizer
from luker_launcher.ui.theme_assets import theme_log_image
from luker_launcher.ui.tokens import (
    CHARACTER_IMAGE_HEIGHT,
    CHARACTER_IMAGE_WIDTH,
    CHARACTER_MOTTO_WRAP,
    CHARACTER_PANEL_PADDING,
    CHARACTER_PANEL_WIDTH,
    CONTROL_HEIGHT_LG,
    CONTROL_HEIGHT_MD,
    CONTROL_HEIGHT_XL,
    CONTROL_HEIGHT_XS,
    DELAY_BLUR_LOG_MS,
    DELAY_RESTORE_WINDOW_MS,
    FONT_BODY,
    FONT_DISPLAY,
    FONT_HEADING,
    FONT_MOTTO,
    FONT_SMALL,
    FONT_TITLE,
    GAP_BRAND,
    GAP_GRID,
    GAP_INLINE,
    GAP_INLINE_SM,
    GAP_SECTION,
    GAP_WINDOW,
    GAP_XS,
    LOGO_BAR_GAP,
    LOGO_BAR_HEIGHT_MAIN,
    LOGO_BAR_WIDTH,
    MOTION_ERROR_REVEAL_MS,
    MOTION_FADE_DURATION_MS,
    MOTION_FADE_INTERVAL_MS,
    MOTION_LOADING_DELAY_MS,
    MOTION_WINDOW_ALPHA,
    MOTION_WINDOW_FADE_START,
    PAD_CARD,
    PAD_CARD_COMPACT,
    PAD_ROW_X,
    PAD_ROW_Y,
    PAD_WINDOW,
    RADIUS_CARD,
    RADIUS_CARD_LG,
    RADIUS_CIRCLE,
    RADIUS_CONTROL,
    RADIUS_LOGO,
    STATUSBAR_HEIGHT,
    TITLEBAR_MAIN_HEIGHT,
    TOOLBAR_HEIGHT,
)
from luker_launcher.ui.window_utils import (
    apply_window_rounding,
    bind_window_drag,
    get_motto_font,
    get_ui_font,
    sync_window_blur,
)

logger = logging.getLogger(__name__)

# Luker 三态对应的状态点、文字、播放按钮和 logo 表现
_STATUS_PRESENTATION: dict[LukerState, tuple[str, str, str, TransportIcon, str, bool]] = {
    LukerState.READY: ('success', '运行中', 'success', 'stop', 'error', False),
    LukerState.STARTING: ('warning', '启动中', 'warning', 'stop', 'error', True),
    LukerState.STOPPED: ('error', '已停止', 'error', 'play', 'success', True),
}


def auto_scroll_button_colors(colors: dict[str, str], enabled: bool) -> dict[str, object]:
    """返回自动滚动按钮在启用/暂停时的描边、文字和悬停颜色。"""
    key = 'accent' if enabled else 'warning'
    options = button_colors('outline', colors)
    options.update(
        hover_color=mix_color(colors['card'], colors[key], 0.12),
        text_color=colors[key],
        border_color=mix_color(colors['border'], colors[key], 0.55),
    )
    return options


def empty_log_text(state: LukerState) -> tuple[str, str]:
    """返回日志区空状态的主标题和说明。"""
    if state is LukerState.STARTING:
        return "正在启动 Luker…", "等待服务就绪，日志马上出现。"
    if state is LukerState.READY:
        return "暂无日志输出", "Luker 正在运行，新日志会显示在这里。"
    return "还没有日志", "点击「开始」运行 Luker，日志会显示在这里。"


def truncate_log_text(text: str, limit: int = 56) -> str:
    """把错误行压成单行并截断，避免横幅把窗口撑宽。"""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(1, limit - 1)].rstrip() + "…"


def fit_character_size(
    native_size: tuple[int, int],
    panel_width: int,
    panel_height: int,
    reserved_height: int,
    padding: int,
) -> tuple[int, int]:
    """在扣除座右铭和内边距后的区域内等比缩放角色立绘。"""
    native_width, native_height = native_size
    if native_width <= 0 or native_height <= 0:
        return (1, 1)

    available_width = max(1, panel_width - padding * 2)
    available_height = max(1, panel_height - reserved_height - padding * 2)
    scale = min(available_width / native_width, available_height / native_height)
    return (
        max(1, round(native_width * scale)),
        max(1, round(native_height * scale)),
    )


def widget_scaling(widget: object) -> float:
    """返回控件缩放系数；Tk 的 winfo_* 是物理像素，CTkImage 尺寸是逻辑像素。"""
    getter = getattr(widget, '_get_widget_scaling', None)
    if not callable(getter):
        return 1.0
    try:
        scale = float(getter())
    except (AttributeError, TypeError, ValueError, tk.TclError):
        return 1.0
    return scale if scale > 0 else 1.0


def error_banner_colors(colors: dict[str, str]) -> dict[str, str]:
    """错误横幅的混合底色和描边；文字色由绑定单独处理。"""
    return {
        'fg_color': mix_color(colors['card'], colors['error'], 0.10),
        'border_color': mix_color(colors['border'], colors['error'], 0.45),
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
        self.MOTTO_FONT = get_motto_font()

    def _init_window(self) -> None:
        self.withdraw()

        self.overrideredirect(True)
        self.resizable(False, False)
        apply_window_rounding(self, context="日志窗口")

        self.title("Luker 日志")
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.bind('<Alt-F4>', lambda _event: self._on_close())
        # 按主屏工作区和当前缩放限制初始尺寸，避免 150% 下落入任务栏
        self._resizer = WindowResizer(self, resizable=False)
        self._resizer.apply_initial_geometry()

        self._set_window_icon()

        self.configure(fg_color=self.COLORS['bg'])
        self.attributes('-alpha', MOTION_WINDOW_ALPHA if config.blur_enabled else 1.0)

        self.after(DELAY_BLUR_LOG_MS, self._ensure_blur)

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

        self._fade = WindowFade(self, interval_ms=MOTION_FADE_INTERVAL_MS)
        self._blur_ready = False
        self._theme_ticker: StepTicker | None = None
        self._theme_from: dict[str, str] | None = None
        self._theme_to: dict[str, str] | None = None

        self._replaying = False
        self._overlay_job: str | None = None
        self._error_reveal_job: str | None = None

        self._character_source: Image.Image | None = None
        self._character_display_size: tuple[int, int] | None = None
        self._character_display_scale: float | None = None
        self._character_fit_job: str | None = None

    def _report_callback_exception(
        self,
        exc: type[BaseException],
        val: BaseException,
        tb: TracebackType | None,
    ) -> None:
        logger.error("界面回调异常", exc_info=(exc, val, tb))

    def _set_window_icon(self) -> None:
        try:
            icon_path = resource_path('icon.ico')
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
            else:
                png_path = resource_path('icon.png')
                if png_path.exists():
                    from PIL import Image, ImageTk

                    img = Image.open(png_path)
                    photo = ImageTk.PhotoImage(img)
                    self.iconphoto(True, photo)
                    self._icon_photo = photo
        except Exception:
            logger.warning("设置窗口图标失败", exc_info=True)

    def _ensure_blur(self) -> None:
        """首次显示前确保毛玻璃已就绪；后续显示不再重复设置。"""
        if self.__dict__.get('_blur_ready', True):
            return
        self._setup_blur()

    def _setup_blur(self) -> None:
        fade = self.__dict__.get('_fade')
        if fade is not None:
            fade.cancel()
        sync_window_blur(
            self,
            self.COLORS['bg'],
            enabled=config.blur_enabled,
            window_alpha=MOTION_WINDOW_ALPHA,
            tint_alpha=0xDD,
            context="日志窗口",
        )
        self._blur_ready = True
        self.update()

    def _on_blur_change(self, _enabled: bool) -> None:
        self._setup_blur()

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        if not self._ui_ready:
            self.COLORS = new_colors
            self._apply_theme()
            return
        self._start_theme_fade(new_colors)

    def _start_theme_fade(self, new_colors: dict[str, str]) -> None:
        """从一个主题平滑过渡到另一个；再次切换时从当前中间色继续。"""
        if self._theme_ticker is not None:
            self._theme_ticker.cancel()
            self._theme_ticker = None
        self._theme_from = dict(self.COLORS)
        self._theme_to = dict(new_colors)
        steps = max(1, round(MOTION_FADE_DURATION_MS / MOTION_FADE_INTERVAL_MS))
        self._theme_ticker = StepTicker(
            self,
            steps=steps,
            interval_ms=MOTION_FADE_INTERVAL_MS,
            on_step=self._theme_step,
            on_done=self._finish_theme_fade,
        )
        self._theme_ticker.start()

    def _theme_step(self, progress: float) -> None:
        if self._theme_from is None or self._theme_to is None:
            return
        palette = fade_palette(self._theme_from, self._theme_to, ease_in_out_cubic(progress))
        self.COLORS = palette
        self._apply_theme_colors(palette)

    def _finish_theme_fade(self) -> None:
        self._theme_ticker = None
        if self._theme_to is None:
            return
        self.COLORS = self._theme_to
        self._theme_from = None
        self._theme_to = None
        self._apply_theme()

    def _bind_theme(self, widget: tk.Misc, **options: ThemeColorKey) -> None:
        """登记控件在主题切换时需要更新的选项，值为 COLORS 的键名。"""
        self._theme_bindings.append((widget, options))

    def _register_button(self, button: ctk.CTkButton, role: ButtonRole) -> ctk.CTkButton:
        """登记按钮角色，主题切换时按新颜色重算。"""
        self._styled_buttons.append((button, role))
        return button

    def _apply_theme_bindings(self, palette: dict[str, str]) -> None:
        for widget, options in self._theme_bindings:
            with contextlib.suppress(tk.TclError):
                widget.configure(**{option: palette[key] for option, key in options.items()})
        for button, role in self._styled_buttons:
            with contextlib.suppress(tk.TclError):
                button.configure(**button_colors(role, palette))

    def _apply_theme_colors(self, palette: dict[str, str]) -> None:
        """渐变期间只改颜色，不触发 DWM、图标重建或状态图标注。"""
        if not self._ui_ready:
            return
        with contextlib.suppress(tk.TclError):
            self.configure(fg_color=palette['bg'])
        self._apply_theme_bindings(palette)
        configure_log_tags(self._get_textbox(), palette)
        self.search.refresh_colors(update_icon=False)
        self._apply_error_banner_colors()

    def _apply_theme(self) -> None:
        if not self._ui_ready:
            return
        try:
            self.configure(fg_color=self.COLORS['bg'])

            self._setup_blur()

            self._apply_theme_bindings(self.COLORS)
            self._apply_theme_art()
            self._refresh_toolbar_icons()

            # 动态状态依赖静态颜色，必须放在绑定之后
            configure_log_tags(self._get_textbox(), self.COLORS)
            self.search.refresh_colors()
            self.update_status(self._luker_state)
            self._apply_error_banner_colors()

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
        theme_ticker = self.__dict__.get('_theme_ticker')
        if theme_ticker is not None:
            theme_ticker.cancel()
            self._theme_ticker = None
        fade = self.__dict__.get('_fade')
        if fade is not None:
            fade.cancel()
        self._cancel_overlay_job()
        reveal_job = self.__dict__.get('_error_reveal_job')
        if reveal_job is not None:
            self._cancel_after_job(reveal_job)
            self._error_reveal_job = None
        self.search.cancel_pending()

    def destroy(self) -> None:
        self._cancel_animation_jobs()
        logs = getattr(self, '_logs', None)
        if logs is not None:
            logs.stop()
        config.remove_theme_change_callback(self._on_theme_change)
        config.remove_blur_change_callback(self._on_blur_change)
        super().destroy()

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=PAD_WINDOW, pady=PAD_WINDOW)

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
            on_search_rerun=lambda: self.search.rerun(preserve_current=True),
            on_replay_state_change=self._on_replay_state_change,
        )
        self._bind_search_shortcuts()
        self._update_log_state()

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
        size: int = FONT_BODY,
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
        self._titlebar = self._make_card(
            parent, height=TITLEBAR_MAIN_HEIGHT, corner_radius=RADIUS_CARD_LG
        )
        self._titlebar.pack(fill="x", pady=(0, GAP_WINDOW))
        self._titlebar.pack_propagate(False)

        self._build_brand_area(self._titlebar)
        self._build_window_buttons(self._titlebar)

    def _build_brand_area(self, parent: tk.Misc) -> None:
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.pack(side="left", padx=PAD_CARD, pady=GAP_SECTION)

        logo = ctk.CTkFrame(left, fg_color="transparent")
        logo.pack(side="left")

        self._logo_bars = []
        for _ in range(4):
            bar_item = ctk.CTkFrame(
                logo,
                width=LOGO_BAR_WIDTH,
                height=LOGO_BAR_HEIGHT_MAIN,
                fg_color=LOGO_STOPPED_COLOR,
                corner_radius=RADIUS_LOGO,
            )
            bar_item.pack(side="left", padx=LOGO_BAR_GAP)
            self._logo_bars.append(bar_item)

        self._title_label = ctk.CTkLabel(
            left,
            text="Luker 日志",
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_TITLE, weight="bold"),
            text_color=self.COLORS['text'],
        )
        self._title_label.pack(side="left", padx=(GAP_BRAND, 0))
        self._bind_theme(self._title_label, text_color='text')

        # Tk 鼠标事件只发给指针下的控件，不会冒泡到父控件，标题栏内可拖拽区域要各自绑定
        bind_window_drag(self, self._titlebar, left, logo, self._title_label)

    def _build_window_buttons(self, parent: tk.Misc) -> None:
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.pack(side="right", padx=PAD_ROW_X)

        self._min_btn = make_button(
            right,
            'ghost',
            self.COLORS,
            text="─",
            width=40,
            height=CONTROL_HEIGHT_MD,
            corner_radius=RADIUS_CONTROL,
            font_size=FONT_TITLE,
            font_weight='bold',
            command=self._on_minimize,
        )
        self._min_btn.pack(side="left", padx=GAP_XS)
        self._register_button(self._min_btn, 'ghost')

        self._close_btn = make_button(
            right,
            'danger_ghost',
            self.COLORS,
            text="✕",
            width=40,
            height=CONTROL_HEIGHT_MD,
            corner_radius=RADIUS_CONTROL,
            font_size=FONT_TITLE,
            font_weight='bold',
            command=self._on_close,
        )
        self._close_btn.pack(side="left", padx=GAP_XS)
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
            hwnd = win32_api.user32.GetParent(self.winfo_id())
            is_minimized = win32_api.user32.IsIconic(hwnd)

            if self._was_minimized and not is_minimized:
                self.after(DELAY_RESTORE_WINDOW_MS, self._restore_window)

            self._was_minimized = is_minimized

        # 隐藏到托盘时降到 1 秒一次，减少空转；窗口销毁后停止轮询
        try:
            interval = 300 if self.winfo_viewable() else 1000
            self.after(interval, self._check_window_state)
        except tk.TclError:
            logger.debug("窗口已销毁，停止状态轮询")

    def _restore_window(self) -> None:
        try:
            hwnd = win32_api.user32.GetParent(self.winfo_id())
            SW_RESTORE = 9
            win32_api.user32.ShowWindow(hwnd, SW_RESTORE)
            self.lift()
            self.focus_force()
        except Exception:
            logger.warning("恢复窗口失败", exc_info=True)

    def _on_close(self) -> None:
        """关闭按钮：交给主程序决定隐藏到托盘、退出或询问。"""
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
        self._toolbar = ctk.CTkFrame(parent, fg_color="transparent", height=TOOLBAR_HEIGHT)
        self._toolbar.pack(fill="x", pady=(0, GAP_WINDOW))

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
        self.search.frame.pack(side="left", fill="x", expand=True, padx=(0, GAP_INLINE))

        right = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        right.pack(side="right")
        self._build_status_card(right)

        # 先让右侧状态卡占位，左侧再拿剩余宽度，搜索框才能随窗口拉伸
        left.pack(side="left", fill="x", expand=True)

    def _build_toolbar_actions(self, parent: tk.Misc) -> None:
        self._clear_btn = make_button(
            parent,
            'danger_outline',
            self.COLORS,
            text="清除",
            image=toolbar_icon('trash', self.COLORS['text']),
            compound='left',
            font_family=self.UI_FONT,
            font_size=FONT_HEADING,
            width=100,
            height=CONTROL_HEIGHT_XL,
            command=self.clear_logs,
        )
        self._clear_btn.pack(side="left", padx=(0, GAP_INLINE))
        self._register_button(self._clear_btn, 'danger_outline')

        self.scroll_btn = make_button(
            parent,
            'outline',
            self.COLORS,
            text="自动滚动",
            image=toolbar_icon('scroll', self.COLORS['text']),
            compound='left',
            font_family=self.UI_FONT,
            font_size=FONT_HEADING,
            width=130,
            height=CONTROL_HEIGHT_XL,
            command=self._toggle_scroll,
        )
        self.scroll_btn.pack(side="left", padx=(0, GAP_INLINE))
        self._register_button(self.scroll_btn, 'outline')

    def _build_status_card(self, parent: tk.Misc) -> None:
        self._status_card = self._make_card(parent, corner_radius=RADIUS_CARD)
        self._status_card.pack()

        inner = ctk.CTkFrame(self._status_card, fg_color="transparent")
        inner.pack(padx=PAD_CARD, pady=GAP_WINDOW)

        self._play_icon = transport_icon('play', self.COLORS['bg'])
        self.play_btn = ctk.CTkButton(
            inner,
            text="",
            image=self._play_icon,
            width=CONTROL_HEIGHT_LG,
            height=CONTROL_HEIGHT_LG,
            fg_color=self.COLORS['success'],
            hover_color=shade_color(self.COLORS['success'], 0.85),
            corner_radius=RADIUS_CIRCLE,
            command=self._toggle_running,
        )
        self.play_btn.pack(side="left", padx=(0, GAP_SECTION))

        self.status_dot = ctk.CTkLabel(
            inner,
            text="●",
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_DISPLAY),
            text_color=self.COLORS['error'],
        )
        self.status_dot.pack(side="left", padx=(0, GAP_INLINE))

        self.status_text = ctk.CTkLabel(
            inner,
            text="已停止",
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_HEADING, weight="bold"),
            text_color=self.COLORS['error'],
        )
        self.status_text.pack(side="left")

    def _build_log_area(self, parent: tk.Misc) -> None:
        self._log_card = self._make_card(parent, corner_radius=RADIUS_CARD_LG)
        self._log_card.pack(fill="both", expand=True, pady=(0, GAP_WINDOW))

        body = ctk.CTkFrame(self._log_card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=PAD_CARD_COMPACT, pady=PAD_CARD_COMPACT)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self._text_panel = ctk.CTkFrame(
            body,
            fg_color=self.COLORS['card'],
            corner_radius=RADIUS_CARD,
        )
        self._text_panel.grid(row=0, column=0, sticky="nsew")
        self._bind_theme(self._text_panel, fg_color='card')

        self._character_panel = ctk.CTkFrame(
            body,
            fg_color=self.COLORS['card'],
            width=CHARACTER_PANEL_WIDTH,
            corner_radius=RADIUS_CARD,
        )
        self._character_panel.grid(row=0, column=1, sticky="ns", padx=(GAP_GRID, 0))
        self._character_panel.grid_propagate(False)
        self._character_panel.columnconfigure(0, weight=1)
        self._character_panel.rowconfigure(0, weight=1)
        self._bind_theme(self._character_panel, fg_color='card')

        self._character_label = ctk.CTkLabel(
            self._character_panel,
            text="",
            fg_color="transparent",
        )
        self._character_label.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=CHARACTER_PANEL_PADDING,
            pady=(CHARACTER_PANEL_PADDING, 0),
        )
        self._motto_label = ctk.CTkLabel(
            self._character_panel,
            text="",
            font=ctk.CTkFont(family=self.MOTTO_FONT, size=FONT_MOTTO),
            text_color=self.COLORS['text_dim'],
            justify="center",
            wraplength=CHARACTER_MOTTO_WRAP,
        )
        self._motto_label.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=PAD_CARD_COMPACT,
            pady=(GAP_INLINE_SM, PAD_CARD_COMPACT),
        )
        self._bind_theme(self._motto_label, text_color='text_dim')
        self._character_panel.bind(
            '<Configure>',
            self._on_character_panel_configure,
            add='+',
        )
        self._character_image: ctk.CTkImage | None = None

        # 错误横幅默认不占位，出现错误时才 pack 到文本区上方
        self._error_banner = ctk.CTkFrame(
            self._text_panel,
            fg_color=self.COLORS['card'],
            corner_radius=RADIUS_CONTROL,
            border_width=1,
            border_color=self.COLORS['border'],
        )
        self._error_icon = ctk.CTkLabel(
            self._error_banner,
            text="⚠",
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_BODY),
            text_color=self.COLORS['error'],
        )
        self._error_icon.pack(side="left", padx=(PAD_ROW_X, GAP_GRID))
        self._error_label = ctk.CTkLabel(
            self._error_banner,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_SMALL),
            text_color=self.COLORS['text_dim'],
            anchor="w",
            justify="left",
        )
        self._error_label.pack(side="left", fill="x", expand=True)
        self._error_locate = make_button(
            self._error_banner,
            'danger_ghost',
            self.COLORS,
            text="定位",
            width=52,
            height=CONTROL_HEIGHT_XS,
            font_family=self.UI_FONT,
            font_size=FONT_SMALL,
            command=self._reveal_last_error,
        )
        self._error_locate.pack(side="right", padx=(GAP_INLINE, PAD_ROW_Y))
        self._register_button(self._error_locate, 'danger_ghost')
        self._bind_theme(self._error_icon, text_color='error')
        self._bind_theme(self._error_label, text_color='text_dim')
        self._apply_error_banner_colors()

        self.log_text = ctk.CTkTextbox(
            self._text_panel,
            fg_color="transparent",
            text_color=self.COLORS['text'],
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_BODY),
            corner_radius=RADIUS_CARD,
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent'],
        )
        self.log_text.pack(fill="both", expand=True, padx=PAD_CARD_COMPACT, pady=PAD_CARD_COMPACT)
        self._bind_theme(
            self.log_text,
            text_color='text',
            scrollbar_button_color='border',
            scrollbar_button_hover_color='accent',
        )
        self._get_textbox().configure(state="disabled")

        # 空/加载遮罩：覆盖在文本区中央，不写入 Text，避免污染搜索和计数
        self._overlay = ctk.CTkFrame(self._text_panel, fg_color="transparent")
        self._overlay_title = ctk.CTkLabel(
            self._overlay,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_HEADING, weight="bold"),
            text_color=self.COLORS['text_dim'],
            justify="center",
        )
        self._overlay_title.pack()
        self._overlay_detail = ctk.CTkLabel(
            self._overlay,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=FONT_BODY),
            text_color=self.COLORS['text_muted'],
            justify="center",
            wraplength=360,
        )
        self._overlay_detail.pack(pady=(GAP_GRID, 0))
        self._bind_theme(self._overlay_title, text_color='text_dim')
        self._bind_theme(self._overlay_detail, text_color='text_muted')
        self._overlay.place(relx=0.5, rely=0.5, anchor="center")
        self._overlay.lift()
        self._overlay.place_forget()

        self._apply_theme_art()
        configure_log_tags(self._get_textbox(), self.COLORS)

    def _apply_theme_art(self) -> None:
        """按当前主题显示或隐藏右侧角色立绘和座右铭。"""
        panel = self.__dict__.get('_character_panel')
        label = self.__dict__.get('_character_label')
        if panel is None or label is None:
            return

        theme = PRESET_THEMES.get(config.theme_name, {})
        motto_label = self.__dict__.get('_motto_label')
        motto = theme.get('motto', '')
        if motto_label is not None:
            motto_label.configure(text=motto)
            if motto:
                motto_label.grid()
            else:
                motto_label.grid_remove()

        image = theme_log_image(theme)
        if image is None:
            self._character_source = None
            self._character_display_size = None
            self._character_display_scale = None
            self._character_image = None
            panel.grid_remove()
            return

        self._character_source = image
        self._character_display_size = None
        self._character_display_scale = None
        self._character_image = None
        panel.grid()
        self._fit_character_art()

    def _on_character_panel_configure(self, _event: tk.Event) -> None:
        self._schedule_character_fit()

    def _schedule_character_fit(self) -> None:
        if self._character_fit_job is not None:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._character_fit_job)
        try:
            self._character_fit_job = self.after_idle(self._run_character_fit)
        except tk.TclError:
            self._character_fit_job = None

    def _run_character_fit(self) -> None:
        self._character_fit_job = None
        self._fit_character_art()

    def _fit_character_art(self) -> None:
        """按面板实际高度等比放大立绘，填满座右铭上方的空间。"""
        panel = self.__dict__.get('_character_panel')
        label = self.__dict__.get('_character_label')
        source = self.__dict__.get('_character_source')
        if panel is None or label is None or source is None:
            return

        # 面板与座右铭的 winfo_* 都是物理像素；CTkImage 的 size 是逻辑像素，
        # 直接混用会让图片在 125%/150% 缩放下被放大两次并裁切。
        scale = widget_scaling(panel)
        try:
            panel_width = panel.winfo_width()
            panel_height = panel.winfo_height()
        except (AttributeError, tk.TclError):
            panel_width = panel_height = 0

        if panel_width <= 1 or panel_height <= 1:
            size = (CHARACTER_IMAGE_WIDTH, CHARACTER_IMAGE_HEIGHT)
        else:
            panel_width = max(1, round(panel_width / scale))
            panel_height = max(1, round(panel_height / scale))
            reserved_height = 0
            motto_label = self.__dict__.get('_motto_label')
            if motto_label is not None:
                try:
                    mapped = bool(motto_label.winfo_ismapped())
                    if mapped:
                        reserved_height = (
                            round(motto_label.winfo_reqheight() / scale)
                            + GAP_INLINE_SM
                            + PAD_CARD_COMPACT
                        )
                except (AttributeError, tk.TclError):
                    reserved_height = 0
            size = fit_character_size(
                source.size,
                panel_width,
                panel_height,
                reserved_height,
                CHARACTER_PANEL_PADDING,
            )

        if size == self._character_display_size and scale == self._character_display_scale:
            return
        self._character_display_size = size
        self._character_display_scale = scale
        self._character_image = ctk.CTkImage(
            light_image=source,
            dark_image=source,
            size=size,
        )
        with contextlib.suppress(tk.TclError):
            label.configure(image=self._character_image)

    def _on_replay_state_change(self, active: bool) -> None:
        self._replaying = active
        self._update_log_state()

    def _update_log_state(self) -> None:
        """根据重放状态、日志条数和 Luker 状态刷新遮罩/错误横幅。"""
        display = self.__dict__.get('_display')
        logs = self.__dict__.get('_logs')
        if display is None or logs is None:
            return

        if self.__dict__.get('_replaying', False):
            self._schedule_loading_overlay()
        else:
            self._cancel_overlay_job()
            if display.count == 0:
                self._show_empty_overlay()
            else:
                self._hide_overlay()
        self._update_error_banner()

    def _schedule_loading_overlay(self) -> None:
        # 重放通常几十毫秒就结束；延迟出现，避免小日志时闪一下
        if self._display.count > 0:
            self._hide_overlay()
            return
        if self.__dict__.get('_overlay_job') is None:
            self._overlay_job = self.after(MOTION_LOADING_DELAY_MS, self._show_loading_overlay)

    def _show_loading_overlay(self) -> None:
        self._overlay_job = None
        if not self.__dict__.get('_replaying', False) or self._display.count > 0:
            return
        self._show_overlay("正在加载日志…", "正在恢复历史日志，请稍候。")

    def _show_empty_overlay(self) -> None:
        title, detail = empty_log_text(self._luker_state)
        self._show_overlay(title, detail)

    def _show_overlay(self, title: str, detail: str) -> None:
        self._overlay_title.configure(text=title)
        self._overlay_detail.configure(text=detail)
        self._overlay.place(relx=0.5, rely=0.5, anchor="center")
        self._overlay.lift()

    def _hide_overlay(self) -> None:
        self._cancel_overlay_job()
        self._overlay.place_forget()

    def _cancel_overlay_job(self) -> None:
        job = self.__dict__.get('_overlay_job')
        if job is not None:
            self._cancel_after_job(job)
            self._overlay_job = None

    def _update_error_banner(self) -> None:
        logs = self.__dict__.get('_logs')
        display = self.__dict__.get('_display')
        if logs is None or display is None:
            return
        error = logs.last_error
        index = display.last_error_index
        if error is None or index is None or display.count == 0:
            self._error_banner.pack_forget()
            return

        self._error_label.configure(text=f"最近错误 · {truncate_log_text(error.text)}")
        self._apply_error_banner_colors()
        if self._error_banner.winfo_manager() != "pack":
            self._error_banner.pack(
                fill="x",
                padx=PAD_CARD_COMPACT,
                pady=(PAD_CARD_COMPACT, 0),
                before=self.log_text,
            )

    def _apply_error_banner_colors(self) -> None:
        banner = self.__dict__.get('_error_banner')
        if banner is None:
            return
        banner.configure(**error_banner_colors(self.COLORS))

    def _reveal_last_error(self) -> None:
        index = self._display.last_error_index
        if not index:
            return
        textbox = self._get_textbox()
        with contextlib.suppress(tk.TclError):
            textbox.see(index)
            textbox.tag_add("error_reveal", index, f"{index} lineend")
            textbox.tag_raise("error_reveal")
        if self._error_reveal_job is not None:
            self._cancel_after_job(self._error_reveal_job)
        self._error_reveal_job = self.after(MOTION_ERROR_REVEAL_MS, self._clear_error_reveal)

    def _clear_error_reveal(self) -> None:
        self._error_reveal_job = None
        with contextlib.suppress(tk.TclError):
            self._get_textbox().tag_remove("error_reveal", "1.0", "end")

    def _get_textbox(self) -> tk.Text:
        """返回 CTkTextbox 内部的 Text 控件；私有属性只在这里访问。"""
        return self.log_text._textbox

    def _build_statusbar(self, parent: tk.Misc) -> None:
        self._statusbar = self._make_card(
            parent, height=STATUSBAR_HEIGHT, corner_radius=RADIUS_CARD
        )
        self._statusbar.pack(fill="x")
        self._statusbar.pack_propagate(False)

        self.count_label = self._make_muted_label(self._statusbar, "📝 0 条日志")
        self.count_label.pack(side="left", padx=PAD_CARD, pady=GAP_WINDOW)

        self._version_label = self._make_muted_label(self._statusbar, f"v{APP_VERSION}")
        self._version_label.pack(side="right", padx=PAD_CARD, pady=GAP_WINDOW)

    def add_log(self, line: str) -> None:
        """添加 Luker 日志。"""
        self._logs.add_log(line)

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
        self._update_log_state()

    def _add_log_lines(self, entries: Sequence[LogEntry]) -> int:
        """批量插入日志，返回被裁剪的文本行数。"""
        removed = self._display.add_entries(entries, auto_scroll=self._auto_scroll)
        self._update_log_state()
        return removed

    def clear_logs(self) -> None:
        self._logs.clear()
        self._clear_search()

    def _toggle_scroll(self) -> None:
        self._auto_scroll = not self._auto_scroll
        self._apply_auto_scroll_ui()

    def _apply_auto_scroll_ui(self) -> None:
        """按自动滚动状态同步文字、图标、描边和悬停色。"""
        self.scroll_btn.configure(
            **auto_scroll_button_colors(self.COLORS, self._auto_scroll),
            text="自动滚动" if self._auto_scroll else "已暂停",
            image=toolbar_icon(
                'scroll' if self._auto_scroll else 'pause',
                self.COLORS['text'],
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
        self._update_log_state()

    def show(self) -> None:
        # 从托盘恢复后不再按“系统最小化”处理，避免下一次轮询重复抢焦点
        self._was_minimized = False
        self._ensure_blur()
        fade = self.__dict__.get('_fade')
        if fade is not None:
            if config.blur_enabled:
                fade.start(
                    MOTION_WINDOW_FADE_START,
                    MOTION_WINDOW_ALPHA,
                    duration_ms=MOTION_FADE_DURATION_MS,
                )
            else:
                fade.cancel(reset=1.0)
        self.deiconify()
        self.lift()
        self.focus_force()
        self._logs.on_show()
        if self.__dict__.get('_display') is not None:
            self._update_log_state()

    def hide(self) -> None:
        self._cancel_overlay_job()
        fade = self.__dict__.get('_fade')
        if fade is not None:
            base = MOTION_WINDOW_ALPHA if config.blur_enabled else 1.0
            fade.cancel(reset=base)
        self._logs.on_hide()
        self.withdraw()

    def is_visible(self) -> bool:
        return self.winfo_viewable()

    # ===== 搜索功能 =====

    def _bind_search_shortcuts(self) -> None:
        """窗口级搜索快捷键：Ctrl+F、F3/Shift+F3。"""
        self.bind('<Control-f>', lambda _event: self._focus_search())
        self.bind('<Control-F>', lambda _event: self._focus_search())
        self.bind('<F3>', lambda _event: self._search_next())
        self.bind('<Shift-F3>', lambda _event: self._search_prev())

    def _focus_search(self) -> str:
        """聚焦搜索框；已有查询时全选。"""
        self.search.focus()
        return "break"

    def _search_next(self) -> str:
        """跳转到下一个搜索结果。"""
        self.search.next()
        return "break"

    def _search_prev(self) -> str:
        """跳转到上一个搜索结果。"""
        self.search.prev()
        return "break"

    def _clear_search(self) -> str:
        """清除搜索；保留薄委托供窗口内部调用。"""
        self.search.clear_and_focus()
        return "break"
