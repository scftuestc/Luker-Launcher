"""日志搜索状态与高亮控制。"""

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

MAX_SEARCH_RESULTS = 5000


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
        tb.tag_configure('search_highlight', background=colors['warning'], foreground='#000000')
        tb.tag_configure('search_current', background=colors['accent'], foreground='#ffffff')

    def _clear_highlights(self) -> None:
        tb = self._get_textbox()
        try:
            tb.tag_remove('search_highlight', "1.0", "end")
            tb.tag_remove('search_current', "1.0", "end")
        except tk.TclError:
            pass
