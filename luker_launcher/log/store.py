"""日志存储：按来源保存有上限的历史日志，供界面重放和切换日志源。"""

import datetime
from collections import deque
from dataclasses import dataclass

from luker_launcher.log.classify import get_tag_for_line

# 每个日志源在内存中保留的最大条数
MAX_LOG_ENTRIES = 3000
# 单个日志源的文本上限，防止少量超长行占满内存
MAX_LOG_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime.datetime
    text: str


class LogStore:
    """有上限的日志缓冲区；超出条数或字节上限时丢弃最旧的记录。"""

    def __init__(
        self,
        max_entries: int = MAX_LOG_ENTRIES,
        max_bytes: int = MAX_LOG_BYTES,
    ) -> None:
        self._entries: deque[LogEntry] = deque()
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._bytes = 0
        self._last_error: LogEntry | None = None
        # 最近错误被容量淘汰后需要反向重扫一次
        self._last_error_dirty = False

    @staticmethod
    def _text_size(text: str) -> int:
        return len(text.encode("utf-8", errors="replace"))

    def append(
        self,
        text: str,
        timestamp: datetime.datetime | None = None,
    ) -> LogEntry:
        entry = LogEntry(timestamp or datetime.datetime.now(), text)
        self._entries.append(entry)
        self._bytes += self._text_size(text)
        if get_tag_for_line(text) == 'error':
            self._last_error = entry
            self._last_error_dirty = False

        while self._entries and (
            len(self._entries) > self._max_entries or self._bytes > self._max_bytes
        ):
            removed = self._entries.popleft()
            self._bytes -= self._text_size(removed.text)
            if removed is self._last_error:
                self._last_error = None
                self._last_error_dirty = True

        return entry

    def last_error(self) -> LogEntry | None:
        """返回当前缓冲区里最近一条错误日志；没有则返回 None。"""
        if self._last_error_dirty:
            self._last_error = next(
                (
                    entry
                    for entry in reversed(self._entries)
                    if get_tag_for_line(entry.text) == 'error'
                ),
                None,
            )
            self._last_error_dirty = False
        return self._last_error

    def snapshot(self) -> list[LogEntry]:
        """返回当前内容的浅拷贝，避免界面遍历时被后台线程修改。"""
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        self._bytes = 0
        self._last_error = None
        self._last_error_dirty = False

    def __len__(self) -> int:
        return len(self._entries)
