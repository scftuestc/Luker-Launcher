"""日志存储：按来源保存有上限的历史日志，供界面重放和切换日志源。"""

import datetime
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional

# 每个日志源在内存中保留的最大条数
MAX_LOG_ENTRIES = 3000


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime.datetime
    text: str


class LogStore:
    """固定容量的日志缓冲区；超出上限时自动丢弃最旧的记录。"""

    def __init__(self, max_entries: int = MAX_LOG_ENTRIES) -> None:
        self._entries: Deque[LogEntry] = deque(maxlen=max_entries)

    def append(
        self,
        text: str,
        timestamp: Optional[datetime.datetime] = None,
    ) -> LogEntry:
        entry = LogEntry(timestamp or datetime.datetime.now(), text)
        self._entries.append(entry)
        return entry

    def snapshot(self) -> List[LogEntry]:
        """返回当前内容的浅拷贝，避免界面遍历时被后台线程修改。"""
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
