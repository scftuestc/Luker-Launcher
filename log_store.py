"""日志存储：按来源保存有上限的历史日志，供界面重放和切换日志源。"""

import datetime
from collections import deque
from dataclasses import dataclass

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

        while self._entries and (
            len(self._entries) > self._max_entries or self._bytes > self._max_bytes
        ):
            removed = self._entries.popleft()
            self._bytes -= self._text_size(removed.text)

        return entry

    def snapshot(self) -> list[LogEntry]:
        """返回当前内容的浅拷贝，避免界面遍历时被后台线程修改。"""
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        self._bytes = 0

    def __len__(self) -> int:
        return len(self._entries)
