"""设置窗口。"""

import contextlib
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

import customtkinter as ctk

from config import config
from core.version import TargetInfo, UpdateProgress, UpdateTarget, VersionCheck
from dialogs import select_gcl_bat_path, select_luker_path
from ui.buttons import make_button
from ui.dpi import (
    centered_position,
    clamp_window_position,
    discard_window_scaling,
    fit_logical_window_size,
    format_geometry,
    get_monitor_info,
    sync_window_scaling,
)
from ui.icons import theme_icon
from ui.theme import PRESET_THEMES, shade_color, theme_swatch_colors
from ui.tooltip import Tooltip
from ui.window_utils import (
    apply_window_rounding,
    bind_window_drag,
    get_mono_font,
    get_ui_font,
    sync_window_blur,
)

SETTINGS_WIDTH = 600
SETTINGS_HEIGHT = 720
SETTINGS_MARGIN = 16

PWA_HINT_TEXT = "用 Edge 独立窗口打开 Luker，更像桌面应用。"
GCL_HINT_TEXT = "GCL 是可选配套服务，可在托盘菜单联动启停。"
CLOSE_BEHAVIOR_OPTIONS = (
    ('ask', '每次询问'),
    ('tray', '隐藏到托盘'),
    ('exit', '退出程序'),
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
    """设置窗口：主题、PWA、GCL、关闭行为和 Luker 管理。"""

    def __init__(
        self,
        parent: tk.Misc,
        anchor_point: tuple[int, int] | None = None,
        on_close: Callable[[], None] | None = None,
        on_check_luker_update: Callable[[], bool] | None = None,
        on_apply_luker_update: Callable[[UpdateTarget], bool] | None = None,
    ) -> None:
        super().__init__(parent)

        self._destroyed = False
        self._on_close_callback = on_close
        self._on_check_luker_update = on_check_luker_update
        self._on_apply_luker_update = on_apply_luker_update
        self._blur_job: str | None = None
        self._rebuild_job: str | None = None
        self._pending_fit = False
        self._version_check: VersionCheck | None = None
        self._update_progress: UpdateProgress | None = None
        self._version_checking = False
        self._update_busy = False

        self.COLORS = config.get_theme_colors()
        self.UI_FONT = get_ui_font()
        self.MONO_FONT = get_mono_font()
        self._close_behavior_var = tk.StringVar(master=self, value=config.close_behavior)
        self._update_channel_var = tk.StringVar(master=self, value="release")

        self.title("设置")
        self.resizable(False, False)

        # 托盘打开时跟随点击所在显示器；其他入口回退到父窗口显示器
        monitor = (
            get_monitor_info(point=anchor_point)
            if anchor_point is not None
            else get_monitor_info(hwnd=parent.winfo_id())
        )
        scale = sync_window_scaling(self, monitor.scale)
        logical_width, logical_height = fit_logical_window_size(
            SETTINGS_WIDTH,
            SETTINGS_HEIGHT,
            monitor,
            scale,
            margin=SETTINGS_MARGIN,
        )
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

        self._blur_job = self.after(100, self._setup_blur)

        config.add_theme_change_callback(self._on_theme_change)
        config.add_blur_change_callback(self._on_blur_change)
        config.add_close_behavior_change_callback(self._on_close_behavior_config_change)

        self.bind('<Map>', self._on_map, add='+')
        self.bind('<Configure>', self._on_configure, add='+')
        self.bind('<Destroy>', self._on_destroy)

    def _on_map(self, event: tk.Event) -> None:
        # 窗口已显示时 DWM 不一定会重新取整，Map 后再补一次
        if event.widget == self and not self._destroyed:
            apply_window_rounding(self, context="设置窗口")

    def _on_configure(self, event: tk.Event) -> None:
        # 合并拖动过程中连续的 Configure 事件，空闲时只检查一次显示器
        if event.widget == self and not self._pending_fit:
            self._pending_fit = True
            self.after_idle(self._run_scheduled_fit)

    def _run_scheduled_fit(self) -> None:
        self._pending_fit = False
        self._fit_to_current_monitor()

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
        logical_width, logical_height = fit_logical_window_size(
            SETTINGS_WIDTH,
            SETTINGS_HEIGHT,
            monitor,
            scale,
            margin=SETTINGS_MARGIN,
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
        self.geometry(format_geometry(logical_width, logical_height, x, y))

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget == self:
            self._destroyed = True
            for job in (self._blur_job, self._rebuild_job):
                if job is not None:
                    with contextlib.suppress(tk.TclError):
                        self.after_cancel(job)
            self._blur_job = None
            self._rebuild_job = None
            tooltip = getattr(self, '_tooltip', None)
            if tooltip is not None:
                tooltip.destroy()
            config.remove_theme_change_callback(self._on_theme_change)
            config.remove_blur_change_callback(self._on_blur_change)
            config.remove_close_behavior_change_callback(self._on_close_behavior_config_change)
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
        self._blur_job = None
        if self._destroyed:
            return
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
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
        # 延后重建，避免在主题卡片的点击回调里销毁当前控件；
        # 连续切换时只保留最后一次，避免排队多次整窗重建。
        if self._rebuild_job is not None:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._rebuild_job)
        self._rebuild_job = self.after(0, self._rebuild_ui)

    def _build_ui(self) -> None:
        self._tooltip = Tooltip(self, self.COLORS, self.UI_FONT, wraplength=380)

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

        self._build_close_behavior_section(scroll_frame)

        self._build_luker_section(scroll_frame)

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
            font_family=self.UI_FONT,
            font_size=14,
            font_weight='bold',
            command=self.destroy,
        ).pack(side="right", padx=10)

    def _make_switch(
        self,
        parent: tk.Misc,
        *,
        text: str,
        command: Callable[[], None],
        selected: bool,
        font_size: int = 13,
    ) -> ctk.CTkSwitch:
        """创建统一配色的开关；文本为空时只作为右侧控件。"""
        switch = ctk.CTkSwitch(
            parent,
            text=text,
            font=ctk.CTkFont(family=self.UI_FONT, size=font_size),
            text_color=self.COLORS['text_dim'] if text else self.COLORS['text'],
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text'],
            button_hover_color=self.COLORS['accent'],
            command=command,
        )
        if selected:
            switch.select()
        return switch

    def _create_switch_row(
        self,
        parent: tk.Misc,
        title: str,
        command: Callable[[], None],
        selected: bool,
        *,
        hint: str | None = None,
    ) -> ctk.CTkSwitch:
        """创建“标题 + 右侧开关”的 section 头部；hint 为标题后的悬停说明。"""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(side="left")
        if hint is not None:
            self._create_hint(header, hint)
        switch = self._make_switch(header, text="", command=command, selected=selected)
        switch.pack(side="right")
        return switch

    def _create_hint(self, parent: tk.Misc, text: str) -> None:
        """在标题后创建圆形问号，悬停时高亮并显示说明。"""
        hint = ctk.CTkLabel(
            parent,
            text="?",
            width=18,
            height=18,
            corner_radius=9,
            fg_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_muted'],
            font=ctk.CTkFont(family=self.UI_FONT, size=11, weight="bold"),
        )
        hint.pack(side="left", padx=(6, 0))
        self._tooltip.attach(hint, text)
        hint.bind('<Enter>', lambda _event: self._on_hint_enter(hint), add='+')
        hint.bind('<Leave>', lambda _event: self._on_hint_leave(hint), add='+')

    def _on_hint_enter(self, hint: ctk.CTkLabel) -> None:
        hint.configure(fg_color=self.COLORS['accent'], text_color=self.COLORS['on_accent'])

    def _on_hint_leave(self, hint: ctk.CTkLabel) -> None:
        hint.configure(
            fg_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_muted'],
        )

    def _create_section(self, parent: tk.Misc) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        """创建 section 外壳和内容区，统一边距。"""
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=14)
        section.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)
        return section, inner

    def _create_path_row(
        self,
        parent: tk.Misc,
        current_value: str,
        command: Callable[[], None],
    ) -> tuple[ctk.CTkLabel, ctk.CTkButton]:
        """创建“路径显示 + 选择按钮”行，返回路径标签和按钮。"""
        path_row = ctk.CTkFrame(parent, fg_color="transparent")
        path_row.pack(fill="x")

        path_display = ctk.CTkFrame(path_row, fg_color=self.COLORS['bg'], corner_radius=8)
        path_display.pack(side="left", fill="x", expand=True, padx=(0, 8))

        value_label = ctk.CTkLabel(
            path_display,
            text=current_value,
            font=ctk.CTkFont(family=self.MONO_FONT, size=11),
            text_color=self.COLORS['text_muted'],
            anchor="w",
        )
        value_label.pack(fill="x", padx=10, pady=8)

        button = make_button(
            path_row,
            'secondary',
            self.COLORS,
            text="📂 选择",
            font_family=self.UI_FONT,
            font_size=12,
            height=32,
            width=80,
            command=command,
        )
        button.pack(side="right")
        return value_label, button

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

        self.blur_switch = self._make_switch(
            header,
            text="毛玻璃",
            command=self._on_blur_toggle,
            selected=config.blur_enabled,
            font_size=12,
        )
        self.blur_switch.pack(side="right")

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

        self._build_theme_card_header(inner, colors)
        self._build_theme_swatches(inner, theme_id)
        self._build_theme_card_status(inner, colors, is_selected)

        def on_click(_event: tk.Event) -> None:
            self._select_theme(theme_id)

        bind_click_recursive(card, on_click)

        return card

    def _build_theme_card_header(self, parent: tk.Misc, colors: dict[str, str]) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
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

    def _build_theme_swatches(self, parent: tk.Misc, theme_id: str) -> None:
        preview = ctk.CTkFrame(parent, fg_color="transparent")
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

    def _build_theme_card_status(
        self,
        parent: tk.Misc,
        colors: dict[str, str],
        is_selected: bool,
    ) -> None:
        ctk.CTkLabel(
            parent,
            text="✓ 当前主题" if is_selected else "",
            font=ctk.CTkFont(family=self.UI_FONT, size=11),
            text_color=colors['accent'],
            height=18,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

    def _select_theme(self, theme_id: str) -> None:
        if theme_id in PRESET_THEMES and theme_id != config.theme_name:
            config.theme_name = theme_id

    def _on_blur_toggle(self) -> None:
        config.blur_enabled = self.blur_switch.get() == 1
        self.update()

    def _rebuild_ui(self) -> None:
        """按当前主题重建整个设置界面，让卡片、文字和选中状态一起刷新。"""
        self._rebuild_job = None
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
        _section, inner = self._create_section(parent)
        self.pwa_switch = self._create_switch_row(
            inner,
            "🌐  PWA 浏览器模式",
            self._on_pwa_toggle,
            config.use_pwa_mode,
            hint=PWA_HINT_TEXT,
        )

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
        _section, inner = self._create_section(parent)
        self.gcl_switch = self._create_switch_row(
            inner,
            "🚀  GCL 功能",
            self._on_gcl_toggle,
            config.gcl_enabled,
            hint=GCL_HINT_TEXT,
        )

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

        self.gcl_path_label, _ = self._create_path_row(
            self._gcl_path_frame,
            config.gcl_bat_path or "未设置",
            self._select_gcl_path,
        )

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

    def _build_close_behavior_section(self, parent: tk.Misc) -> None:
        """构建关闭窗口行为选择区域。"""
        _section, inner = self._create_section(parent)

        ctk.CTkLabel(
            inner,
            text="🚪  当关闭日志窗口时",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(anchor="w", pady=(0, 10))

        self._close_behavior_var.set(config.close_behavior)
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")

        for value, label in CLOSE_BEHAVIOR_OPTIONS:
            ctk.CTkRadioButton(
                row,
                text=label,
                value=value,
                variable=self._close_behavior_var,
                command=lambda value=value: self._on_close_behavior_change(value),
                width=128,
                font=ctk.CTkFont(family=self.UI_FONT, size=12),
                text_color=self.COLORS['text'],
                fg_color=self.COLORS['accent'],
                hover_color=shade_color(self.COLORS['accent'], 0.85),
                border_color=self.COLORS['border'],
                radiobutton_width=18,
                radiobutton_height=18,
                corner_radius=9,
                border_width_unchecked=2,
                border_width_checked=6,
            ).pack(side="left", padx=(0, 18))

    def _on_close_behavior_change(self, value: str) -> None:
        config.close_behavior = value

    def _on_close_behavior_config_change(self, value: str) -> None:
        if self._destroyed:
            return
        variable = getattr(self, '_close_behavior_var', None)
        if variable is not None:
            variable.set(value)

    def _build_luker_section(self, parent: tk.Misc) -> None:
        _section, inner = self._create_section(parent)

        ctk.CTkLabel(
            inner,
            text="📁  Luker 管理",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text'],
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            inner,
            text="安装路径",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            text_color=self.COLORS['text_dim'],
        ).pack(anchor="w", pady=(0, 6))

        self.path_label, self.path_button = self._create_path_row(
            inner,
            config.luker_path or "未设置",
            self._select_path,
        )

        ctk.CTkFrame(inner, height=1, fg_color=self.COLORS['border']).pack(
            fill="x",
            pady=12,
        )

        ctk.CTkLabel(
            inner,
            text="版本管理",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            text_color=self.COLORS['text_dim'],
        ).pack(anchor="w", pady=(0, 6))

        self._current_label = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_dim'],
            justify="left",
            anchor="w",
            wraplength=480,
        )
        self._current_label.pack(fill="x", pady=(0, 8))

        self._release_summary = self._create_version_choice(
            inner,
            "release",
            "最新发行版",
        )
        self._commit_summary = self._create_version_choice(
            inner,
            "commit",
            "最新提交",
        )

        actions = ctk.CTkFrame(inner, fg_color="transparent")
        actions.pack(fill="x", pady=(10, 0))

        self._check_button = make_button(
            actions,
            'secondary',
            self.COLORS,
            text="检查更新",
            width=100,
            height=32,
            font_family=self.UI_FONT,
            font_size=12,
            command=self._on_check_update,
        )
        self._check_button.pack(side="left")

        self._update_button = make_button(
            actions,
            'primary',
            self.COLORS,
            text="更新",
            width=190,
            height=32,
            font_family=self.UI_FONT,
            font_size=12,
            command=self._on_apply_update,
            state="disabled",
        )
        self._update_button.pack(side="right")

        self._version_status = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted'],
            justify="left",
            anchor="w",
            wraplength=480,
        )
        self._version_status.pack(fill="x", pady=(8, 0))

        self._render_luker_state()

    def _create_version_choice(
        self,
        parent: tk.Misc,
        value: str,
        label: str,
    ) -> ctk.CTkLabel:
        """创建“单选项 + 一行版本摘要”，返回摘要标签。"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))

        radio = ctk.CTkRadioButton(
            row,
            text=label,
            value=value,
            variable=self._update_channel_var,
            command=self._on_update_channel_change,
            width=110,
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text'],
            fg_color=self.COLORS['accent'],
            hover_color=shade_color(self.COLORS['accent'], 0.85),
            border_color=self.COLORS['border'],
            radiobutton_width=18,
            radiobutton_height=18,
            corner_radius=9,
            border_width_unchecked=2,
            border_width_checked=6,
        )
        radio.pack(side="left")
        if value == "release":
            self._release_radio = radio
        else:
            self._commit_radio = radio

        summary = ctk.CTkLabel(
            row,
            text="尚未检查",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted'],
            justify="left",
            anchor="w",
            wraplength=400,
        )
        summary.pack(side="left", padx=(8, 0), fill="x", expand=True)
        return summary

    def _render_luker_state(self) -> None:
        if self._destroyed:
            return

        busy = self._version_checking or self._update_busy
        state = "disabled" if busy else "normal"
        self.path_button.configure(state=state)
        self._release_radio.configure(state=state)
        self._commit_radio.configure(state=state)
        self._check_button.configure(
            state="disabled" if busy or self._on_check_luker_update is None else "normal",
            text="检查中..." if self._version_checking else "检查更新",
        )

        self._current_label.configure(text=self._current_text())
        check = self._version_check
        release = check.release if check is not None else None
        commit = check.commit if check is not None else None
        self._release_summary.configure(text=self._summary_text(release))
        self._commit_summary.configure(text=self._summary_text(commit))

        target = self._selected_target()
        can_update = bool(
            target is not None
            and target.actionable
            and not busy
            and self._on_apply_luker_update is not None
        )
        self._update_button.configure(
            state="normal" if can_update else "disabled",
            text=self._update_button_text(target),
        )
        self._version_status.configure(
            text=self._status_text(target),
            text_color=self._status_color(target),
        )

    def _selected_target(self) -> TargetInfo | None:
        check = self._version_check
        if check is None:
            return None
        if self._update_channel_var.get() == "commit":
            return check.commit
        return check.release

    def _current_text(self) -> str:
        check = self._version_check
        if check is None:
            return "当前版本：尚未检查"
        local = check.local
        if local.error:
            return f"当前版本：无法读取（{local.error}）"

        branch = local.branch if local.branch and local.branch != "HEAD" else "分离 HEAD"
        meta = " · ".join(part for part in (branch, local.date) if part)
        version = local.describe or local.short_head or "未知"
        lines = [f"当前版本：{version} · {meta}" if meta else f"当前版本：{version}"]
        if local.dirty:
            lines.append("存在未提交的跟踪文件修改，更新已禁用。")
        if not local.path_matches:
            lines.append("Luker 路径已更改，请先重启应用新路径。")
        return "\n".join(lines)

    @staticmethod
    def _summary_text(target: TargetInfo | None) -> str:
        if target is None:
            return "尚未检查"
        commit = target.commit
        if target.kind == "release":
            tag = target.tag or target.label
            published = target.published_at or "未知"
            return f"{tag} · 发布于 {published} · 提交 {commit.short_sha}"
        return f"提交于 {commit.date or '未知'} · {commit.short_sha}"

    def _update_button_text(self, target: TargetInfo | None) -> str:
        if target is None:
            return "更新"
        if not target.actionable:
            if target.relation == "up_to_date":
                return "已是最新"
            return "当前不可更新"
        if target.downgrade:
            return f"回退到 {target.label}"
        if target.kind == "commit":
            return "更新到最新提交"
        return f"更新到 {target.label}"

    def _status_text(self, target: TargetInfo | None) -> str:
        if self._version_checking:
            return "正在检查更新..."
        if self._update_progress is not None:
            return self._update_progress.message
        check = self._version_check
        if check is None:
            return "点击“检查更新”获取最新发行版和最新提交。"
        if check.error and target is None:
            return check.error
        if check.local.error:
            return check.local.error
        if target is None:
            return check.error or "没有可用的版本信息。"
        if self._on_check_luker_update is None:
            return "版本管理未连接启动器。"
        return target.status

    def _status_color(self, target: TargetInfo | None) -> str:
        if self._update_progress is not None:
            return {
                "info": self.COLORS['text_muted'],
                "success": self.COLORS['success'],
                "warning": self.COLORS['warning'],
                "error": self.COLORS['error'],
            }.get(self._update_progress.level, self.COLORS['text_muted'])
        if self._version_checking:
            return self.COLORS['text_muted']
        check = self._version_check
        if check is None:
            return self.COLORS['text_muted']
        if check.error and target is None:
            return self.COLORS['error']
        if check.local.error:
            return self.COLORS['error']
        if target is None:
            return self.COLORS['text_muted']
        if target.downgrade:
            return self.COLORS['warning']
        if target.actionable:
            return self.COLORS['text_muted']
        if target.relation == "up_to_date":
            return self.COLORS['success']
        if target.relation in ("ahead", "unknown"):
            return self.COLORS['warning']
        if target.relation == "diverged":
            return self.COLORS['error']
        if check.error:
            return self.COLORS['warning']
        return self.COLORS['error']

    def _on_update_channel_change(self) -> None:
        self._render_luker_state()

    def _on_check_update(self) -> None:
        if self._version_checking or self._update_busy:
            return
        if self._on_check_luker_update is None:
            self._update_progress = UpdateProgress(
                "error",
                "版本管理未连接启动器。",
                "warning",
                False,
            )
            self._render_luker_state()
            return

        self._version_checking = True
        self._update_progress = None
        self._render_luker_state()
        if not self._on_check_luker_update():
            self._version_checking = False
            self._update_progress = UpdateProgress(
                "error",
                "暂时无法检查版本，请稍后再试。",
                "warning",
                False,
            )
            self._render_luker_state()

    def set_version_check(self, check: VersionCheck) -> None:
        """接收后台检查结果；主题重建后仍按该结果渲染。"""
        if self._destroyed:
            return
        self._version_checking = False
        self._version_check = check
        self._update_progress = None
        self._render_luker_state()

    def set_update_progress(self, progress: UpdateProgress) -> None:
        """接收更新阶段和最终结果。"""
        if self._destroyed:
            return
        self._update_progress = progress
        self._update_busy = progress.busy
        if not progress.busy and progress.stage in ("done", "error"):
            # 更新后当前版本可能已变化，强制重新检查，避免继续显示旧目标
            self._version_check = None
        self._render_luker_state()

    def _on_apply_update(self) -> None:
        if self._update_busy or self._version_checking:
            return
        target = self._selected_target()
        if target is None or not target.actionable:
            return
        if self._on_apply_luker_update is None:
            return

        if target.downgrade:
            text = (
                f"当前已包含 {target.label}，领先 {target.ahead} 个提交。\n"
                f"更新会回退代码到 {target.label}，并重新安装依赖。\n"
                "更新完成后，如果 Luker 原本在运行会自动重启。\n是否继续？"
            )
        else:
            text = (
                f"将停止 Luker，更新到 {target.label} 并安装依赖。\n"
                "更新完成后，如果 Luker 原本在运行会自动重启。\n是否继续？"
            )
        if not messagebox.askyesno("更新 Luker", text, parent=self):
            return

        update_target = UpdateTarget(
            kind=target.kind,
            label=target.label,
            sha=target.commit.sha,
            tag=target.tag,
            branch=target.branch,
        )
        self._update_busy = True
        self._update_progress = UpdateProgress(
            "preparing",
            "正在准备更新...",
            "info",
            True,
        )
        self._render_luker_state()
        if not self._on_apply_luker_update(update_target):
            self._update_busy = False
            self._update_progress = UpdateProgress(
                "error",
                "更新未启动，请稍后再试。",
                "warning",
                False,
            )
            self._render_luker_state()

    def _select_path(self) -> None:
        path = select_luker_path(self)
        if path:
            self.path_label.configure(text=path)
            self._version_check = None
            self._update_progress = None
            self._version_checking = False
            self._update_busy = False
            self._render_luker_state()

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
