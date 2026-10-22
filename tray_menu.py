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
from theme import (
    LOGO_BAR_COLORS,
    LOGO_BAR_RGB,
    blend_color,
    is_light_color,
    logo_bar_brightness,
)
from win_utils import apply_window_blur, disable_window_blur, get_ui_font

logger = logging.getLogger(__name__)

MENU_WIDTH = 240
HEADER_PAD_X = 18
HEADER_PAD_Y = 14
TITLE_FONT_SIZE = 18
LOGO_BAR_WIDTH = 4
LOGO_BAR_HEIGHT = 24


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
        self._window_visible = False
        self._gcl_enabled = False

        self.COLORS = config.get_theme_colors()

        self.UI_FONT = get_ui_font()

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 1.0 if is_light_color(self.COLORS['bg']) else 0.97)

        self.configure(fg_color=self.COLORS['bg'])

        self._animation_phase = 0.0
        self._menu_animation_id: str | None = None
        self._menu_animation_active = False
        self._mouse_poll_id: str | None = None

        self._build_menu()

        config.add_theme_change_callback(self._on_theme_change)

        self.after(50, self._setup_blur)
        self.after(100, self._setup_no_activate)

        self.withdraw()

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        """主题变化时重建菜单，保证托盘菜单与新主题一致。"""
        if not self.winfo_exists():
            return

        self.COLORS = new_colors
        self.configure(fg_color=self.COLORS['bg'])

        for child in self.winfo_children():
            child.destroy()

        gcl_running = self._gcl_running
        self._build_menu()
        self.update_state(self._is_running, self._window_visible, self._gcl_enabled, gcl_running)
        self._setup_blur()

        if self.winfo_viewable():
            self._start_menu_animation()
            self._start_mouse_poll()

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
        if is_light_color(self.COLORS['bg']):
            self.attributes('-alpha', 1.0)
            disable_window_blur(self, context="托盘菜单")
            return

        # 先重置再设置透明度，确保从浅色主题切回时重新启用分层窗口
        self.attributes('-alpha', 1.0)
        self.attributes('-alpha', 0.97)
        apply_window_blur(self, self.COLORS['bg'], alpha=0xEE, context="托盘菜单")

    def _start_menu_animation(self) -> None:
        if self._menu_animation_active:
            return
        self._menu_animation_active = True
        self._animate_menu()

    def _animate_menu(self) -> None:
        self._menu_animation_id = None
        if not self.winfo_viewable():
            self._menu_animation_active = False
            return

        self._animation_phase = (self._animation_phase + 0.05) % 1.0

        if hasattr(self, '_menu_logo_bars'):
            for index, bar in enumerate(self._menu_logo_bars):
                brightness = logo_bar_brightness(index, self._animation_phase)
                bar.configure(fg_color=blend_color((0, 0, 0), LOGO_BAR_RGB[index], brightness))

        self._menu_animation_id = self.after(50, self._animate_menu)

    def _build_menu(self) -> None:
        main = ctk.CTkFrame(self, fg_color=self.COLORS['card'], corner_radius=16)
        main.pack(fill="both", expand=True, padx=2, pady=2)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", padx=HEADER_PAD_X, pady=(HEADER_PAD_Y, 12))

        logo = ctk.CTkFrame(header, fg_color="transparent")
        logo.pack(side="left")

        self._menu_logo_bars = []
        for c in LOGO_BAR_COLORS:
            bar = ctk.CTkFrame(
                logo,
                width=LOGO_BAR_WIDTH,
                height=LOGO_BAR_HEIGHT,
                fg_color=c,
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

        ctk.CTkFrame(main, height=1, fg_color=self.COLORS['border']).pack(fill="x", padx=12)

        items_frame = ctk.CTkFrame(main, fg_color="transparent")
        items_frame.pack(fill="x", padx=8, pady=8)

        self.menu_items: dict[str, MenuItem] = {}

        self.menu_items['window'] = self._create_menu_item(
            items_frame, "📋", "显示日志窗口", self._on_toggle_window
        )

        ctk.CTkFrame(items_frame, height=1, fg_color=self.COLORS['border']).pack(
            fill="x", padx=8, pady=6
        )

        # Luker 控制区域：启动/停止合并为一个动态按钮
        self.menu_items['luker_toggle'] = self._create_menu_item(
            items_frame, "▶", "启动 Luker", self._on_luker_toggle, color=self.COLORS['success']
        )

        self.menu_items['restart'] = self._create_menu_item(
            items_frame, "🔄", "重启 Luker", self._on_restart, color=self.COLORS['accent']
        )

        self.menu_items['luker_browser'] = self._create_menu_item(
            items_frame, "🌐", "Luker 页面", self._on_open_browser, color=self.COLORS['info']
        )

        # GCL 菜单项按配置动态显示
        self._gcl_separator = ctk.CTkFrame(items_frame, height=1, fg_color=self.COLORS['border'])

        self.menu_items['gcl_toggle'] = self._create_menu_item(
            items_frame,
            "▶",
            "启动 GCL",
            self._on_gcl_toggle,
            color=self.COLORS['success'],
            visible=False,
        )

        self.menu_items['gcl_browser'] = self._create_menu_item(
            items_frame,
            "🌐",
            "GCL 页面",
            self._on_gcl_browser,
            color=self.COLORS['info'],
            visible=False,
        )

        self._bottom_separator = ctk.CTkFrame(items_frame, height=1, fg_color=self.COLORS['border'])
        self._bottom_separator.pack(fill="x", padx=8, pady=6)

        self.menu_items['settings'] = self._create_menu_item(
            items_frame, "⚙️", "设置", self._on_settings
        )

        self.menu_items['exit'] = self._create_menu_item(
            items_frame, "🚪", "退出", self._on_exit, color=self.COLORS['error']
        )

        self._gcl_running = False

    def _create_menu_item(
        self,
        parent: tk.Misc,
        icon: str,
        text: str,
        command: Callable[[], None],
        color: str | None = None,
        visible: bool = True,
    ) -> MenuItem:
        """创建菜单项；visible=False 时由 update_state 控制显示。"""
        frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8)
        if visible:
            frame.pack(fill="x", pady=2)

        btn = ctk.CTkButton(
            frame,
            text=f"{icon}  {text}",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            fg_color="transparent",
            hover_color=self.COLORS['card_hover'],
            text_color=color if color else self.COLORS['text'],
            anchor="w",
            corner_radius=8,
            height=38,
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

    def update_state(
        self,
        is_running: bool,
        window_visible: bool,
        gcl_enabled: bool = False,
        gcl_running: bool = False,
    ) -> None:
        self._is_running = is_running
        self._window_visible = window_visible
        self._gcl_enabled = gcl_enabled

        window_text = "隐藏日志窗口" if window_visible else "显示日志窗口"
        self.menu_items['window']['btn'].configure(text=f"📋  {window_text}")

        # 启停按钮共用一个位置，根据状态切换文案和颜色
        if is_running:
            self.menu_items['luker_toggle']['btn'].configure(
                text="⏹  停止 Luker", text_color=self.COLORS['error']
            )
            self.menu_items['restart']['btn'].configure(
                state="normal", text_color=self.COLORS['accent']
            )
        else:
            self.menu_items['luker_toggle']['btn'].configure(
                text="▶  启动 Luker", text_color=self.COLORS['success']
            )
            self.menu_items['restart']['btn'].configure(
                state="disabled", text_color=self.COLORS['text_muted']
            )

        # 更新 GCL 菜单项状态
        self._gcl_running = gcl_running
        if gcl_enabled:
            # 先隐藏再按顺序插到底部分隔线之前
            self._gcl_separator.pack_forget()
            self.menu_items['gcl_toggle']['frame'].pack_forget()
            self.menu_items['gcl_browser']['frame'].pack_forget()

            self._gcl_separator.pack(fill="x", padx=8, pady=6, before=self._bottom_separator)
            self.menu_items['gcl_toggle']['frame'].pack(
                fill="x", pady=2, before=self._bottom_separator
            )
            self.menu_items['gcl_browser']['frame'].pack(
                fill="x", pady=2, before=self._bottom_separator
            )

            if gcl_running:
                self.menu_items['gcl_toggle']['btn'].configure(
                    text="⏹  停止 GCL", text_color=self.COLORS['error']
                )
            else:
                self.menu_items['gcl_toggle']['btn'].configure(
                    text="▶  启动 GCL", text_color=self.COLORS['success']
                )
        else:
            self._gcl_separator.pack_forget()
            self.menu_items['gcl_toggle']['frame'].pack_forget()
            self.menu_items['gcl_browser']['frame'].pack_forget()

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

        self._setup_no_activate()

        self._start_menu_animation()
        self._start_mouse_poll()

    def hide(self) -> None:
        if self._menu_animation_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._menu_animation_id)
            self._menu_animation_id = None
        self._menu_animation_active = False

        if self._mouse_poll_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._mouse_poll_id)
            self._mouse_poll_id = None

        self.withdraw()
