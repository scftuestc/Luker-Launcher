"""设置窗口。"""

import contextlib
import logging
import tkinter as tk
from collections.abc import Callable
from ctypes import windll

import customtkinter as ctk

from config import config
from dpi import (
    centered_position,
    clamp_window_position,
    discard_window_scaling,
    fit_logical_window_size,
    format_geometry,
    get_monitor_info,
    sync_window_scaling,
)
from path_dialogs import select_gcl_bat_path, select_luker_path
from theme import PRESET_THEMES
from win_utils import apply_blur, get_mono_font, get_ui_font

logger = logging.getLogger(__name__)

# CTkScrollableFrame 在 root 上注册的全局事件；CTk 6.0 销毁时不会解绑，
# 旧控件树会被 root 的绑定脚本一直引用。
_SCROLL_BINDING_SEQUENCES = (
    "<MouseWheel>",
    "<KeyPress-Shift_L>",
    "<KeyPress-Shift_R>",
    "<KeyRelease-Shift_L>",
    "<KeyRelease-Shift_R>",
)


def clear_scroll_bindings(widget: tk.Misc) -> None:
    """清除 CTkScrollableFrame 留在 root 上的全局绑定。

    应用同时只保留一个设置窗口，重建前清空这些序列，再由新的滚动区域
    重新注册；如果以后新增其他滚动容器，需要改为按实例移除。
    """
    for sequence in _SCROLL_BINDING_SEQUENCES:
        with contextlib.suppress(tk.TclError):
            widget.tk.call("bind", "all", sequence, "")


class SettingsWindow(ctk.CTkToplevel):
    """设置窗口：主题、PWA 模式、GCL 和 Luker 路径。"""

    def __init__(
        self,
        parent: tk.Misc,
        anchor_point: tuple[int, int] | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)

        self._destroyed = False
        self._on_close_callback = on_close

        self.COLORS = config.get_theme_colors()
        self.UI_FONT = get_ui_font()

        self.title("设置")
        self.resizable(False, False)

        # 托盘打开时跟随点击所在显示器；其他入口回退到父窗口显示器
        monitor = (
            get_monitor_info(point=anchor_point)
            if anchor_point is not None
            else get_monitor_info(hwnd=parent.winfo_id())
        )
        scale = sync_window_scaling(self, monitor.scale)
        logical_width, logical_height = fit_logical_window_size(600, 720, monitor, scale, margin=16)
        # 高度不足时由窗口内部的滚动区域承载
        physical_width = round(logical_width * scale)
        physical_height = round(logical_height * scale)
        x, y = centered_position(physical_width, physical_height, monitor)
        self.geometry(format_geometry(logical_width, logical_height, x, y))
        self._monitor_signature = (
            monitor.left,
            monitor.top,
            monitor.right,
            monitor.bottom,
            monitor.dpi,
        )

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.98)
        self.configure(fg_color=self.COLORS['bg'])

        self._drag_x = 0
        self._drag_y = 0

        self._build_ui()

        self.after(100, self._setup_blur)

        config.add_theme_change_callback(self._on_theme_change)

        self.bind('<Configure>', self._on_configure)
        self.bind('<Destroy>', self._on_destroy)

    def _on_configure(self, event: tk.Event) -> None:
        # 合并拖动过程中连续的 Configure 事件，空闲时只检查一次显示器
        if event.widget == self:
            self.after_idle(self._fit_to_current_monitor)

    def _fit_to_current_monitor(self) -> None:
        """移动到不同 DPI 的显示器后重新限制尺寸和位置。"""
        if self._destroyed or not self.winfo_exists():
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
        logical_width, logical_height = fit_logical_window_size(600, 720, monitor, scale, margin=16)
        physical_width = round(logical_width * scale)
        physical_height = round(logical_height * scale)
        x, y = clamp_window_position(
            self.winfo_x(),
            self.winfo_y(),
            physical_width,
            physical_height,
            monitor,
        )
        self.geometry(format_geometry(logical_width, logical_height, x, y))

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget == self:
            self._destroyed = True
            config.remove_theme_change_callback(self._on_theme_change)
            discard_window_scaling(self)
            clear_scroll_bindings(self)
            if self._on_close_callback is not None:
                self._on_close_callback()

    def is_alive(self) -> bool:
        if self._destroyed:
            return False
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _setup_blur(self) -> None:
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            apply_blur(hwnd, self.COLORS['bg'], alpha=0xEE)
        except Exception:
            logger.warning("设置窗口毛玻璃失败", exc_info=True)

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        if self._destroyed:
            return
        self.COLORS = new_colors
        # 延后重建，避免在主题卡片的点击回调里销毁当前控件
        self.after(0, self._rebuild_ui)

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=16)

        self._build_titlebar(main)

        scroll_frame = ctk.CTkScrollableFrame(
            main,
            fg_color="transparent",
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent'],
        )
        scroll_frame.pack(fill="both", expand=True, pady=(0, 8))

        self._build_theme_section(scroll_frame)

        self._build_pwa_section(scroll_frame)

        self._build_gcl_section(scroll_frame)

        self._build_path_section(scroll_frame)

        self._build_footer(main)

    def _build_titlebar(self, parent: tk.Misc) -> None:
        bar = ctk.CTkFrame(parent, height=48, fg_color=self.COLORS['card'], corner_radius=12)
        bar.pack(fill="x", pady=(0, 16))
        bar.pack_propagate(False)

        bar.bind('<Button-1>', self._start_drag)
        bar.bind('<B1-Motion>', self._on_drag)

        ctk.CTkLabel(
            bar,
            text="⚙️  设置",
            font=ctk.CTkFont(family=self.UI_FONT, size=16, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkButton(
            bar,
            text="✕",
            width=36,
            height=28,
            fg_color="transparent",
            hover_color=self.COLORS['error'],
            text_color=self.COLORS['text_dim'],
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            command=self.destroy,
        ).pack(side="right", padx=10)

    def _start_drag(self, e: tk.Event) -> None:
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _on_drag(self, e: tk.Event) -> None:
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _build_theme_section(self, parent: tk.Misc) -> None:
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 12))

        ctk.CTkLabel(
            header,
            text="🎨  主题颜色",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="点击卡片实时预览",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted'],
        ).pack(side="right")

        grid = ctk.CTkFrame(section, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 16))

        self.theme_cards: dict[str, ctk.CTkFrame] = {}
        current_theme = config.theme_name

        row = 0
        col = 0
        for theme_id, colors in PRESET_THEMES.items():
            card = self._create_theme_card(grid, theme_id, colors, current_theme == theme_id)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self.theme_cards[theme_id] = card

            col += 1
            if col >= 3:
                col = 0
                row += 1

        for i in range(3):
            grid.columnconfigure(i, weight=1)

    def _create_theme_card(
        self,
        parent: tk.Misc,
        theme_id: str,
        colors: dict[str, str],
        is_selected: bool,
    ) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=colors['card'],
            corner_radius=10,
            border_width=3 if is_selected else 1,
            border_color=colors['accent'] if is_selected else colors['border'],
        )

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        preview = ctk.CTkFrame(inner, fg_color="transparent", height=24)
        preview.pack(fill="x", pady=(0, 8))

        preview_colors = [colors['accent'], colors['success'], colors['info'], colors['warning']]
        for pc in preview_colors:
            ctk.CTkFrame(preview, width=28, height=20, fg_color=pc, corner_radius=4).pack(
                side="left", padx=2
            )

        name_label = ctk.CTkLabel(
            inner,
            text=f"{colors['icon']} {colors['short_name']}",
            font=ctk.CTkFont(family=self.UI_FONT, size=13, weight="bold"),
            text_color=colors['text'],
        )
        name_label.pack(anchor="w")

        if is_selected:
            ctk.CTkLabel(
                inner,
                text="✓ 当前主题",
                font=ctk.CTkFont(family=self.UI_FONT, size=11),
                text_color=colors['accent'],
            ).pack(anchor="w", pady=(4, 0))

        def on_click(e: tk.Event, tid: str = theme_id) -> None:
            self._select_theme(tid)

        card.bind('<Button-1>', on_click)
        inner.bind('<Button-1>', on_click)
        for child in inner.winfo_children():
            child.bind('<Button-1>', on_click)
            if hasattr(child, 'winfo_children'):
                for subchild in child.winfo_children():
                    subchild.bind('<Button-1>', on_click)

        return card

    def _select_theme(self, theme_id: str) -> None:
        if theme_id in PRESET_THEMES:
            config.theme_name = theme_id

    def _rebuild_ui(self) -> None:
        """按当前主题重建整个设置界面，让卡片、文字和选中状态一起刷新。"""
        if self._destroyed or not self.winfo_exists():
            return

        for child in self.winfo_children():
            child.destroy()

        clear_scroll_bindings(self)
        self._build_ui()
        self.configure(fg_color=self.COLORS['bg'])
        self._setup_blur()

    def _build_pwa_section(self, parent: tk.Misc) -> None:
        """构建 PWA 模式开关区域"""
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            header,
            text="🌐  PWA 浏览器模式",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left")

        self.pwa_switch = ctk.CTkSwitch(
            header,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text'],
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text'],
            button_hover_color=self.COLORS['accent'],
            command=self._on_pwa_toggle,
        )
        self.pwa_switch.pack(side="right")

        if config.use_pwa_mode:
            self.pwa_switch.select()

        ctk.CTkLabel(
            inner,
            text="开启后，打开浏览器时将使用 PWA 模式\n标题栏颜色会自动跟随 Luker 主题色变化",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted'],
            justify="left",
        ).pack(anchor="w")

    def _on_pwa_toggle(self) -> None:
        config.use_pwa_mode = self.pwa_switch.get() == 1

    def _build_gcl_section(self, parent: tk.Misc) -> None:
        """构建 GCL 设置区域"""
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            header,
            text="🚀  GCL 功能",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left")

        self.gcl_switch = ctk.CTkSwitch(
            header,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text'],
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text'],
            button_hover_color=self.COLORS['accent'],
            command=self._on_gcl_toggle,
        )
        self.gcl_switch.pack(side="right")

        if config.gcl_enabled:
            self.gcl_switch.select()

        ctk.CTkLabel(
            inner,
            text="开启后，可在托盘菜单中控制 GCL 的启动和停止",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted'],
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # GCL 路径选择区域（仅在开启时显示）
        self._gcl_path_frame = ctk.CTkFrame(inner, fg_color="transparent")

        ctk.CTkLabel(
            self._gcl_path_frame,
            text="GCL start.bat 路径:",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_dim'],
        ).pack(anchor="w", pady=(0, 6))

        path_row = ctk.CTkFrame(self._gcl_path_frame, fg_color="transparent")
        path_row.pack(fill="x")

        gcl_path_display = ctk.CTkFrame(path_row, fg_color=self.COLORS['bg'], corner_radius=8)
        gcl_path_display.pack(side="left", fill="x", expand=True, padx=(0, 8))

        current_gcl_path = config.gcl_bat_path or "未设置"
        self.gcl_path_label = ctk.CTkLabel(
            gcl_path_display,
            text=current_gcl_path,
            font=ctk.CTkFont(family=get_mono_font(), size=11),
            text_color=self.COLORS['text_muted'],
            anchor="w",
        )
        self.gcl_path_label.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(
            path_row,
            text="📂 选择",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            corner_radius=8,
            height=32,
            width=80,
            command=self._select_gcl_path,
        ).pack(side="right")

        if config.gcl_enabled:
            self._gcl_path_frame.pack(fill="x")

    def _on_gcl_toggle(self) -> None:
        enabled = self.gcl_switch.get() == 1

        if enabled:
            bat_path = config.gcl_bat_path
            if not bat_path or not config.is_valid_gcl_path(bat_path):
                selected = select_gcl_bat_path(self)
                if not selected:
                    # 用户取消选择，回退开关，避免出现“已启用但没有路径”的状态
                    self.gcl_switch.deselect()
                    self._gcl_path_frame.pack_forget()
                    return
                self.gcl_path_label.configure(text=selected)

        config.gcl_enabled = enabled

        if enabled:
            self._gcl_path_frame.pack(fill="x")
        else:
            self._gcl_path_frame.pack_forget()

    def _select_gcl_path(self) -> None:
        path = select_gcl_bat_path(self)
        if path:
            self.gcl_path_label.configure(text=path)

    def _build_path_section(self, parent: tk.Misc) -> None:
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(
            inner,
            text="📁  Luker 路径",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(anchor="w", pady=(0, 10))

        path_row = ctk.CTkFrame(inner, fg_color="transparent")
        path_row.pack(fill="x")

        path_display = ctk.CTkFrame(path_row, fg_color=self.COLORS['bg'], corner_radius=8)
        path_display.pack(side="left", fill="x", expand=True, padx=(0, 8))

        current_path = config.luker_path or "未设置"
        self.path_label = ctk.CTkLabel(
            path_display,
            text=current_path,
            font=ctk.CTkFont(family=get_mono_font(), size=11),
            text_color=self.COLORS['text_muted'],
            anchor="w",
        )
        self.path_label.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(
            path_row,
            text="📂 选择",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            corner_radius=8,
            height=32,
            width=80,
            command=self._select_path,
        ).pack(side="right")

    def _select_path(self) -> None:
        path = select_luker_path(self)
        if path:
            self.path_label.configure(text=path)

    def _build_footer(self, parent: tk.Misc) -> None:
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", pady=(8, 0))

        ctk.CTkButton(
            footer,
            text="完成",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            corner_radius=10,
            height=42,
            width=120,
            command=self.destroy,
        ).pack(side="right")
