"""日志渲染缓冲：插入、计数和裁剪。"""

import datetime
import tkinter as tk
from collections import deque
from collections.abc import Callable, Sequence

import customtkinter as ctk

from log_store import MAX_LOG_BYTES, MAX_LOG_ENTRIES, LogEntry
from log_tags import get_tag_for_line


class LogDisplay:
    """维护 Text 控件中每条日志占用的行数/字节数，并按上限裁剪。"""

    def __init__(
        self,
        get_textbox: Callable[[], tk.Text],
        count_label: ctk.CTkLabel,
    ) -> None:
        self._get_textbox = get_textbox
        self._count_label = count_label
        self.entry_lines: deque[int] = deque()
        self.entry_bytes: deque[int] = deque()
        self.bytes = 0
        self.last_timestamp: datetime.datetime | None = None

    @property
    def count(self) -> int:
        return len(self.entry_lines)

    def reset(self) -> None:
        """清空缓冲并同步计数标签。"""
        self.entry_lines.clear()
        self.entry_bytes.clear()
        self.bytes = 0
        self.last_timestamp = None
        self._update_count_label()

    def add_entries(self, entries: Sequence[LogEntry], *, auto_scroll: bool) -> int:
        """批量插入日志，返回因超限删除的文本行数。"""
        if not entries:
            return 0

        tb = self._get_textbox()
        tb.configure(state="normal")
        for entry in entries:
            self._insert_entry(tb, entry.text, entry.timestamp)

        if auto_scroll:
            tb.see("end")
        tb.configure(state="disabled")

        removed_lines = self.trim()
        self._update_count_label()
        return removed_lines

    def trim(self) -> int:
        """超过条数或字节上限时从 Text 头部删除最旧的日志。"""
        if len(self.entry_lines) <= MAX_LOG_ENTRIES and self.bytes <= MAX_LOG_BYTES:
            return 0

        removed_lines = 0
        while self.entry_lines and (
            len(self.entry_lines) > MAX_LOG_ENTRIES or self.bytes > MAX_LOG_BYTES
        ):
            removed_lines += self.entry_lines.popleft()
            self.bytes -= self.entry_bytes.popleft()

        if removed_lines <= 0:
            return 0

        tb = self._get_textbox()
        tb.configure(state="normal")
        tb.delete("1.0", f"{removed_lines + 1}.0")
        tb.configure(state="disabled")
        self._update_count_label()
        return removed_lines

    def _insert_entry(self, tb: tk.Text, text: str, timestamp: datetime.datetime) -> None:
        ts = timestamp.strftime("%H:%M:%S")
        tag = get_tag_for_line(text)

        lines_before = int(tb.index("end-1c").split(".")[0])

        if (
            self.last_timestamp is not None
            and (timestamp - self.last_timestamp).total_seconds() >= 60
        ):
            tb.insert("end", "\n")
            tb.insert("end", "─" * 40 + "\n", "separator")

        self.last_timestamp = timestamp

        tb.insert("end", f"[{ts}] ", "time")
        tb.insert("end", f"{text}\n", tag)

        lines_after = int(tb.index("end-1c").split(".")[0])
        self.entry_lines.append(lines_after - lines_before)
        size = len(text.encode("utf-8", errors="replace"))
        self.entry_bytes.append(size)
        self.bytes += size

    def _update_count_label(self) -> None:
        self._count_label.configure(text=f"📝 {len(self.entry_lines)} 条日志")
