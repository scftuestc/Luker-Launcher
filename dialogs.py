"""托盘右键菜单和设置窗口。"""

import customtkinter as ctk
from ctypes import windll
from typing import Dict
import math
import webbrowser

from config import config, PRESET_THEMES
from log_window import WindowsBlur, get_ui_font, get_mono_font


class TrayMenu(ctk.CTkToplevel):
    """置顶、不抢焦点的托盘右键菜单。"""

    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    GWL_EXSTYLE = -20

    def __init__(self, parent, callbacks):
        super().__init__(parent)

        self.callbacks = callbacks
        self._is_running = False
        self._window_visible = False
        self._gcl_enabled = False

        self.COLORS = config.get_theme_colors()

        self.UI_FONT = get_ui_font()

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.97)

        self.configure(fg_color=self.COLORS['bg'])

        self._animation_phase = 0
        self._hover_item = None

        self._build_menu()

        config.add_theme_change_callback(self._on_theme_change)

        self.after(50, self._setup_blur)
        self.after(100, self._setup_no_activate)

        self._animate_menu()

        self._check_mouse_outside()

        self.withdraw()

    def _on_theme_change(self, new_colors: Dict[str, str]) -> None:
        """主题变化时重建菜单，保证托盘菜单与新主题一致。"""
        if not self.winfo_exists():
            return

        self.COLORS = new_colors
        self.configure(fg_color=self.COLORS['bg'])

        for child in self.winfo_children():
            child.destroy()

        gcl_running = self._gcl_running
        self._build_menu()
        self.update_state(self._is_running, self._window_visible,
                          self._gcl_enabled, gcl_running)
        self._setup_blur()

    def _setup_no_activate(self):
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            ex_style = windll.user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            new_style = ex_style | self.WS_EX_NOACTIVATE | self.WS_EX_TOOLWINDOW
            windll.user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, new_style)
        except Exception as e:
            print(f"设置无焦点窗口失败: {e}")

    def _check_mouse_outside(self):
        """菜单可见时轮询鼠标，左键点击菜单外部则收起。"""
        if not self.winfo_viewable():
            self.after(200, self._check_mouse_outside)
            return

        try:
            mouse_x = self.winfo_pointerx()
            mouse_y = self.winfo_pointery()

            menu_x = self.winfo_x()
            menu_y = self.winfo_y()
            menu_w = self.winfo_width()
            menu_h = self.winfo_height()

            in_menu = (menu_x <= mouse_x <= menu_x + menu_w and
                      menu_y <= mouse_y <= menu_y + menu_h)

            if not in_menu:
                left_button = windll.user32.GetAsyncKeyState(0x01) & 0x8000
                if left_button:
                    self.hide()
                    self.after(200, self._check_mouse_outside)
                    return

        except Exception:
            pass

        self.after(100, self._check_mouse_outside)

    def _setup_blur(self):
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            WindowsBlur.extend_frame(hwnd)
            WindowsBlur.enable_blur(hwnd, 0xEE17110d)
        except Exception:
            pass

    def _animate_menu(self):
        self._animation_phase = (self._animation_phase + 0.05) % 1.0

        if hasattr(self, '_menu_logo_bars'):
            for i, bar in enumerate(self._menu_logo_bars):
                phase = (self._animation_phase + i * 0.25) % 1.0
                brightness = 0.7 + 0.3 * math.sin(phase * 2 * 3.14159)

                colors = [(0xff, 0x6b, 0x6b), (0xfe, 0xca, 0x57), (0x48, 0xdb, 0xfb), (0x1d, 0xd1, 0xa1)]
                r, g, b = colors[i]
                r = int(r * brightness)
                g = int(g * brightness)
                b = int(b * brightness)
                bar.configure(fg_color=f"#{r:02x}{g:02x}{b:02x}")

        if self.winfo_viewable():
            self.after(50, self._animate_menu)

    def _build_menu(self):
        main = ctk.CTkFrame(self, fg_color=self.COLORS['card'], corner_radius=16)
        main.pack(fill="both", expand=True, padx=2, pady=2)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 12))

        logo = ctk.CTkFrame(header, fg_color="transparent")
        logo.pack(side="left")

        self._menu_logo_bars = []
        colors = ['#ff6b6b', '#feca57', '#48dbfb', '#1dd1a1']
        for c in colors:
            bar = ctk.CTkFrame(logo, width=3, height=18, fg_color=c, corner_radius=2)
            bar.pack(side="left", padx=1)
            self._menu_logo_bars.append(bar)

        ctk.CTkLabel(
            header, text="Luker",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text']
        ).pack(side="left", padx=(10, 0))

        ctk.CTkFrame(main, height=1, fg_color=self.COLORS['border']).pack(fill="x", padx=12)

        items_frame = ctk.CTkFrame(main, fg_color="transparent")
        items_frame.pack(fill="x", padx=8, pady=8)
        self._items_frame = items_frame

        self.menu_items = {}

        # 显示日志窗口
        self.menu_items['window'] = self._create_menu_item(
            items_frame, "📋", "显示日志窗口", self._on_toggle_window
        )

        ctk.CTkFrame(items_frame, height=1, fg_color=self.COLORS['border']).pack(fill="x", padx=8, pady=6)

        # Luker 控制区域：启动/停止（合并为一个按钮）、重启、Luker 页面
        self.menu_items['luker_toggle'] = self._create_menu_item(
            items_frame, "▶", "启动 Luker", self._on_luker_toggle, color=self.COLORS['success']
        )

        self.menu_items['restart'] = self._create_menu_item(
            items_frame, "🔄", "重启 Luker", self._on_restart, color=self.COLORS['accent']
        )

        self.menu_items['luker_browser'] = self._create_menu_item(
            items_frame, "🌐", "Luker 页面", self._on_open_browser, color=self.COLORS['info']
        )

        # GCL 分隔线和菜单项（根据配置动态显示，初始隐藏）
        self._gcl_separator = ctk.CTkFrame(items_frame, height=1, fg_color=self.COLORS['border'])
        # 初始不 pack，由 update_state 控制

        self.menu_items['gcl_toggle'] = self._create_menu_item_hidden(
            items_frame, "▶", "启动 GCL", self._on_gcl_toggle, color=self.COLORS['success']
        )

        self.menu_items['gcl_browser'] = self._create_menu_item_hidden(
            items_frame, "🌐", "GCL 页面", self._on_gcl_browser, color=self.COLORS['info']
        )

        # 底部分隔线
        self._bottom_separator = ctk.CTkFrame(items_frame, height=1, fg_color=self.COLORS['border'])
        self._bottom_separator.pack(fill="x", padx=8, pady=6)

        self.menu_items['settings'] = self._create_menu_item(
            items_frame, "⚙️", "设置", self._on_settings
        )

        self.menu_items['exit'] = self._create_menu_item(
            items_frame, "🚪", "退出", self._on_exit, color=self.COLORS['error']
        )

        # 初始化 GCL 状态
        self._gcl_running = False

    def _create_menu_item(self, parent, icon, text, command, color=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8)
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
            command=command
        )
        btn.pack(fill="x", padx=4)

        return {'frame': frame, 'btn': btn, 'color': color}

    def _create_menu_item_hidden(self, parent, icon, text, command, color=None):
        """创建菜单项但不立即显示（不 pack）"""
        frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8)
        # 不调用 pack，由 update_state 控制显示

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
            command=command
        )
        btn.pack(fill="x", padx=4)

        return {'frame': frame, 'btn': btn, 'color': color}

    def _on_toggle_window(self):
        self.hide()
        if self._window_visible:
            self.callbacks['hide_window']()
        else:
            self.callbacks['show_window']()

    def _on_luker_toggle(self):
        """Luker 启动/停止切换"""
        self.hide()
        if self._is_running:
            self.callbacks['stop']()
        else:
            self.callbacks['start']()

    def _on_restart(self):
        self.hide()
        self.callbacks['restart']()

    def _on_settings(self):
        self.hide()
        self.callbacks['settings']()

    def _on_open_browser(self):
        self.hide()
        if 'open_browser' in self.callbacks:
            self.callbacks['open_browser']()
        else:
            webbrowser.open(config.get_server_url())

    def _on_gcl_toggle(self):
        self.hide()
        if self._gcl_running:
            if 'gcl_stop' in self.callbacks:
                self.callbacks['gcl_stop']()
        else:
            if 'gcl_start' in self.callbacks:
                self.callbacks['gcl_start']()

    def _on_gcl_browser(self):
        self.hide()
        webbrowser.open(config.gcl_url)

    def _on_exit(self):
        self.hide()
        self.callbacks['exit']()

    def update_state(self, is_running: bool, window_visible: bool, gcl_enabled: bool = False, gcl_running: bool = False):
        self._is_running = is_running
        self._window_visible = window_visible
        self._gcl_enabled = gcl_enabled

        # 更新日志窗口按钮
        window_text = "隐藏日志窗口" if window_visible else "显示日志窗口"
        self.menu_items['window']['btn'].configure(text=f"📋  {window_text}")

        # 更新 Luker 启动/停止按钮（合并为一个动态按钮）
        if is_running:
            self.menu_items['luker_toggle']['btn'].configure(
                text="⏹  停止 Luker",
                text_color=self.COLORS['error']
            )
            self.menu_items['restart']['btn'].configure(state="normal", text_color=self.COLORS['accent'])
        else:
            self.menu_items['luker_toggle']['btn'].configure(
                text="▶  启动 Luker",
                text_color=self.COLORS['success']
            )
            self.menu_items['restart']['btn'].configure(state="disabled", text_color=self.COLORS['text_muted'])

        # 更新 GCL 菜单项状态
        self._gcl_running = gcl_running
        if gcl_enabled:
            # 先隐藏再显示，确保顺序正确（在底部分隔线之前）
            self._gcl_separator.pack_forget()
            self.menu_items['gcl_toggle']['frame'].pack_forget()
            self.menu_items['gcl_browser']['frame'].pack_forget()

            # 在底部分隔线之前插入
            self._gcl_separator.pack(fill="x", padx=8, pady=6, before=self._bottom_separator)
            self.menu_items['gcl_toggle']['frame'].pack(fill="x", pady=2, before=self._bottom_separator)
            self.menu_items['gcl_browser']['frame'].pack(fill="x", pady=2, before=self._bottom_separator)

            if gcl_running:
                self.menu_items['gcl_toggle']['btn'].configure(
                    text="⏹  停止 GCL",
                    text_color=self.COLORS['error']
                )
            else:
                self.menu_items['gcl_toggle']['btn'].configure(
                    text="▶  启动 GCL",
                    text_color=self.COLORS['success']
                )
        else:
            self._gcl_separator.pack_forget()
            self.menu_items['gcl_toggle']['frame'].pack_forget()
            self.menu_items['gcl_browser']['frame'].pack_forget()

    def show_at(self, x: int, y: int):
        self.update_idletasks()
        w = 220
        h = self.winfo_reqheight()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        if x + w > screen_w:
            x = screen_w - w - 10
        if y + h > screen_h - 50:
            y = y - h - 10

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()

        self._setup_no_activate()

        self._animate_menu()

    def hide(self):
        self.withdraw()


class SettingsWindow(ctk.CTkToplevel):
    """设置窗口：主题、PWA 模式、GCL 和 Luker 路径。"""

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self._destroyed = False

        self.COLORS = config.get_theme_colors()
        self.UI_FONT = get_ui_font()

        self.title("设置")
        self.resizable(False, False)

        # 先设置窗口位置到屏幕中央，再设置其他属性
        # 计算居中位置
        w = 600
        h = 720
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.98)
        self.configure(fg_color=self.COLORS['bg'])

        self._drag_x = 0
        self._drag_y = 0

        self._build_ui()

        self.after(100, self._setup_blur)

        config.add_theme_change_callback(self._on_theme_change)

        self.bind('<Destroy>', self._on_destroy)

    def _on_destroy(self, event):
        if event.widget == self:
            self._destroyed = True
            config.remove_theme_change_callback(self._on_theme_change)

    def _setup_blur(self):
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            WindowsBlur.extend_frame(hwnd)
            bg = self.COLORS['bg']
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            blur_color = 0xEE000000 | (b << 16) | (g << 8) | r
            WindowsBlur.enable_blur(hwnd, blur_color)
        except Exception as e:
            print(f"设置窗口毛玻璃错误: {e}")

    def _on_theme_change(self, new_colors: Dict[str, str]) -> None:
        if self._destroyed:
            return
        self.COLORS = new_colors
        # 延后重建，避免在主题卡片的点击回调里销毁当前控件
        self.after(0, self._rebuild_ui)

    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=16)

        self._build_titlebar(main)

        # 创建可滚动区域
        scroll_frame = ctk.CTkScrollableFrame(
            main,
            fg_color="transparent",
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent']
        )
        scroll_frame.pack(fill="both", expand=True, pady=(0, 8))

        self._build_theme_section(scroll_frame)

        self._build_pwa_section(scroll_frame)

        self._build_gcl_section(scroll_frame)

        self._build_path_section(scroll_frame)

        self._build_footer(main)

    def _build_titlebar(self, parent):
        bar = ctk.CTkFrame(parent, height=48, fg_color=self.COLORS['card'], corner_radius=12)
        bar.pack(fill="x", pady=(0, 16))
        bar.pack_propagate(False)

        bar.bind('<Button-1>', self._start_drag)
        bar.bind('<B1-Motion>', self._on_drag)

        ctk.CTkLabel(
            bar, text="⚙️  设置",
            font=ctk.CTkFont(family=self.UI_FONT, size=16, weight="bold"),
            text_color=self.COLORS['text']
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkButton(
            bar, text="✕", width=36, height=28,
            fg_color="transparent",
            hover_color=self.COLORS['error'],
            text_color=self.COLORS['text_dim'],
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            command=self.destroy
        ).pack(side="right", padx=10)

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _on_drag(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _build_theme_section(self, parent):
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 12))

        ctk.CTkLabel(
            header, text="🎨  主题颜色",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text']
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="点击卡片实时预览",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted']
        ).pack(side="right")

        grid = ctk.CTkFrame(section, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 16))

        self.theme_cards = {}
        current_theme = config.theme_name

        theme_info = {
            'deep_blue': {'name': '深蓝', 'icon': '🌊'},
            'purple_night': {'name': '紫夜', 'icon': '🔮'},
            'forest_green': {'name': '森林', 'icon': '🌲'},
            'warm_orange': {'name': '暖橙', 'icon': '🌅'},
            'ocean_cyan': {'name': '海洋', 'icon': '🌴'},
            'rose_pink': {'name': '玫瑰', 'icon': '🌸'},
        }

        row = 0
        col = 0
        for theme_id, colors in PRESET_THEMES.items():
            info = theme_info.get(theme_id, {'name': theme_id, 'icon': '🎨'})
            card = self._create_theme_card(grid, theme_id, colors, info, current_theme == theme_id)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self.theme_cards[theme_id] = card

            col += 1
            if col >= 3:
                col = 0
                row += 1

        for i in range(3):
            grid.columnconfigure(i, weight=1)

    def _create_theme_card(self, parent, theme_id, colors, info, is_selected):
        card = ctk.CTkFrame(
            parent,
            fg_color=colors['card'],
            corner_radius=10,
            border_width=3 if is_selected else 1,
            border_color=colors['accent'] if is_selected else colors['border']
        )

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        preview = ctk.CTkFrame(inner, fg_color="transparent", height=24)
        preview.pack(fill="x", pady=(0, 8))

        preview_colors = [colors['accent'], colors['success'], colors['info'], colors['warning']]
        for pc in preview_colors:
            ctk.CTkFrame(preview, width=28, height=20, fg_color=pc, corner_radius=4).pack(side="left", padx=2)

        name_label = ctk.CTkLabel(
            inner,
            text=f"{info['icon']} {info['name']}",
            font=ctk.CTkFont(family=self.UI_FONT, size=13, weight="bold"),
            text_color=colors['text']
        )
        name_label.pack(anchor="w")

        if is_selected:
            ctk.CTkLabel(
                inner,
                text="✓ 当前主题",
                font=ctk.CTkFont(family=self.UI_FONT, size=11),
                text_color=colors['accent']
            ).pack(anchor="w", pady=(4, 0))

        def on_click(e, tid=theme_id):
            self._select_theme(tid)

        card.bind('<Button-1>', on_click)
        inner.bind('<Button-1>', on_click)
        for child in inner.winfo_children():
            child.bind('<Button-1>', on_click)
            if hasattr(child, 'winfo_children'):
                for subchild in child.winfo_children():
                    subchild.bind('<Button-1>', on_click)

        return card

    def _select_theme(self, theme_id):
        if theme_id in PRESET_THEMES:
            config.theme_name = theme_id

    def _rebuild_ui(self):
        """按当前主题重建整个设置界面，让卡片、文字和选中状态一起刷新。"""
        if self._destroyed or not self.winfo_exists():
            return

        for child in self.winfo_children():
            child.destroy()

        self._build_ui()
        self.configure(fg_color=self.COLORS['bg'])
        self._setup_blur()

    def _build_pwa_section(self, parent):
        """构建 PWA 模式开关区域"""
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        # 标题行
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            header, text="🌐  PWA 浏览器模式",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text']
        ).pack(side="left")

        # 开关
        self.pwa_switch = ctk.CTkSwitch(
            header,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text'],
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text'],
            button_hover_color=self.COLORS['accent'],
            command=self._on_pwa_toggle
        )
        self.pwa_switch.pack(side="right")

        # 设置初始状态
        if config.use_pwa_mode:
            self.pwa_switch.select()

        # 说明文字
        ctk.CTkLabel(
            inner,
            text="开启后，打开浏览器时将使用 PWA 模式\n标题栏颜色会自动跟随 Luker 主题色变化",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted'],
            justify="left"
        ).pack(anchor="w")

    def _on_pwa_toggle(self):
        """PWA 模式开关切换回调"""
        config.use_pwa_mode = self.pwa_switch.get() == 1

    def _build_gcl_section(self, parent):
        """构建 GCL 设置区域"""
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        # 标题行
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            header, text="🚀  GCL 功能",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text']
        ).pack(side="left")

        # 开关
        self.gcl_switch = ctk.CTkSwitch(
            header,
            text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text'],
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text'],
            button_hover_color=self.COLORS['accent'],
            command=self._on_gcl_toggle
        )
        self.gcl_switch.pack(side="right")

        # 设置初始状态
        if config.gcl_enabled:
            self.gcl_switch.select()

        # 说明文字
        ctk.CTkLabel(
            inner,
            text="开启后，可在托盘菜单中控制 GCL 的启动和停止",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_muted'],
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # GCL 路径选择区域（仅在开启时显示）
        self._gcl_path_frame = ctk.CTkFrame(inner, fg_color="transparent")

        ctk.CTkLabel(
            self._gcl_path_frame, text="GCL start.bat 路径:",
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_dim']
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
            anchor="w"
        )
        self.gcl_path_label.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(
            path_row, text="📂 选择",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            corner_radius=8, height=32, width=80,
            command=self._select_gcl_path
        ).pack(side="right")

        # 根据开关状态显示或隐藏路径选择
        if config.gcl_enabled:
            self._gcl_path_frame.pack(fill="x")

    def _on_gcl_toggle(self):
        """GCL 开关切换回调"""
        enabled = self.gcl_switch.get() == 1

        if enabled:
            bat_path = config.gcl_bat_path
            if not bat_path or not config.is_valid_gcl_path(bat_path):
                selected = config.select_gcl_bat_path()
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

    def _select_gcl_path(self):
        """选择 GCL bat 路径"""
        path = config.select_gcl_bat_path()
        if path:
            self.gcl_path_label.configure(text=path)

    def _build_path_section(self, parent):
        section = ctk.CTkFrame(parent, fg_color=self.COLORS['card'], corner_radius=12)
        section.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(
            inner, text="📁  Luker 路径",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['text']
        ).pack(anchor="w", pady=(0, 10))

        # 路径和按钮在同一行（与 GCL 布局一致）
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
            anchor="w"
        )
        self.path_label.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(
            path_row, text="📂 选择",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            corner_radius=8, height=32, width=80,
            command=self._select_path
        ).pack(side="right")

    def _select_path(self):
        path = config.select_luker_path()
        if path:
            self.path_label.configure(text=path)

    def _build_footer(self, parent):
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", pady=(8, 0))

        ctk.CTkButton(
            footer, text="完成",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            corner_radius=10, height=42, width=120,
            command=self.destroy
        ).pack(side="right")
