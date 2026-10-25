"""日志搜索结果状态与搜索框。"""

import contextlib
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from ui.buttons import ButtonRole, button_colors, make_button
from ui.icons import toolbar_icon

MAX_SEARCH_RESULTS = 5000
SEARCH_DEBOUNCE_MS = 250
SEARCH_HINT_TEXT = "搜索日志..."


class LogSearch:
    """负责搜索结果、当前选中项和高亮标签，不负责输入防抖。"""

    def __init__(
        self,
        get_textbox: Callable[[], tk.Text],
        count_label: ctk.CTkLabel,
        nav_frame: ctk.CTkFrame,
        get_colors: Callable[[], dict[str, str]],
    ) -> None:
        self._get_textbox = get_textbox
        self._count_label = count_label
        self._nav_frame = nav_frame
        self._get_colors = get_colors
        self.results: list[tuple[str, str]] = []
        self.current_index = -1
        self.truncated = False

    def clear_state(self) -> None:
        """清除高亮、结果和导航状态。"""
        self._clear_highlights()
        self.results = []
        self.current_index = -1
        self.truncated = False
        self._nav_frame.pack_forget()
        self._count_label.configure(text="")

    def refresh_colors(self) -> None:
        """主题切换后重配高亮标签，保留已有搜索结果。"""
        self._configure_highlight_tags()

    def perform(self, search_text: str) -> None:
        """执行搜索并高亮全部结果。"""
        tb = self._get_textbox()
        self._clear_highlights()
        self._configure_highlight_tags()

        self.results = []
        self.truncated = False
        start_pos = "1.0"

        while len(self.results) < MAX_SEARCH_RESULTS:
            pos = tb.search(search_text, start_pos, stopindex="end", nocase=True)
            if not pos:
                break

            end_pos = f"{pos}+{len(search_text)}c"
            self.results.append((pos, end_pos))
            tb.tag_add('search_highlight', pos, end_pos)
            start_pos = end_pos

        if len(self.results) >= MAX_SEARCH_RESULTS:
            # 达到上限后再看一眼是否还有匹配，用于显示截断标记
            self.truncated = bool(tb.search(search_text, start_pos, stopindex="end", nocase=True))

        if self.results:
            self.current_index = 0
            self.highlight_current()
        else:
            self.current_index = -1
            self._count_label.configure(text="0/0")

    def adjust(self, removed_lines: int) -> None:
        """文本头部被裁剪后，同步平移已保存的搜索结果位置。"""
        if not self.results:
            return

        adjusted = []
        removed_before_current = 0
        for index, (start, end) in enumerate(self.results):
            start_line, start_col = map(int, start.split("."))
            end_base, sep, end_offset = end.partition("+")
            end_line, end_col = map(int, end_base.split("."))
            start_line -= removed_lines
            end_line -= removed_lines
            if start_line >= 1:
                new_end = f"{end_line}.{end_col}"
                if sep:
                    new_end += f"+{end_offset}"
                adjusted.append((f"{start_line}.{start_col}", new_end))
            elif index < self.current_index:
                removed_before_current += 1

        self.results = adjusted
        if adjusted:
            new_index = self.current_index - removed_before_current
            self.current_index = max(0, min(new_index, len(adjusted) - 1))

            # 不滚动窗口，只把“当前结果”标记移到仍然有效的位置
            tb = self._get_textbox()
            tb.tag_remove('search_current', "1.0", "end")
            start, end = adjusted[self.current_index]
            tb.tag_add('search_current', start, end)
            tb.tag_raise('search_current')
            self._count_label.configure(text=self.count_text(self.current_index))
        else:
            self.current_index = -1
            self._count_label.configure(text="0/0")

    def count_text(self, index: int) -> str:
        """生成“当前/总数”文本，结果被截断时追加 +。"""
        suffix = "+" if self.truncated else ""
        return f"{index + 1}/{len(self.results)}{suffix}"

    def highlight_current(self) -> None:
        """高亮当前选中的搜索结果。"""
        if not self.results or self.current_index < 0:
            return

        tb = self._get_textbox()
        tb.tag_remove('search_current', "1.0", "end")
        pos, end_pos = self.results[self.current_index]
        tb.tag_add('search_current', pos, end_pos)
        # 确保当前高亮在所有高亮之上
        tb.tag_raise('search_current')
        tb.see(pos)
        self._count_label.configure(text=self.count_text(self.current_index))

    def next(self) -> None:
        """跳转到下一个搜索结果。"""
        if not self.results:
            return
        self.current_index = (self.current_index + 1) % len(self.results)
        self.highlight_current()

    def prev(self) -> None:
        """跳转到上一个搜索结果。"""
        if not self.results:
            return
        self.current_index = (self.current_index - 1) % len(self.results)
        self.highlight_current()

    def _configure_highlight_tags(self) -> None:
        colors = self._get_colors()
        tb = self._get_textbox()
        tb.tag_configure('search_highlight', background=colors['warning'], foreground=colors['bg'])
        tb.tag_configure(
            'search_current', background=colors['accent'], foreground=colors['on_accent']
        )

    def _clear_highlights(self) -> None:
        tb = self._get_textbox()
        try:
            tb.tag_remove('search_highlight', "1.0", "end")
            tb.tag_remove('search_current', "1.0", "end")
        except tk.TclError:
            pass


class SearchBar:
    """管理搜索输入、防抖、提示覆盖层和结果导航。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        host: tk.Misc,
        ui_font: str,
        get_colors: Callable[[], dict[str, str]],
        get_textbox: Callable[[], tk.Text],
        get_scaling: Callable[[], float] | None = None,
    ) -> None:
        self._host = host
        self._ui_font = ui_font
        self._get_colors = get_colors
        self._get_scaling = get_scaling
        self._job: str | None = None
        self._focused = False
        self._clearing = False
        self._buttons: list[tuple[ctk.CTkButton, ButtonRole]] = []

        colors = get_colors()
        self.frame = ctk.CTkFrame(
            parent,
            fg_color=colors['card'],
            corner_radius=10,
            border_width=1,
            border_color=colors['border'],
        )

        inner = ctk.CTkFrame(self.frame, fg_color="transparent")
        inner.pack(fill="x", expand=True, padx=8, pady=4)

        self.icon = ctk.CTkLabel(
            inner,
            image=toolbar_icon('search', colors['text_muted']),
            text="",
            width=18,
            height=18,
        )
        self.icon.pack(side="left", padx=(4, 6))

        self.var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            inner,
            font=ctk.CTkFont(family=ui_font, size=13),
            fg_color="transparent",
            border_width=0,
            text_color=colors['text'],
            width=150,
            height=32,
            textvariable=self.var,
        )
        self.entry.pack(side="left", fill="x", expand=True)

        # 原生 placeholder 与 textvariable 同用时不会生效，改用独立 hint 覆盖层
        self.hint = ctk.CTkLabel(
            inner,
            text=SEARCH_HINT_TEXT,
            font=ctk.CTkFont(family=ui_font, size=13),
            text_color=colors['text_muted'],
            fg_color="transparent",
            height=18,
        )
        self.hint.bind("<Button-1>", lambda _event: self.entry.focus_set())
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

        self.nav = ctk.CTkFrame(inner, fg_color="transparent")
        self.nav.pack(side="left", padx=(4, 0))

        self.count_label = ctk.CTkLabel(
            self.nav,
            text="",
            font=ctk.CTkFont(family=ui_font, size=11),
            text_color=colors['text_muted'],
            width=50,
        )
        self.count_label.pack(side="left")

        prev_btn = self._make_nav_button('▲', 'ghost', self.prev)
        prev_btn.pack(side="left", padx=1)
        next_btn = self._make_nav_button('▼', 'ghost', self.next)
        next_btn.pack(side="left", padx=1)
        clear_btn = self._make_nav_button('✕', 'danger_ghost', self.clear_and_focus)
        clear_btn.pack(side="left", padx=1)

        self.nav.pack_forget()

        self.search = LogSearch(get_textbox, self.count_label, self.nav, get_colors)
        self.var.trace_add('write', self._on_change)
        self._update_hint()

    @property
    def focused(self) -> bool:
        return self._focused

    def _make_nav_button(
        self,
        text: str,
        role: ButtonRole,
        command: Callable[[], None],
    ) -> ctk.CTkButton:
        button = make_button(
            self.nav,
            role,
            self._get_colors(),
            text=text,
            width=26,
            height=26,
            corner_radius=6,
            font_size=10,
            command=command,
        )
        self._buttons.append((button, role))
        return button

    def refresh_colors(self) -> None:
        """主题切换后重配搜索框、图标、提示和导航按钮。"""
        colors = self._get_colors()
        self.frame.configure(fg_color=colors['card'], border_color=colors['border'])
        self.entry.configure(text_color=colors['text'])
        self.hint.configure(text_color=colors['text_muted'])
        self.count_label.configure(text_color=colors['text_muted'])
        self.icon.configure(image=toolbar_icon('search', colors['text_muted']))
        for button, role in self._buttons:
            button.configure(**button_colors(role, colors))
        self.search.refresh_colors()

    def adjust(self, removed_lines: int) -> None:
        self.search.adjust(removed_lines)

    def has_query(self) -> bool:
        return bool(self.var.get().strip())

    def rerun(self) -> None:
        """按当前输入重新搜索；由防抖任务和日志重放结束回调共用。"""
        self._job = None
        search_text = self.var.get().strip()
        if not search_text:
            self.search.clear_state()
            return

        self.nav.pack(side="left", padx=(4, 0))
        self.search.perform(search_text)

    def reset(self) -> None:
        """取消防抖并清除高亮、结果和导航。"""
        self.cancel_pending()
        self.search.clear_state()

    def clear_and_focus(self) -> None:
        """清空输入并把焦点交还搜索框。"""
        self.cancel_pending()
        self._clearing = True
        try:
            self.var.set("")
        finally:
            self._clearing = False
        self.search.clear_state()
        self._update_hint()
        self.entry.focus_set()

    def cancel_pending(self) -> None:
        if self._job is None:
            return
        with contextlib.suppress(tk.TclError):
            self._host.after_cancel(self._job)
        self._job = None

    def next(self) -> None:
        self.search.next()

    def prev(self) -> None:
        self.search.prev()

    def on_map(self) -> None:
        """窗口显示后重新对齐 hint，此时 DPI 缩放已经注册。"""
        self._update_hint()

    def _on_change(self, *args: str) -> None:
        self.cancel_pending()
        if self._clearing:
            return

        if not self.var.get().strip():
            self.search.clear_state()
            self._update_hint()
            return

        self._job = self._host.after(SEARCH_DEBOUNCE_MS, self.rerun)
        self._update_hint()

    def _on_focus_in(self, _event: tk.Event | None = None) -> None:
        self._focused = True
        self._update_hint()

    def _on_focus_out(self, _event: tk.Event | None = None) -> None:
        self._focused = False
        self._update_hint()

    def _update_hint(self) -> None:
        """输入为空且未聚焦时，把浅色提示覆盖在输入框文字起点上。"""
        if self._focused or self.var.get():
            self.hint.place_forget()
            return
        self.hint.place(
            in_=self.entry,
            x=self._hint_x(),
            rely=0.5,
            anchor='w',
        )

    def _hint_x(self) -> int:
        try:
            scale = self._get_scaling() if self._get_scaling is not None else 1.0
        except AttributeError:
            # 构造早期缩放尚未注册，先按 1.0 放置，Map 后会重新校正
            scale = 1.0
        return round(6 * scale)
