"""设置窗口。"""

import contextlib
import tkinter as tk
from collections.abc import Callable

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
from theme import PRESET_THEMES, theme_swatch_colors
from ui_icons import theme_icon
from ui_style import make_button
from win_utils import (
    apply_window_rounding,
    bind_window_drag,
    get_mono_font,
    get_ui_font,
    sync_window_blur,
)

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

    CTk 通过 bind_all 注册这些序列，绑定挂在 "all" bindtag 上，没有按实例
    解绑的入口；应用同时只保留一个设置窗口，所以重建前清空序列，再由新的
    滚动区域重新注册。
    """
    for sequence in _SCROLL_BINDING_SEQUENCES:
        with contextlib.suppress(tk.TclError):
            widget.tk.call("bind", "all", sequence, "")


def bind_click_recursive(widget: tk.Misc, callback: Callable[[tk.Event], None]) -> None:
    """把点击绑定到控件及其所有后代，避免控件层级加深后漏绑。"""
    widget.bind('<Button-1>', callback)
    for child in widget.winfo_children():
        bind_click_recursive(child, callback)


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
        self._monitor_signature = monitor.signature()

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.95 if config.blur_enabled else 1.0)
        apply_window_rounding(self, context="设置窗口")
        self.configure(fg_color=self.COLORS['bg'])

        self._build_ui()

        self.after(100, self._setup_blur)

        config.add_theme_change_callback(self._on_theme_change)
        config.add_blur_change_callback(self._on_blur_change)

        self.bind('<Map>', self._on_map, add='+')
        self.bind('<Configure>', self._on_configure, add='+')
        self.bind('<Destroy>', self._on_destroy)

    def _on_map(self, event: tk.Event) -> None:
        # 窗口已显示时 DWM 不一定会重新取整，Map 后再补一次
        if event.widget == self and not self._destroyed:
            apply_window_rounding(self, context="设置窗口")

    def _on_configure(self, event: tk.Event) -> None:
        # 合并拖动过程中连续的 Configure 事件，空闲时只检查一次显示器
        if event.widget == self:
            self.after_idle(self._fit_to_current_monitor)

    def _fit_to_current_monitor(self) -> None:
        """移动到不同 DPI 的显示器后重新限制尺寸和位置。"""
        if self._destroyed or not self.winfo_exists():
            return

        monitor = get_monitor_info(hwnd=self.winfo_id())
        signature = monitor.signature()
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
            config.remove_blur_change_callback(self._on_blur_change)
            discard_window_scaling(self)
            clear_scroll_bindings(self)
            if self._on_close_callback is not None:
                self._on_close_callback()

    def is_alive(self) -> bool:
        """窗口是否仍存在，供主窗口复用单例前检查。"""
        if self._destroyed:
            return False
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _setup_blur(self) -> None:
        sync_window_blur(
            self,
            self.COLORS['bg'],
            enabled=config.blur_enabled,
            window_alpha=0.95,
            tint_alpha=0xEE,
            context="设置窗口",
        )

    def _on_blur_change(self, enabled: bool) -> None:
        if self._destroyed:
            return
        if enabled:
            self.blur_switch.select()
        else:
            self.blur_switch.deselect()
        self._setup_blur()

    def _on_theme_change(self, new_colors: dict[str, str]) -> None:
        if self._destroyed:
            return
        self.COLORS = new_colors
        # 延后重建，避免在主题卡片的点击回调里销毁当前控件
        self.after(0, self._rebuild_ui)

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=12)

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
        bar = ctk.CTkFrame(parent, height=48, fg_color=self.COLORS['card'], corner_radius=14)
        bar.pack(fill="x", pady=(0, 16))
        bar.pack_propagate(False)

        bind_window_drag(self, bar)

        ctk.CTkLabel(
            bar,
            text="⚙️  设置",
            font=ctk.CTkFont(family=self.UI_FONT, size=16, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left", padx=16, pady=12)

        make_button(
            bar,
            'danger_ghost',
            self.COLORS,
            text="✕",
            width=36,
            height=28,
            corner_radius=8,
            font_size=14,
            font_weight='bold',
            command=self.destroy,
        ).pack(side="right", padx=10)

    def _build_theme_section(self, parent: tk.Misc) -> None:
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 12))

        ctk.CTkLabel(
            header,
            text="🎨  主题颜色",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left")

        self.blur_switch = ctk.CTkSwitch(
            header,
            text="毛玻璃",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_dim'],
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text'],
            button_hover_color=self.COLORS['accent'],
            command=self._on_blur_toggle,
        )
        self.blur_switch.pack(side="right")

        if config.blur_enabled:
            self.blur_switch.select()

        grid = ctk.CTkFrame(section, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 16))

        current_theme = config.theme_name

        row = 0
        col = 0
        for theme_id, colors in PRESET_THEMES.items():
            card = self._create_theme_card(grid, theme_id, colors, current_theme == theme_id)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

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
            border_width=2,
            border_color=colors['accent'] if is_selected else colors['border'],
        )

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            header,
            image=theme_icon(colors['icon'], colors['accent']),
            text="",
            width=20,
            height=20,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text=colors['short_name'],
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=colors['text'],
            height=20,
        ).pack(side="left", padx=(6, 0))

        preview = ctk.CTkFrame(inner, fg_color="transparent")
        preview.pack(fill="x", pady=(0, 6))

        for index, color in enumerate(theme_swatch_colors(theme_id)):
            ctk.CTkFrame(
                preview,
                height=20,
                fg_color=color,
                corner_radius=4,
            ).grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0 if index == 0 else 4, 0),
            )
            preview.columnconfigure(index, weight=1)

        ctk.CTkLabel(
            inner,
            text="✓ 当前主题" if is_selected else "",
            font=ctk.CTkFont(family=self.UI_FONT, size=11),
            text_color=colors['accent'],
            height=18,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        def on_click(_event: tk.Event) -> None:
            self._select_theme(theme_id)

        bind_click_recursive(card, on_click)

        return card

    def _select_theme(self, theme_id: str) -> None:
        if theme_id in PRESET_THEMES:
            config.theme_name = theme_id

    def _on_blur_toggle(self) -> None:
        config.blur_enabled = self.blur_switch.get() == 1
        self.update()

    def _rebuild_ui(self) -> None:
        """按当前主题重建整个设置界面，让卡片、文字和选中状态一起刷新。"""
        if self._destroyed or not self.winfo_exists():
            return

        for child in self.winfo_children():
            child.destroy()

        clear_scroll_bindings(self)
        # 透明 frame 在创建时继承根窗口背景，必须先更新根背景再重建
        self.configure(fg_color=self.COLORS['bg'])
        self._build_ui()
        self._setup_blur()

    def _build_pwa_section(self, parent: tk.Misc) -> None:
        """构建 PWA 模式开关区域"""
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=14)
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
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=14)
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

        make_button(
            path_row,
            'secondary',
            self.COLORS,
            text="📂 选择",
            font_family=self.UI_FONT,
            font_size=12,
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
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=14)
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

        make_button(
            path_row,
            'secondary',
            self.COLORS,
            text="📂 选择",
            font_family=self.UI_FONT,
            font_size=12,
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

        make_button(
            footer,
            'primary',
            self.COLORS,
            text="完成",
            font_family=self.UI_FONT,
            height=40,
            width=120,
            command=self.destroy,
        ).pack(side="right")
