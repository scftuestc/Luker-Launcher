"""托盘右键菜单。"""

import contextlib
import logging
import math
import tkinter as tk
import webbrowser
from collections.abc import Callable
from ctypes import windll
from typing import TypedDict

import customtkinter as ctk

from config import config
from dpi import clamp_popup_position, format_geometry, get_monitor_info, sync_window_scaling
from luker_readiness import LukerState
from theme import (
    LOGO_GLOW_INTERVAL_MS,
    LOGO_GLOW_STEP,
    LOGO_STOPPED_COLOR,
    logo_bar_glow_color,
)
from ui_icons import MenuIcon, menu_icon
from ui_style import make_button
from win_utils import apply_window_rounding, get_ui_font, sync_window_blur

logger = logging.getLogger(__name__)

MENU_WIDTH = 240
HEADER_PAD_X = 18
HEADER_PAD_Y = 14
TITLE_FONT_SIZE = 18
LOGO_BAR_WIDTH = 4
LOGO_BAR_HEIGHT = 24
MENU_ICON_SIZE = 18


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
        self._gcl_enabled = False
        self._gcl_running = False

        self.COLORS = config.get_theme_colors()

        self.UI_FONT = get_ui_font()

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.95 if config.blur_enabled else 1.0)
        apply_window_rounding(self, context="托盘菜单")

        # 外层只保留系统圆角，面板颜色铺满窗口避免出现第二层圆角亮边
        self.configure(fg_color=self.COLORS['card'])

        self._animation_phase = 0.0
        self._menu_animation_id: str | None = None
        self._menu_animation_active = False
        self._menu_logo_gray = True
        self._mouse_poll_id: str | None = None

        self._build_menu()

        config.add_theme_change_callback(self._on_theme_change)
        config.add_blur_change_callback(self._on_blur_change)

        self.after(50, self._setup_blur)
        self.after(100, self._setup_no_activate)

        self.withdraw()

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        """主题变化时重建菜单，保证托盘菜单与新主题一致。"""
        if not self.winfo_exists():
            return

        self.COLORS = new_colors
        self.configure(fg_color=self.COLORS['card'])

        for child in self.winfo_children():
            child.destroy()

        gcl_running = self._gcl_running
        self._build_menu()
        self.update_state(
            self._is_running,
            self._window_visible,
            self._gcl_enabled,
            gcl_running,
            self._luker_state,
        )
        self._setup_blur()

        if self.winfo_viewable():
            self._start_menu_animation()
            self._start_mouse_poll()

    def _on_blur_change(self, _enabled: bool) -> None:
        if self.winfo_exists():
            self._setup_blur()

    def _setup_no_activate(self) -> None:
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            ex_style = windll.user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            new_style = ex_style | self.WS_EX_NOACTIVATE | self.WS_EX_TOOLWINDOW
            windll.user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, new_style)
        except Exception:
            logger.warning("设置无焦点窗口失败", exc_info=True)

    def _start_mouse_poll(self) -> None:
        if self._mouse_poll_id is None:
            self._mouse_poll_id = self.after(100, self._check_mouse_outside)

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
                left_button = windll.user32.GetAsyncKeyState(0x01) & 0x8000
                if left_button:
                    self.hide()
                    return

        except Exception:
            pass

        self._mouse_poll_id = self.after(100, self._check_mouse_outside)

    def _setup_blur(self) -> None:
        sync_window_blur(
            self,
            self.COLORS['bg'],
            enabled=config.blur_enabled,
            window_alpha=0.95,
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
        items_frame.pack(fill="x", padx=8, pady=8)
        self.menu_items: dict[str, MenuItem] = {}
        self._build_menu_items(items_frame)
        self._build_menu_footer(items_frame)

    def _build_menu_header(self, parent: tk.Misc) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=HEADER_PAD_X, pady=(HEADER_PAD_Y, 12))

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
                corner_radius=2,
            )
            bar.pack(side="left", padx=1)
            self._menu_logo_bars.append(bar)

        ctk.CTkLabel(
            header,
            text="Luker",
            font=ctk.CTkFont(family=self.UI_FONT, size=TITLE_FONT_SIZE, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left", padx=(12, 0))

        ctk.CTkFrame(parent, height=1, fg_color=self.COLORS['border']).pack(fill="x", padx=12)

    def _build_menu_items(self, parent: tk.Misc) -> None:
        self.menu_items['window'] = self._create_menu_item(
            parent, 'window', "显示日志窗口", self._on_toggle_window
        )

        ctk.CTkFrame(parent, height=1, fg_color=self.COLORS['border']).pack(
            fill="x", padx=8, pady=6
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

        # GCL 菜单项按配置动态显示
        self._gcl_separator = ctk.CTkFrame(parent, height=1, fg_color=self.COLORS['border'])
        self.menu_items['gcl_toggle'] = self._create_menu_item(
            parent,
            'play',
            "启动 GCL",
            self._on_gcl_toggle,
            color=self.COLORS['success'],
            visible=False,
        )
        self.menu_items['gcl_browser'] = self._create_menu_item(
            parent,
            'gcl',
            "GCL 页面",
            self._on_gcl_browser,
            color=self.COLORS['info'],
            visible=False,
        )

    def _build_menu_footer(self, parent: tk.Misc) -> None:
        self._bottom_separator = ctk.CTkFrame(parent, height=1, fg_color=self.COLORS['border'])
        self._bottom_separator.pack(fill="x", padx=8, pady=6)
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
        frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=10)
        if visible:
            frame.pack(fill="x", pady=2)

        icon_color = color if color is not None else self.COLORS['text']
        btn = make_button(
            frame,
            'menu',
            self.COLORS,
            text=text,
            image=menu_icon(icon, icon_color, size=MENU_ICON_SIZE),
            compound='left',
            font_family=self.UI_FONT,
            anchor="w",
            text_color=icon_color,
            command=command,
        )
        btn.pack(fill="x", padx=4)

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

    def _on_gcl_toggle(self) -> None:
        self.hide()
        if self._gcl_running:
            self.callbacks['gcl_stop']()
        else:
            self.callbacks['gcl_start']()

    def _on_gcl_browser(self) -> None:
        self.hide()
        webbrowser.open(config.gcl_url)

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
            image=menu_icon(icon, color, size=MENU_ICON_SIZE),
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
                    image=menu_icon('refresh', self.COLORS['accent'], size=MENU_ICON_SIZE),
                )
            else:
                restart['btn'].configure(
                    state="disabled",
                    text_color=self.COLORS['text_muted'],
                    text_color_disabled=self.COLORS['text_muted'],
                    image=menu_icon('refresh', self.COLORS['text_muted'], size=MENU_ICON_SIZE),
                )

    def _apply_gcl_toggle(self) -> None:
        self._apply_toggle_item(
            'gcl_toggle',
            self._gcl_running,
            running_text="停止 GCL",
            stopped_text="启动 GCL",
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
        gcl_enabled: bool = False,
        gcl_running: bool = False,
        luker_state: LukerState | None = None,
    ) -> None:
        self._is_running = is_running
        self._luker_state = (
            luker_state
            if luker_state is not None
            else (LukerState.STARTING if is_running else LukerState.STOPPED)
        )
        self._window_visible = window_visible
        self._gcl_enabled = gcl_enabled
        self._gcl_running = gcl_running

        window_text = "隐藏日志窗口" if window_visible else "显示日志窗口"
        window_item = self.menu_items.get('window')
        if window_item is not None:
            window_item['btn'].configure(text=window_text)

        self._apply_luker_toggle()
        self._apply_gcl_toggle()

        self._set_gcl_items_visible(gcl_enabled)
        self._apply_menu_logo_state()

    def _set_gcl_items_visible(self, visible: bool) -> None:
        """按 GCL 是否启用显示或隐藏分隔线和两个 GCL 菜单项。"""
        self._gcl_separator.pack_forget()
        self.menu_items['gcl_toggle']['frame'].pack_forget()
        self.menu_items['gcl_browser']['frame'].pack_forget()
        if not visible:
            return

        self._gcl_separator.pack(fill="x", padx=8, pady=6, before=self._bottom_separator)
        self.menu_items['gcl_toggle']['frame'].pack(fill="x", pady=2, before=self._bottom_separator)
        self.menu_items['gcl_browser']['frame'].pack(
            fill="x", pady=2, before=self._bottom_separator
        )

    def show_at(self, x: int, y: int) -> None:
        """在物理坐标 (x, y) 附近显示，并限制在光标所在显示器。"""
        monitor = get_monitor_info(point=(x, y))
        scale = sync_window_scaling(self, monitor.scale)
        self.update_idletasks()

        width = round(MENU_WIDTH * scale)
        # reqheight 是缩放后的物理像素；CTk 的 geometry 接收逻辑尺寸
        height = self.winfo_reqheight()
        x, y = clamp_popup_position(x, y, width, height, monitor)
        logical_height = max(1, math.ceil(height / scale))

        self.geometry(format_geometry(MENU_WIDTH, logical_height, x, y))
        self.deiconify()
        self.lift()
        apply_window_rounding(self, context="托盘菜单")

        self._setup_no_activate()

        self._start_menu_animation()
        self._start_mouse_poll()

    def hide(self) -> None:
        self._stop_menu_animation()
        self._stop_mouse_poll()
        self.withdraw()
