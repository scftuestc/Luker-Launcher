
import sys
import os
import customtkinter as ctk
import ctypes
from ctypes import windll, byref, sizeof, c_int
from typing import Dict
import queue
import datetime
import math
import tkinter as tk
import tkinter.font as tkfont

from config import config

# 每条队列每轮最多处理的日志行数
MAX_LOG_LINES_PER_CYCLE = 10


class WindowsBlur:
    class ACCENT_POLICY(ctypes.Structure):
        _fields_ = [
            ("AccentState", c_int),
            ("AccentFlags", c_int),
            ("GradientColor", ctypes.c_uint),
            ("AnimationId", c_int),
        ]

    class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
        _fields_ = [
            ("Attrib", c_int),
            ("pvData", ctypes.c_void_p),
            ("cbData", ctypes.c_size_t),
        ]

    class MARGINS(ctypes.Structure):
        _fields_ = [
            ("cxLeftWidth", c_int),
            ("cxRightWidth", c_int),
            ("cyTopHeight", c_int),
            ("cyBottomHeight", c_int),
        ]

    @staticmethod
    def enable_blur(hwnd, color=0xCC000000):
        user32 = windll.user32
        dwmapi = windll.dwmapi
        build = sys.getwindowsversion().build

        try:
            value = c_int(1)
            dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(value), sizeof(value))

            if build >= 22000:
                corner = c_int(2)
                dwmapi.DwmSetWindowAttribute(hwnd, 33, byref(corner), sizeof(corner))

            accent = WindowsBlur.ACCENT_POLICY()
            accent.AccentState = 4
            accent.AccentFlags = 2
            accent.GradientColor = color

            data = WindowsBlur.WINDOWCOMPOSITIONATTRIBDATA()
            data.Attrib = 19
            data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
            data.cbData = sizeof(accent)

            user32.SetWindowCompositionAttribute(hwnd, byref(data))

        except Exception as e:
            print(f"毛玻璃错误: {e}")

    @staticmethod
    def extend_frame(hwnd):
        margins = WindowsBlur.MARGINS(-1, -1, -1, -1)
        windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, byref(margins))


def get_ui_font():
    source_han_fonts = [
        'Source Han Sans SC',
        'Source Han Sans CN',
        'Noto Sans SC',
        'Noto Sans CJK SC',
        'Source Han Sans',
    ]
    available = tkfont.families()
    for font in source_han_fonts:
        if font in available:
            return font
    return 'Microsoft YaHei'


def get_mono_font():
    mono_fonts = [
        'Source Han Mono SC',
        'Noto Sans Mono CJK SC',
        'Sarasa Mono SC',
        'Consolas',
        'Cascadia Code',
    ]
    available = tkfont.families()
    for font in mono_fonts:
        if font in available:
            return font
    return 'Consolas'


class LogWindow(ctk.CTk):
    def __init__(self, on_hide_callback=None, on_start=None, on_stop=None):
        super().__init__()

        self.on_hide_callback = on_hide_callback
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop

        self.COLORS = config.get_theme_colors()

        config.add_theme_change_callback(self._on_theme_change)

        self.UI_FONT = get_ui_font()
        self.MONO_FONT = get_mono_font()

        self.withdraw()

        self.overrideredirect(True)

        self.title("Luker 日志")
        self.geometry("960x640+200+100")
        self.minsize(700, 450)

        self._set_window_icon()

        self.configure(fg_color=self.COLORS['bg'])
        self.attributes('-alpha', 0.97)

        self.after(150, self._setup_blur)

        self.bind('<Map>', self._on_map)

        self._drag_x = 0
        self._drag_y = 0

        self._resize_edge = None

        self._animation_phase = 0
        self._glow_intensity = 0
        self._glow_direction = 1

        # 日志源切换状态：'luker' 或 'gcl'
        self._log_source = 'luker'
        # 分别存储两个日志源的日志：(时间戳, 日志行)
        self._luker_logs: list[tuple[datetime.datetime, str]] = []
        self._gcl_logs: list[tuple[datetime.datetime, str]] = []

        self._build_ui()

        self._log_count = 0
        self._auto_scroll = True
        self._is_running = False
        self._last_log_timestamp: datetime.datetime | None = None

        self.log_queue: queue.Queue = queue.Queue()
        self.gcl_log_queue: queue.Queue = queue.Queue()

        self._process_logs()

        self._setup_resize()

        self._check_window_state()

        self._start_animations()

    def _set_window_icon(self):
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
                else:
                    self._create_dynamic_icon()
        except Exception as e:
            print(f"设置窗口图标失败: {e}")

    def _create_dynamic_icon(self):
        try:
            from PIL import Image, ImageDraw, ImageTk

            size = 64
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            margin = 4
            draw.rounded_rectangle(
                [margin, margin, size - margin, size - margin],
                radius=12,
                fill=(13, 17, 23, 255)
            )

            bar_colors = [(255, 107, 107), (254, 202, 87), (72, 219, 251), (29, 209, 161)]
            bar_width = 6
            bar_height = 28
            start_x = 14
            start_y = (size - bar_height) // 2

            for i, color in enumerate(bar_colors):
                x = start_x + i * (bar_width + 4)
                draw.rounded_rectangle(
                    [x, start_y, x + bar_width, start_y + bar_height],
                    radius=2,
                    fill=color + (255,)
                )

            photo = ImageTk.PhotoImage(img)
            self.iconphoto(True, photo)
            self._icon_photo = photo

        except Exception as e:
            print(f"动态生成图标失败: {e}")

    def _setup_blur(self):
        hwnd = windll.user32.GetParent(self.winfo_id())
        WindowsBlur.extend_frame(hwnd)
        bg = self.COLORS['bg']
        r = int(bg[1:3], 16)
        g = int(bg[3:5], 16)
        b = int(bg[5:7], 16)
        blur_color = 0xDD000000 | (b << 16) | (g << 8) | r
        WindowsBlur.enable_blur(hwnd, blur_color)

        self.update()

    def _on_theme_change(self, new_colors: Dict[str, str]) -> None:
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
            if hasattr(self, '_min_btn'):
                self._min_btn.configure(
                    hover_color=self.COLORS['card_hover'],
                    text_color=self.COLORS['text_dim']
                )
            if hasattr(self, '_close_btn'):
                self._close_btn.configure(
                    hover_color=self.COLORS['error'],
                    text_color=self.COLORS['text_dim']
                )

            if hasattr(self, '_clear_btn'):
                self._clear_btn.configure(
                    fg_color=self.COLORS['card'],
                    hover_color=self.COLORS['card_hover'],
                    text_color=self.COLORS['text']
                )
            if hasattr(self, 'scroll_btn'):
                self.scroll_btn.configure(
                    fg_color=self.COLORS['card'],
                    hover_color=self.COLORS['card_hover'],
                    text_color=self.COLORS['text']
                )

            # 搜索框主题更新
            if hasattr(self, '_search_frame'):
                self._search_frame.configure(fg_color=self.COLORS['card'])
            if hasattr(self, '_search_entry'):
                self._search_entry.configure(
                    text_color=self.COLORS['text'],
                    placeholder_text_color=self.COLORS['text_muted']
                )
            if hasattr(self, '_search_count_label'):
                self._search_count_label.configure(text_color=self.COLORS['text_muted'])
            if hasattr(self, '_search_prev_btn'):
                self._search_prev_btn.configure(
                    hover_color=self.COLORS['card_hover'],
                    text_color=self.COLORS['text_dim']
                )
            if hasattr(self, '_search_next_btn'):
                self._search_next_btn.configure(
                    hover_color=self.COLORS['card_hover'],
                    text_color=self.COLORS['text_dim']
                )
            if hasattr(self, '_search_clear_btn'):
                self._search_clear_btn.configure(
                    hover_color=self.COLORS['error'],
                    text_color=self.COLORS['text_dim']
                )

            if hasattr(self, '_status_card'):
                self._status_card.configure(fg_color=self.COLORS['card'])

            if hasattr(self, '_log_card'):
                self._log_card.configure(fg_color=self.COLORS['card'])
            if hasattr(self, 'log_text'):
                self.log_text.configure(
                    text_color=self.COLORS['text'],
                    scrollbar_button_color=self.COLORS['border'],
                    scrollbar_button_hover_color=self.COLORS['accent']
                )
                tb = self.log_text._textbox
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

        except Exception as e:
            print(f"应用主题时出错: {e}")

    def _start_animations(self):
        self._animate_glow()
        self._animate_status_pulse()

    def _animate_glow(self):
        self._glow_intensity += 0.03 * self._glow_direction
        if self._glow_intensity >= 1:
            self._glow_direction = -1
        elif self._glow_intensity <= 0:
            self._glow_direction = 1

        if hasattr(self, '_logo_bars'):
            colors_start = [(0xff, 0x6b, 0x6b), (0xfe, 0xca, 0x57), (0x48, 0xdb, 0xfb), (0x1d, 0xd1, 0xa1)]
            colors_end = [(0xf8, 0x71, 0x71), (0xff, 0xb7, 0x4d), (0x22, 0xd3, 0xee), (0x4a, 0xde, 0x80)]

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

    def _animate_status_pulse(self):
        if hasattr(self, 'status_dot') and self._is_running:
            self._animation_phase = (self._animation_phase + 0.1) % (2 * 3.14159)
            alpha = 0.5 + 0.5 * math.sin(self._animation_phase)

            r = int(0x3f + (0x2e - 0x3f) * alpha)
            g = int(0xb9 + (0xa0 - 0xb9) * alpha)
            b = int(0x50 + (0x43 - 0x50) * alpha)
            pulse_color = f"#{r:02x}{g:02x}{b:02x}"

            try:
                self.status_dot.configure(text_color=pulse_color)
            except tk.TclError:
                pass

        self.after(100, self._animate_status_pulse)

    def _setup_resize(self):
        self.bind('<Motion>', self._check_resize_edge)
        self.bind('<Button-1>', self._start_resize)
        self.bind('<B1-Motion>', self._do_resize)
        self.bind('<ButtonRelease-1>', self._end_resize)

    def _check_resize_edge(self, e):
        if e.widget != self:
            self.configure(cursor='')
            self._resize_edge = None
            return

        margin = 8
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
        elif x < margin:
            edge = 'w'
        elif x > w - margin:
            edge = 'e'
        elif y > h - margin:
            edge = 's'

        cursors = {
            'nw': 'size_nw_se', 'se': 'size_nw_se',
            'ne': 'size_ne_sw', 'sw': 'size_ne_sw',
            'n': 'size_ns', 's': 'size_ns',
            'w': 'size_we', 'e': 'size_we'
        }

        if edge:
            self.configure(cursor=cursors.get(edge, ''))
        else:
            self.configure(cursor='')

        self._resize_edge = edge

    def _start_resize(self, e):
        if e.widget != self or not self._resize_edge:
            return
        self._resize_start = (e.x_root, e.y_root, self.winfo_width(), self.winfo_height(), self.winfo_x(), self.winfo_y())

    def _do_resize(self, e):
        if not self._resize_edge or not hasattr(self, '_resize_start'):
            return
        if e.widget != self:
            return

        sx, sy, sw, sh, wx, wy = self._resize_start
        dx = e.x_root - sx
        dy = e.y_root - sy

        nw, nh, nx, ny = sw, sh, wx, wy

        if 'e' in self._resize_edge:
            nw = max(700, sw + dx)
        if 's' in self._resize_edge:
            nh = max(450, sh + dy)
        if 'w' in self._resize_edge:
            nw = max(700, sw - dx)
            if nw != sw:
                nx = wx + (sw - nw)
        if 'n' in self._resize_edge:
            nh = max(450, sh - dy)
            if nh != sh:
                ny = wy + (sh - nh)

        self.geometry(f"{nw}x{nh}+{nx}+{ny}")

    def _end_resize(self, e):
        self._resize_edge = None

    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_titlebar(main)
        self._build_toolbar(main)
        self._build_log_area(main)
        self._build_statusbar(main)

    def _build_titlebar(self, parent):
        self._titlebar = ctk.CTkFrame(
            parent, height=52,
            fg_color=self.COLORS['card'],
            corner_radius=14
        )
        self._titlebar.pack(fill="x", pady=(0, 10))
        self._titlebar.pack_propagate(False)

        self._titlebar.bind('<Button-1>', self._start_drag)
        self._titlebar.bind('<B1-Motion>', self._on_drag)
        self._titlebar.bind('<Double-Button-1>', self._toggle_maximize)

        left = ctk.CTkFrame(self._titlebar, fg_color="transparent")
        left.pack(side="left", padx=16, pady=12)
        left.bind('<Button-1>', self._start_drag)
        left.bind('<B1-Motion>', self._on_drag)

        logo = ctk.CTkFrame(left, fg_color="transparent")
        logo.pack(side="left")
        logo.bind('<Button-1>', self._start_drag)
        logo.bind('<B1-Motion>', self._on_drag)

        self._logo_bars = []
        gradient_colors = ['#ff6b6b', '#feca57', '#48dbfb', '#1dd1a1']
        for c in gradient_colors:
            bar_item = ctk.CTkFrame(logo, width=4, height=22, fg_color=c, corner_radius=2)
            bar_item.pack(side="left", padx=1)
            self._logo_bars.append(bar_item)

        self._title_label = ctk.CTkLabel(
            left, text="Luker 日志",
            font=ctk.CTkFont(family=self.UI_FONT, size=16, weight="bold"),
            text_color=self.COLORS['text']
        )
        self._title_label.pack(side="left", padx=(14, 0))
        self._title_label.bind('<Button-1>', self._start_drag)
        self._title_label.bind('<B1-Motion>', self._on_drag)

        right = ctk.CTkFrame(self._titlebar, fg_color="transparent")
        right.pack(side="right", padx=10)

        # 日志源切换按钮（仅在 GCL 启用时显示）
        self._log_source_btn = ctk.CTkButton(
            right, text="📊 Luker 日志", width=110, height=32,
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['card_hover'],
            text_color="#ffffff",
            font=ctk.CTkFont(family=self.UI_FONT, size=12, weight="bold"),
            corner_radius=8,
            command=self._toggle_log_source
        )
        # 初始隐藏，只有 GCL 启用时才显示
        # self._log_source_btn.pack(side="left", padx=2)

        self._min_btn = ctk.CTkButton(
            right, text="─", width=40, height=32,
            fg_color="transparent",
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_dim'],
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=8,
            command=self._on_minimize
        )
        self._min_btn.pack(side="left", padx=2)

        self._close_btn = ctk.CTkButton(
            right, text="✕", width=40, height=32,
            fg_color="transparent",
            hover_color=self.COLORS['error'],
            text_color=self.COLORS['text_dim'],
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=8,
            command=self._on_close
        )
        self._close_btn.pack(side="left", padx=2)

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _on_drag(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _toggle_maximize(self, e):
        pass

    def _on_minimize(self):
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            SW_MINIMIZE = 6
            windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
            self._minimized = True
        except Exception as e:
            print(f"最小化窗口失败: {e}")

    def _on_map(self, event):
        if hasattr(self, '_minimized') and self._minimized:
            self._minimized = False
            self.lift()
            self.focus_force()

    def _check_window_state(self):
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            is_minimized = windll.user32.IsIconic(hwnd)

            if hasattr(self, '_was_minimized'):
                if self._was_minimized and not is_minimized:
                    self.after(50, self._restore_window)

            self._was_minimized = is_minimized
        except Exception:
            pass

        self.after(200, self._check_window_state)

    def _restore_window(self):
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            SW_RESTORE = 9
            windll.user32.ShowWindow(hwnd, SW_RESTORE)
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _on_close(self):
        self.hide()
        if self.on_hide_callback:
            self.on_hide_callback()

    def _build_toolbar(self, parent):
        self._toolbar = ctk.CTkFrame(parent, fg_color="transparent", height=48)
        self._toolbar.pack(fill="x", pady=(0, 10))

        left = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        left.pack(side="left")

        self._clear_btn = ctk.CTkButton(
            left, text="🗑️ 清除",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            fg_color=self.COLORS['card'],
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text'],
            corner_radius=10, width=100, height=40,
            command=self.clear_logs
        )
        self._clear_btn.pack(side="left", padx=(0, 8))

        self.scroll_btn = ctk.CTkButton(
            left, text="📜 自动滚动",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            fg_color=self.COLORS['card'],
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text'],
            corner_radius=10, width=130, height=40,
            command=self._toggle_scroll
        )
        self.scroll_btn.pack(side="left", padx=(0, 8))

        # 搜索框
        self._search_frame = ctk.CTkFrame(left, fg_color=self.COLORS['card'], corner_radius=10)
        self._search_frame.pack(side="left")

        search_inner = ctk.CTkFrame(self._search_frame, fg_color="transparent")
        search_inner.pack(padx=8, pady=4)

        ctk.CTkLabel(
            search_inner, text="🔍",
            font=ctk.CTkFont(size=14),
            text_color=self.COLORS['text_muted']
        ).pack(side="left", padx=(4, 4))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add('write', self._on_search_change)

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
            textvariable=self._search_var
        )
        self._search_entry.pack(side="left")

        # 搜索结果计数和导航
        self._search_nav = ctk.CTkFrame(search_inner, fg_color="transparent")
        self._search_nav.pack(side="left", padx=(4, 0))

        self._search_count_label = ctk.CTkLabel(
            self._search_nav, text="",
            font=ctk.CTkFont(family=self.UI_FONT, size=11),
            text_color=self.COLORS['text_muted'],
            width=50
        )
        self._search_count_label.pack(side="left")

        self._search_prev_btn = ctk.CTkButton(
            self._search_nav, text="▲", width=24, height=24,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_dim'],
            corner_radius=4,
            command=self._search_prev
        )
        self._search_prev_btn.pack(side="left", padx=1)

        self._search_next_btn = ctk.CTkButton(
            self._search_nav, text="▼", width=24, height=24,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=self.COLORS['card_hover'],
            text_color=self.COLORS['text_dim'],
            corner_radius=4,
            command=self._search_next
        )
        self._search_next_btn.pack(side="left", padx=1)

        self._search_clear_btn = ctk.CTkButton(
            self._search_nav, text="✕", width=24, height=24,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=self.COLORS['error'],
            text_color=self.COLORS['text_dim'],
            corner_radius=4,
            command=self._clear_search
        )
        self._search_clear_btn.pack(side="left", padx=1)

        # 初始化搜索状态
        self._search_results = []
        self._search_current_index = -1
        self._search_nav.pack_forget()  # 初始隐藏导航按钮

        right = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        right.pack(side="right")

        self._status_card = ctk.CTkFrame(
            right, fg_color=self.COLORS['card'], corner_radius=10
        )
        self._status_card.pack()

        inner = ctk.CTkFrame(self._status_card, fg_color="transparent")
        inner.pack(padx=16, pady=10)

        self.play_btn = ctk.CTkButton(
            inner, text="▶", width=36, height=36,
            font=ctk.CTkFont(size=16),
            fg_color=self.COLORS['success'],
            hover_color="#2ea043",
            text_color="#ffffff",
            corner_radius=18,
            command=self._toggle_running
        )
        self.play_btn.pack(side="left", padx=(0, 12))

        self.status_dot = ctk.CTkLabel(
            inner, text="●", font=ctk.CTkFont(size=18),
            text_color=self.COLORS['error']
        )
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_text = ctk.CTkLabel(
            inner, text="已停止",
            font=ctk.CTkFont(family=self.UI_FONT, size=14, weight="bold"),
            text_color=self.COLORS['error']
        )
        self.status_text.pack(side="left")

    def _build_log_area(self, parent):
        self._log_card = ctk.CTkFrame(
            parent, fg_color=self.COLORS['card'], corner_radius=14
        )
        self._log_card.pack(fill="both", expand=True, pady=(0, 10))

        self.log_text = ctk.CTkTextbox(
            self._log_card, fg_color="transparent",
            text_color=self.COLORS['text'],
            font=ctk.CTkFont(family=self.MONO_FONT, size=13),
            corner_radius=10,
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent']
        )
        self.log_text.pack(fill="both", expand=True, padx=12, pady=12)

        tb = self.log_text._textbox
        tb.tag_configure('time', foreground=self.COLORS['text_muted'])
        tb.tag_configure('info', foreground=self.COLORS['info'])
        tb.tag_configure('success', foreground=self.COLORS['success'])
        tb.tag_configure('error', foreground=self.COLORS['error'])
        tb.tag_configure('warn', foreground=self.COLORS['warning'])
        tb.tag_configure('accent', foreground=self.COLORS['accent'])
        tb.tag_configure('dim', foreground=self.COLORS['text_dim'])
        tb.tag_configure('separator', foreground=self.COLORS['accent'], elide=False)

    def _build_statusbar(self, parent):
        self._statusbar = ctk.CTkFrame(
            parent, height=42,
            fg_color=self.COLORS['card'], corner_radius=10
        )
        self._statusbar.pack(fill="x")
        self._statusbar.pack_propagate(False)

        self.count_label = ctk.CTkLabel(
            self._statusbar, text="📝 0 条日志",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text_muted']
        )
        self.count_label.pack(side="left", padx=16, pady=10)

        self._version_label = ctk.CTkLabel(
            self._statusbar, text="v1.0.0",
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text_muted']
        )
        self._version_label.pack(side="right", padx=16, pady=10)

    def _get_tag_for_line(self, line: str) -> str:
        line_lower = line.lower()
        if '[错误]' in line or 'error' in line_lower or 'fail' in line_lower:
            return 'error'
        elif '[警告]' in line or 'warn' in line_lower:
            return 'warn'
        elif '[信息]' in line or 'info' in line_lower:
            return 'info'
        elif '[启动器]' in line:
            return 'accent'
        elif 'success' in line_lower or '成功' in line or 'listening' in line_lower or 'compiled' in line_lower:
            return 'success'
        return 'dim'

    def add_log(self, line: str, source: str = 'luker') -> None:
        """添加日志，source 可以是 'luker' 或 'gcl'"""
        if source == 'gcl':
            self.gcl_log_queue.put(line)
        else:
            self.log_queue.put(line)

    def add_gcl_log(self, line: str) -> None:
        """添加 GCL 日志的便捷方法"""
        self.gcl_log_queue.put(line)

    def _drain_log_queue(self, log_queue: queue.Queue, log_store: list, source: str) -> None:
        """从队列取一批日志写入存储；仅当前日志源需要立即渲染。"""
        for _ in range(MAX_LOG_LINES_PER_CYCLE):
            try:
                line = log_queue.get_nowait()
            except queue.Empty:
                return

            timestamp = datetime.datetime.now()
            log_store.append((timestamp, line))
            if self._log_source == source:
                self._add_log_line(line, timestamp)

    def _process_logs(self) -> None:
        # 两个队列各自限额，避免一个日志源刷屏时另一个被饿死
        self._drain_log_queue(self.log_queue, self._luker_logs, 'luker')
        self._drain_log_queue(self.gcl_log_queue, self._gcl_logs, 'gcl')

        if not self.log_queue.empty() or not self.gcl_log_queue.empty():
            self.after(10, self._process_logs)
        else:
            self.after(100, self._process_logs)

    def _toggle_log_source(self) -> None:
        """切换日志源"""
        if self._log_source == 'luker':
            self._log_source = 'gcl'
            self._log_source_btn.configure(
                text="🚀 GCL 日志",
                fg_color=self.COLORS['warning']
            )
            self._title_label.configure(text="GCL 日志")
        else:
            self._log_source = 'luker'
            self._log_source_btn.configure(
                text="📊 Luker 日志",
                fg_color=self.COLORS['accent']
            )
            self._title_label.configure(text="Luker 日志")

        # 切换日志显示
        self._refresh_log_display()

    def _refresh_log_display(self) -> None:
        """刷新日志显示，根据当前日志源重新加载日志"""
        # 清空当前显示
        tb = self.log_text._textbox
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")

        # 重置计数
        self._log_count = 0
        self._last_log_timestamp = None

        # 加载对应日志源的日志
        logs = self._luker_logs if self._log_source == 'luker' else self._gcl_logs
        for timestamp, line in logs:
            self._add_log_line(line, timestamp)

        self.count_label.configure(text=f"📝 {self._log_count} 条日志")

    def set_gcl_enabled(self, enabled: bool) -> None:
        """设置 GCL 功能是否启用，控制切换按钮的显示"""
        if enabled:
            self._log_source_btn.pack(side="left", padx=2, before=self._min_btn)
        else:
            self._log_source_btn.pack_forget()
            # 如果当前显示的是 GCL 日志，切换回 Luker 日志
            if self._log_source == 'gcl':
                self._log_source = 'luker'
                self._log_source_btn.configure(
                    text="📊 Luker 日志",
                    fg_color=self.COLORS['accent']
                )
                self._title_label.configure(text="Luker 日志")
                self._refresh_log_display()

    def _add_log_line(self, text: str, timestamp: datetime.datetime | None = None) -> None:
        now = timestamp if timestamp is not None else datetime.datetime.now()
        ts = now.strftime("%H:%M:%S")

        tag = self._get_tag_for_line(text)

        tb = self.log_text._textbox
        tb.configure(state="normal")

        if self._last_log_timestamp is not None and (now - self._last_log_timestamp).total_seconds() >= 60:
            tb.insert("end", "\n")
            separator_text = "─" * 40
            separator = tk.Label(tb, text=separator_text, fg=self.COLORS['accent'],
                               bg=self._log_card.cget('fg_color')[1] if isinstance(self._log_card.cget('fg_color'), tuple) else self._log_card.cget('fg_color'),
                               font=(self.MONO_FONT, 10), bd=0, highlightthickness=0)
            tb.window_create("end", window=separator)
            tb.insert("end", "\n\n")

        self._last_log_timestamp = now

        tb.insert("end", f"[{ts}] ", "time")
        tb.insert("end", f"{text}\n", tag)
        if self._auto_scroll:
            tb.see("end")
        tb.configure(state="disabled")

        self._log_count += 1
        self.count_label.configure(text=f"📝 {self._log_count} 条日志")

    def clear_logs(self) -> None:
        tb = self.log_text._textbox
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")

        # 同步清空底层存储，否则切换日志源后已清除的内容会重新出现
        self._luker_logs.clear()
        self._gcl_logs.clear()
        self._log_count = 0
        self._last_log_timestamp = None
        self.count_label.configure(text="📝 0 条日志")

        self._clear_search_highlights()
        self._search_results = []
        self._search_current_index = -1
        self._search_nav.pack_forget()
        self._search_var.set("")

    def _toggle_scroll(self):
        self._auto_scroll = not self._auto_scroll
        self.scroll_btn.configure(
            text="📜 自动滚动" if self._auto_scroll else "📜 已暂停"
        )

    def _toggle_running(self):
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
            self.play_btn.configure(
                text="⏸",
                fg_color=self.COLORS['error'],
                hover_color="#da3633"
            )
        else:
            self.status_dot.configure(text_color=self.COLORS['error'])
            self.status_text.configure(text="已停止", text_color=self.COLORS['error'])
            self.play_btn.configure(
                text="▶",
                fg_color=self.COLORS['success'],
                hover_color="#2ea043"
            )

    def show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self) -> None:
        self.withdraw()

    def is_visible(self) -> bool:
        return self.winfo_viewable()

    # ===== 搜索功能 =====

    def _on_search_change(self, *args):
        """当搜索框内容改变时触发"""
        search_text = self._search_var.get().strip()

        if not search_text:
            self._clear_search_highlights()
            self._search_nav.pack_forget()
            self._search_results = []
            self._search_current_index = -1
            return

        # 显示导航按钮
        self._search_nav.pack(side="left", padx=(4, 0))

        # 执行搜索
        self._perform_search(search_text)

    def _perform_search(self, search_text: str):
        """执行搜索并高亮结果"""
        tb = self.log_text._textbox

        # 清除之前的高亮
        self._clear_search_highlights()

        # 配置搜索高亮标签
        tb.tag_configure('search_highlight', background=self.COLORS['warning'], foreground='#000000')
        tb.tag_configure('search_current', background=self.COLORS['accent'], foreground='#ffffff')

        # 搜索所有匹配项
        self._search_results = []
        start_pos = "1.0"

        while True:
            # 不区分大小写搜索
            pos = tb.search(search_text, start_pos, stopindex="end", nocase=True)
            if not pos:
                break

            # 计算结束位置
            end_pos = f"{pos}+{len(search_text)}c"
            self._search_results.append((pos, end_pos))

            # 添加高亮
            tb.tag_add('search_highlight', pos, end_pos)

            # 移动到下一个位置继续搜索
            start_pos = end_pos

        # 更新搜索结果计数
        count = len(self._search_results)
        if count > 0:
            self._search_current_index = 0
            self._highlight_current_result()
            self._search_count_label.configure(text=f"{1}/{count}")
        else:
            self._search_current_index = -1
            self._search_count_label.configure(text="0/0")

    def _clear_search_highlights(self):
        """清除所有搜索高亮"""
        tb = self.log_text._textbox
        try:
            tb.tag_remove('search_highlight', "1.0", "end")
            tb.tag_remove('search_current', "1.0", "end")
        except tk.TclError:
            pass

    def _highlight_current_result(self):
        """高亮当前选中的搜索结果"""
        if not self._search_results or self._search_current_index < 0:
            return

        tb = self.log_text._textbox

        # 移除之前的当前高亮
        tb.tag_remove('search_current', "1.0", "end")

        # 获取当前结果
        pos, end_pos = self._search_results[self._search_current_index]

        # 添加当前高亮
        tb.tag_add('search_current', pos, end_pos)

        # 确保当前高亮在所有高亮之上
        tb.tag_raise('search_current')

        # 滚动到当前结果
        tb.see(pos)

        # 更新计数显示
        self._search_count_label.configure(
            text=f"{self._search_current_index + 1}/{len(self._search_results)}"
        )

    def _search_next(self):
        """跳转到下一个搜索结果"""
        if not self._search_results:
            return

        self._search_current_index = (self._search_current_index + 1) % len(self._search_results)
        self._highlight_current_result()

    def _search_prev(self):
        """跳转到上一个搜索结果"""
        if not self._search_results:
            return

        self._search_current_index = (self._search_current_index - 1) % len(self._search_results)
        self._highlight_current_result()

    def _clear_search(self):
        """清除搜索"""
        self._search_var.set("")
        self._search_entry.focus_set()
