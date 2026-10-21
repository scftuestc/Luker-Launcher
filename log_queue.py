"""线程安全的日志行队列。"""

from collections import deque
from threading import Lock


class BoundedLogQueue:
    """线程安全的日志行队列，同时限制行数和 UTF-8 字节数。"""

    def __init__(self, max_lines: int, max_bytes: int) -> None:
        self._items: deque[tuple[str, int]] = deque()
        self._bytes = 0
        self._max_lines = max_lines
        self._max_bytes = max_bytes
        self._lock = Lock()

    @staticmethod
    def _size(line: str) -> int:
        return len(line.encode("utf-8", errors="replace"))

    def put(self, line: str) -> None:
        size = self._size(line)
        with self._lock:
            self._items.append((line, size))
            self._bytes += size
            while self._items and (
                len(self._items) > self._max_lines or self._bytes > self._max_bytes
            ):
                _, removed_size = self._items.popleft()
                self._bytes -= removed_size

    def get_nowait(self) -> str | None:
        with self._lock:
            if not self._items:
                return None
            line, size = self._items.popleft()
            self._bytes -= size
            return line

    def empty(self) -> bool:
        with self._lock:
            return not self._items

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0
