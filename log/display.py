"""日志渲染缓冲与颜色标签。"""

import datetime
import tkinter as tk
from collections import deque
from collections.abc import Callable, Mapping, Sequence

import customtkinter as ctk

from log.store import MAX_LOG_BYTES, MAX_LOG_ENTRIES, LogEntry

_TAG_COLOR_KEYS = {
    'time': 'text_muted',
    'info': 'info',
    'success': 'success',
    'error': 'error',
    'warn': 'warning',
    'accent': 'accent',
    'dim': 'text_dim',
}


def configure_log_tags(textbox: tk.Text, colors: Mapping[str, str]) -> None:
    """把日志级别映射到文本标签颜色。"""
    for tag, color_key in _TAG_COLOR_KEYS.items():
        textbox.tag_configure(tag, foreground=colors[color_key])
    textbox.tag_configure('separator', foreground=colors['accent'], elide=False)


def get_tag_for_line(line: str) -> str:
    """按日志内容选择颜色标签。"""
    line_lower = line.lower()
    # GCL 日志带 [GCL 错误] 这类作用域前缀，归一化后复用同一套匹配
    normalized = line.replace('[GCL ', '[')
    if '[错误]' in normalized or 'error' in line_lower or 'fail' in line_lower:
        return 'error'
    elif '[警告]' in normalized or 'warn' in line_lower:
        return 'warn'
    elif '[信息]' in normalized or 'info' in line_lower:
        return 'info'
    elif '[启动器]' in line:
        return 'accent'
    elif (
        'success' in line_lower
        or '成功' in line
        or 'listening' in line_lower
        or 'compiled' in line_lower
    ):
        return 'success'
    return 'dim'


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
