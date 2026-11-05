"""托盘右键菜单。"""

import contextlib
import logging
import math
import tkinter as tk
from collections.abc import Callable, Sequence
from typing import TypedDict

import customtkinter as ctk

from luker_launcher.config import config
from luker_launcher.infrastructure import win32 as win32_api
from luker_launcher.services.readiness import LukerState
from luker_launcher.theme import (
    LOGO_GLOW_INTERVAL_MS,
    LOGO_GLOW_STEP,
    LOGO_STOPPED_COLOR,
    logo_bar_glow_color,
)
from luker_launcher.ui.buttons import make_button
from luker_launcher.ui.dpi import (
    clamp_popup_position,
    format_geometry,
    get_monitor_info,
    sync_window_scaling,
)
from luker_launcher.ui.icons import MenuIcon, menu_icon
from luker_launcher.ui.motion import WindowFade
from luker_launcher.ui.tokens import (
    DELAY_BLUR_TRAY_MS,
    DELAY_NOACTIVATE_TRAY_MS,
    FONT_MENU_TITLE,
    GAP_INLINE_SM,
    GAP_MENU_ITEM,
    GAP_MENU_SEPARATOR,
    GAP_SECTION,
    ICON_MENU,
    LOGO_BAR_GAP,
    LOGO_BAR_HEIGHT_MENU,
    LOGO_BAR_WIDTH,
    MENU_WIDTH,
    MOTION_TRAY_FADE_MS,
    MOTION_TRAY_FADE_START,
    MOTION_WINDOW_ALPHA,
    PAD_MENU,
    PAD_TRAY_HEADER_X,
    PAD_TRAY_HEADER_Y,
    POLL_TRAY_MOUSE_MS,
    RADIUS_CARD,
    RADIUS_LOGO,
    SEPARATOR_HEIGHT,
)
from luker_launcher.ui.window_utils import apply_window_rounding, get_ui_font, sync_window_blur

logger = logging.getLogger(__name__)

HEADER_PAD_X = PAD_TRAY_HEADER_X
HEADER_PAD_Y = PAD_TRAY_HEADER_Y
TITLE_FONT_SIZE = FONT_MENU_TITLE
LOGO_BAR_HEIGHT = LOGO_BAR_HEIGHT_MENU
MENU_ICON_SIZE = ICON_MENU


def next_menu_key(keys: Sequence[str], current: str | None, step: int) -> str | None:
    """在可用菜单项中循环移动；当前项失效时从头/尾进入。"""
    if not keys:
        return None
    if current not in keys:
        return keys[0] if step >= 0 else keys[-1]
    index = keys.index(current)
    return keys[(index + step) % len(keys)]


class MenuItem(TypedDict):
    """菜单项的控件。"""

    frame: ctk.CTkFrame
    btn: ctk.CTkButton


class TrayMenu(ctk.CTkToplevel):
    """置顶、不抢焦点的托盘右键菜单。"""

    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    GWL_EXSTYLE = -20

    def __init__(
        self,
        parent: tk.Misc,
        callbacks: dict[str, Callable[[], None]],
    ) -> None:
        super().__init__(parent)

        self.callbacks = callbacks
        self._is_running = False
        self._luker_state = LukerState.STOPPED
        self._window_visible = False

        self.COLORS = config.get_theme_colors()

        self.UI_FONT = get_ui_font()

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', MOTION_WINDOW_ALPHA if config.blur_enabled else 1.0)
        apply_window_rounding(self, context="托盘菜单")

        # 外层只保留系统圆角，面板颜色铺满窗口避免出现第二层圆角亮边
        self.configure(fg_color=self.COLORS['card'])

        self._animation_phase = 0.0
        self._menu_animation_id: str | None = None
        self._menu_animation_active = False
        self._menu_logo_gray = True
        self._mouse_poll_id: str | None = None
        self._fade = WindowFade(self)
        self._selected_key: str | None = None
        self._previous_foreground = 0
        self._menu_focused = False

        self._build_menu()
        self._bind_keyboard()

        config.add_theme_change_callback(self._on_theme_change)
        config.add_blur_change_callback(self._on_blur_change)

        self.after(DELAY_BLUR_TRAY_MS, self._setup_blur)
        self.after(DELAY_NOACTIVATE_TRAY_MS, self._set_no_activate)

        self.withdraw()

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        """主题变化时重建菜单，保证托盘菜单与新主题一致。"""
        if not self.winfo_exists():
            return

        self.COLORS = new_colors
        self.configure(fg_color=self.COLORS['card'])

        was_viewable = self.__dict__.get('_menu_focused', False)
        selected = self.__dict__.get('_selected_key')
        self._selected_key = None
        for child in self.winfo_children():
            child.destroy()

        self._build_menu()
        self.update_state(
            self._is_running,
            self._window_visible,
            self._luker_state,
        )
        self._setup_blur()

        if was_viewable:
            if selected in self._navigable_keys():
                self._select_key(selected)
            else:
                self._select_first()
            self.focus_force()
            self._start_menu_animation()
            self._start_mouse_poll()

    def _on_blur_change(self, _enabled: bool) -> None:
        if self.winfo_exists():
            self._setup_blur()

    def _set_no_activate(self, enabled: bool = True) -> None:
        """切换 WS_EX_NOACTIVATE；键盘模式下让菜单可以接收焦点。"""
        try:
            hwnd = win32_api.user32.GetParent(self.winfo_id())
            ex_style = win32_api.user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            if enabled:
                new_style = ex_style | self.WS_EX_NOACTIVATE | self.WS_EX_TOOLWINDOW
            else:
                new_style = (ex_style & ~self.WS_EX_NOACTIVATE) | self.WS_EX_TOOLWINDOW
            win32_api.user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, new_style & 0xFFFFFFFF)
        except Exception:
            logger.warning("设置无焦点窗口失败", exc_info=True)

    def _bind_keyboard(self) -> None:
        self.bind('<Up>', self._on_key_up)
        self.bind('<Down>', self._on_key_down)
        self.bind('<Home>', self._on_key_home)
        self.bind('<End>', self._on_key_end)
        self.bind('<Return>', self._on_key_activate)
        self.bind('<KP_Enter>', self._on_key_activate)
        self.bind('<Escape>', self._on_key_escape)
        self.bind('<Tab>', self._on_key_down)
        self.bind('<Shift-Tab>', self._on_key_up)

    def _navigable_keys(self) -> list[str]:
        """按视觉顺序返回当前可见且未禁用的菜单项。"""
        keys: list[str] = []
        for key, item in self.menu_items.items():
            try:
                if item['frame'].winfo_manager() != "pack":
                    continue
                if str(item['btn'].cget('state')) == "disabled":
                    continue
            except (tk.TclError, AttributeError):
                continue
            keys.append(key)
        return keys

    def _select_first(self) -> None:
        keys = self._navigable_keys()
        if keys:
            self._select_key(keys[0])

    def _select_key(self, key: str | None) -> None:
        if key == self._selected_key:
            return
        self._clear_selection()
        if key is None:
            return
        item = self.menu_items.get(key)
        if item is None:
            return
        try:
            item['frame'].configure(
                fg_color=self.COLORS['card_hover'],
                border_width=1,
                border_color=self.COLORS['accent'],
            )
        except tk.TclError:
            return
        self._selected_key = key

    def _clear_selection(self) -> None:
        key = self.__dict__.get('_selected_key')
        self._selected_key = None
        if key is None:
            return
        item = self.menu_items.get(key)
        if item is None:
            return
        with contextlib.suppress(tk.TclError):
            item['frame'].configure(fg_color="transparent", border_width=0)

    def _clamp_selection(self) -> None:
        """状态变化后让高亮落在仍然可用的一项上。"""
        if not self.__dict__.get('_menu_focused', False):
            return
        keys = self._navigable_keys()
        if not keys:
            self._clear_selection()
            return
        if self._selected_key not in keys:
            self._select_key(keys[0])

    def _move_selection(self, step: int) -> str:
        keys = self._navigable_keys()
        next_key = next_menu_key(keys, self._selected_key, step)
        self._select_key(next_key)
        return "break"

    def _on_key_up(self, _event: tk.Event | None = None) -> str:
        return self._move_selection(-1)

    def _on_key_down(self, _event: tk.Event | None = None) -> str:
        return self._move_selection(1)

    def _on_key_home(self, _event: tk.Event | None = None) -> str:
        keys = self._navigable_keys()
        if keys:
            self._select_key(keys[0])
        return "break"

    def _on_key_end(self, _event: tk.Event | None = None) -> str:
        keys = self._navigable_keys()
        if keys:
            self._select_key(keys[-1])
        return "break"

    def _on_key_activate(self, _event: tk.Event | None = None) -> str:
        if self._selected_key is None:
            self._select_first()
        item = self.menu_items.get(self._selected_key or "")
        if item is None:
            return "break"
        try:
            if str(item['btn'].cget('state')) == "disabled":
                return "break"
            item['btn'].invoke()
        except tk.TclError:
            pass
        return "break"

    def _on_key_escape(self, _event: tk.Event | None = None) -> str:
        self.hide()
        return "break"

    def _start_mouse_poll(self) -> None:
        if self._mouse_poll_id is None:
            self._mouse_poll_id = self.after(POLL_TRAY_MOUSE_MS, self._check_mouse_outside)

    def _stop_mouse_poll(self) -> None:
        if self._mouse_poll_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._mouse_poll_id)
            self._mouse_poll_id = None

    def _check_mouse_outside(self) -> None:
        """菜单可见时轮询鼠标，左键点击菜单外部则收起。"""
        self._mouse_poll_id = None
        if not self.winfo_viewable():
            return

        try:
            mouse_x = self.winfo_pointerx()
            mouse_y = self.winfo_pointery()

            menu_x = self.winfo_x()
            menu_y = self.winfo_y()
            menu_w = self.winfo_width()
            menu_h = self.winfo_height()

            in_menu = menu_x <= mouse_x <= menu_x + menu_w and menu_y <= mouse_y <= menu_y + menu_h

            if not in_menu:
                left_button = win32_api.user32.GetAsyncKeyState(0x01) & 0x8000
                if left_button:
                    # 点击外部时焦点已经交给目标窗口，不要再抢回来
                    self.hide(restore_focus=False)
                    return

        except Exception:
            pass

        self._mouse_poll_id = self.after(POLL_TRAY_MOUSE_MS, self._check_mouse_outside)

    def _setup_blur(self) -> None:
        fade = self.__dict__.get('_fade')
        if fade is not None:
            fade.cancel()
        sync_window_blur(
            self,
            self.COLORS['bg'],
            enabled=config.blur_enabled,
            window_alpha=MOTION_WINDOW_ALPHA,
            tint_alpha=0xEE,
            context="托盘菜单",
        )

    def _set_menu_logo_stopped(self) -> None:
        bars = getattr(self, '_menu_logo_bars', None)
        if not bars or self._menu_logo_gray:
            return
        for bar in bars:
            bar.configure(fg_color=LOGO_STOPPED_COLOR)
        self._menu_logo_gray = True

    def _stop_menu_animation(self) -> None:
        if self._menu_animation_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._menu_animation_id)
            self._menu_animation_id = None
        self._menu_animation_active = False

    def _apply_menu_logo_state(self) -> None:
        if self._luker_state is LukerState.READY:
            self._start_menu_animation()
        else:
            self._set_menu_logo_stopped()
            self._stop_menu_animation()

    def _start_menu_animation(self) -> None:
        if self._luker_state is not LukerState.READY:
            self._set_menu_logo_stopped()
            return
        if self._menu_animation_active:
            return
        self._menu_animation_active = True
        self._animate_menu()

    def _animate_menu(self) -> None:
        self._menu_animation_id = None
        if not self.winfo_viewable():
            self._menu_animation_active = False
            return

        if self._luker_state is not LukerState.READY:
            self._set_menu_logo_stopped()
            self._menu_animation_active = False
            return

        bars = getattr(self, '_menu_logo_bars', None)
        if not bars:
            self._menu_animation_active = False
            return

        self._menu_logo_gray = False
        self._animation_phase = (self._animation_phase + LOGO_GLOW_STEP) % 1.0

        for index, bar in enumerate(bars):
            bar.configure(fg_color=logo_bar_glow_color(index, self._animation_phase))

        self._menu_animation_id = self.after(LOGO_GLOW_INTERVAL_MS, self._animate_menu)

    def _build_menu(self) -> None:
        main = ctk.CTkFrame(self, fg_color=self.COLORS['card'], corner_radius=0)
        main.pack(fill="both", expand=True)

        self._build_menu_header(main)

        items_frame = ctk.CTkFrame(main, fg_color="transparent")
        items_frame.pack(fill="x", padx=PAD_MENU, pady=PAD_MENU)
        self.menu_items: dict[str, MenuItem] = {}
        self._build_menu_items(items_frame)
        self._build_menu_footer(items_frame)

    def _build_menu_header(self, parent: tk.Misc) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=HEADER_PAD_X, pady=(HEADER_PAD_Y, GAP_SECTION))

        logo = ctk.CTkFrame(header, fg_color="transparent")
        logo.pack(side="left")

        self._menu_logo_bars = []
        self._menu_logo_gray = True
        for _ in range(4):
            bar = ctk.CTkFrame(
                logo,
                width=LOGO_BAR_WIDTH,
                height=LOGO_BAR_HEIGHT,
                fg_color=LOGO_STOPPED_COLOR,
                corner_radius=RADIUS_LOGO,
            )
            bar.pack(side="left", padx=LOGO_BAR_GAP)
            self._menu_logo_bars.append(bar)

        ctk.CTkLabel(
            header,
            text="Luker",
            font=ctk.CTkFont(family=self.UI_FONT, size=TITLE_FONT_SIZE, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left", padx=(GAP_SECTION, 0))

        ctk.CTkFrame(parent, height=SEPARATOR_HEIGHT, fg_color=self.COLORS['border']).pack(
            fill="x", padx=GAP_SECTION
        )

    def _build_menu_items(self, parent: tk.Misc) -> None:
        self.menu_items['window'] = self._create_menu_item(
            parent, 'window', "显示日志窗口", self._on_toggle_window
        )

        ctk.CTkFrame(parent, height=SEPARATOR_HEIGHT, fg_color=self.COLORS['border']).pack(
            fill="x", padx=PAD_MENU, pady=GAP_MENU_SEPARATOR
        )

        # Luker 控制区域：启动/停止合并为一个动态按钮
        self.menu_items['luker_toggle'] = self._create_menu_item(
            parent, 'play', "启动 Luker", self._on_luker_toggle, color=self.COLORS['success']
        )
        self.menu_items['restart'] = self._create_menu_item(
            parent, 'refresh', "重启 Luker", self._on_restart, color=self.COLORS['accent']
        )
        self.menu_items['luker_browser'] = self._create_menu_item(
            parent, 'globe', "Luker 页面", self._on_open_browser, color=self.COLORS['info']
        )

    def _build_menu_footer(self, parent: tk.Misc) -> None:
        self._bottom_separator = ctk.CTkFrame(
            parent, height=SEPARATOR_HEIGHT, fg_color=self.COLORS['border']
        )
        self._bottom_separator.pack(fill="x", padx=PAD_MENU, pady=GAP_MENU_SEPARATOR)
        self.menu_items['settings'] = self._create_menu_item(
            parent, 'settings', "设置", self._on_settings
        )
        self.menu_items['exit'] = self._create_menu_item(
            parent, 'power', "退出", self._on_exit, color=self.COLORS['error']
        )

    def _create_menu_item(
        self,
        parent: tk.Misc,
        icon: MenuIcon,
        text: str,
        command: Callable[[], None],
        color: str | None = None,
        visible: bool = True,
    ) -> MenuItem:
        """创建菜单项；visible=False 时由 update_state 控制显示。"""
        frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=RADIUS_CARD)
        if visible:
            frame.pack(fill="x", pady=GAP_MENU_ITEM)

        icon_color = self.COLORS['text']
        text_color = color if color is not None else self.COLORS['text']
        btn = make_button(
            frame,
            'menu',
            self.COLORS,
            text=text,
            image=menu_icon(icon, icon_color, size=MENU_ICON_SIZE),
            compound='left',
            font_family=self.UI_FONT,
            anchor="w",
            text_color=text_color,
            command=command,
        )
        btn.pack(fill="x", padx=GAP_INLINE_SM)

        return {'frame': frame, 'btn': btn}

    def _on_toggle_window(self) -> None:
        self.hide()
        if self._window_visible:
            self.callbacks['hide_window']()
        else:
            self.callbacks['show_window']()

    def _on_luker_toggle(self) -> None:
        self.hide()
        if self._is_running:
            self.callbacks['stop']()
        else:
            self.callbacks['start']()

    def _on_restart(self) -> None:
        self.hide()
        self.callbacks['restart']()

    def _on_settings(self) -> None:
        self.hide()
        self.callbacks['settings']()

    def _on_open_browser(self) -> None:
        self.hide()
        self.callbacks['open_browser']()

    def _on_exit(self) -> None:
        self.hide()
        self.callbacks['exit']()

    def _apply_toggle_item(
        self,
        key: str,
        running: bool,
        *,
        running_text: str,
        stopped_text: str,
    ) -> None:
        """按运行状态重配启动/停止菜单项的文本、颜色和图标。"""
        item = self.menu_items.get(key)
        if item is None:
            return
        text = running_text if running else stopped_text
        color = self.COLORS['error'] if running else self.COLORS['success']
        icon: MenuIcon = 'stop' if running else 'play'
        item['btn'].configure(
            text=text,
            text_color=color,
            image=menu_icon(icon, self.COLORS['text'], size=MENU_ICON_SIZE),
        )

    def _apply_luker_toggle(self) -> None:
        self._apply_toggle_item(
            'luker_toggle',
            self._is_running,
            running_text="停止 Luker",
            stopped_text="启动 Luker",
        )

        restart = self.menu_items.get('restart')
        if restart is not None:
            if self._is_running:
                restart['btn'].configure(
                    state="normal",
                    text_color=self.COLORS['accent'],
                    image=menu_icon('refresh', self.COLORS['text'], size=MENU_ICON_SIZE),
                )
            else:
                restart['btn'].configure(
                    state="disabled",
                    text_color=self.COLORS['text_muted'],
                    text_color_disabled=self.COLORS['text_muted'],
                    image=menu_icon('refresh', self.COLORS['text_muted'], size=MENU_ICON_SIZE),
                )

    def set_luker_state(self, state: LukerState) -> None:
        """主程序推送就绪状态，菜单未打开时也记住以便下次直接生效。"""
        self._luker_state = state
        self._is_running = state is not LukerState.STOPPED
        self._apply_luker_toggle()
        self._apply_menu_logo_state()

    def update_state(
        self,
        is_running: bool,
        window_visible: bool,
        luker_state: LukerState | None = None,
    ) -> None:
        self._is_running = is_running
        self._luker_state = (
            luker_state
            if luker_state is not None
            else (LukerState.STARTING if is_running else LukerState.STOPPED)
        )
        self._window_visible = window_visible

        window_text = "隐藏日志窗口" if window_visible else "显示日志窗口"
        window_item = self.menu_items.get('window')
        if window_item is not None:
            window_item['btn'].configure(text=window_text)

        self._apply_luker_toggle()
        self._apply_menu_logo_state()
        self._clamp_selection()

    def show_at(self, x: int, y: int, previous_foreground: int = 0) -> None:
        """在物理坐标 (x, y) 附近显示，并限制在光标所在显示器。"""
        was_visible = self.winfo_viewable()
        if not was_visible:
            self._previous_foreground = previous_foreground or self._get_foreground()
            self._selected_key = None

        monitor = get_monitor_info(point=(x, y))
        scale = sync_window_scaling(self, monitor.scale)
        self.update_idletasks()

        width = round(MENU_WIDTH * scale)
        # reqheight 是缩放后的物理像素；CTk 的 geometry 接收逻辑尺寸
        height = self.winfo_reqheight()
        x, y = clamp_popup_position(x, y, width, height, monitor)
        logical_height = max(1, math.ceil(height / scale))

        fade = self.__dict__.get('_fade')
        if fade is not None:
            if config.blur_enabled:
                fade.start(
                    MOTION_TRAY_FADE_START,
                    MOTION_WINDOW_ALPHA,
                    duration_ms=MOTION_TRAY_FADE_MS,
                )
            else:
                fade.cancel(reset=1.0)

        # 允许键盘输入后再显示，避免先以 NOACTIVATE 出现再切换样式
        self._set_no_activate(False)
        self.geometry(format_geometry(MENU_WIDTH, logical_height, x, y))
        self.deiconify()
        self.lift()
        apply_window_rounding(self, context="托盘菜单")
        self._force_foreground()
        self.focus_force()

        self._menu_focused = True
        if was_visible:
            self._clamp_selection()
        else:
            self._select_first()

        self._start_menu_animation()
        self._start_mouse_poll()

    def hide(self, restore_focus: bool = True) -> None:
        self._clear_selection()
        focused = self.__dict__.get('_menu_focused', False)
        self._menu_focused = False
        fade = self.__dict__.get('_fade')
        if fade is not None:
            base = MOTION_WINDOW_ALPHA if config.blur_enabled else 1.0
            fade.cancel(reset=base)
        self._stop_menu_animation()
        self._stop_mouse_poll()
        self.withdraw()
        if focused:
            self._set_no_activate(True)
        if restore_focus and self.__dict__.get('_previous_foreground'):
            self._restore_foreground()

    def _get_foreground(self) -> int:
        try:
            return int(win32_api.user32.GetForegroundWindow())
        except Exception:
            return 0

    def _set_foreground(self, hwnd: int) -> bool:
        """把窗口设为系统前台。

        托盘回调来自 explorer，不属于本进程的输入事件，直接调用
        SetForegroundWindow 会被 Windows 前台锁拒绝；临时附加到当前前台
        线程的输入队列可以稳定绕过限制，随后立即分离。
        """
        if not hwnd:
            return False
        user32 = win32_api.user32
        kernel32 = win32_api.kernel32
        try:
            if user32.GetForegroundWindow() == hwnd:
                return True
            foreground = user32.GetForegroundWindow()
            foreground_thread = (
                user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
            )
            current_thread = kernel32.GetCurrentThreadId()
            attached = False
            try:
                if foreground_thread and foreground_thread != current_thread:
                    attached = bool(
                        user32.AttachThreadInput(current_thread, foreground_thread, True)
                    )
                return bool(user32.SetForegroundWindow(hwnd))
            finally:
                if attached:
                    user32.AttachThreadInput(current_thread, foreground_thread, False)
        except Exception:
            logger.warning("设置前台窗口失败", exc_info=True)
            return False

    def _force_foreground(self) -> None:
        try:
            hwnd = win32_api.user32.GetParent(self.winfo_id())
        except Exception:
            logger.warning("读取托盘菜单窗口句柄失败", exc_info=True)
            return
        self._set_foreground(hwnd)

    def _restore_foreground(self) -> None:
        previous = self.__dict__.get('_previous_foreground', 0)
        self._previous_foreground = 0
        if not previous:
            return
        try:
            if win32_api.user32.IsWindow(previous) and win32_api.user32.IsWindowVisible(previous):
                self._set_foreground(previous)
        except Exception:
            logger.debug("恢复前台窗口失败", exc_info=True)

    def destroy(self) -> None:
        self._clear_selection()
        fade = self.__dict__.get('_fade')
        if fade is not None:
            fade.cancel()
        self._stop_menu_animation()
        self._stop_mouse_poll()
        config.remove_theme_change_callback(self._on_theme_change)
        config.remove_blur_change_callback(self._on_blur_change)
        super().destroy()
