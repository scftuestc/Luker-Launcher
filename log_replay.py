"""日志文本的分批重放调度。"""

from collections import deque
from collections.abc import Callable, Sequence

from log_store import MAX_LOG_ENTRIES, LogEntry

# 重放时每批插入的日志条数和让出主线程的间隔
REPLAY_BATCH_SIZE = 200
REPLAY_YIELD_MS = 1


class LogReplay:
    """维护重放快照、当前批次和重放期间到达的新日志。"""

    def __init__(
        self,
        schedule: Callable[[int, Callable[[], None]], str],
        cancel: Callable[[str], None],
        add_entries: Callable[[Sequence[LogEntry]], None],
        exists: Callable[[], bool],
        on_finished: Callable[[], None],
    ) -> None:
        self._schedule = schedule
        self._cancel = cancel
        self._add_entries = add_entries
        self._exists = exists
        self._on_finished = on_finished
        self.job: str | None = None
        self.active = False
        self.entries: list[LogEntry] = []
        self.index = 0
        self.tail: deque[LogEntry] = deque(maxlen=MAX_LOG_ENTRIES)

    def start(self, entries: Sequence[LogEntry]) -> None:
        """从快照开始重放。"""
        self.cancel()
        self.entries = list(entries)
        self.index = 0
        self.active = True
        self._schedule_chunk()

    def append(self, entry: LogEntry) -> None:
        """重放期间到达的当前源日志，等快照结束后再插入。"""
        self.tail.append(entry)

    def cancel(self) -> None:
        """取消进行中的重放并释放快照和 tail。"""
        if self.job is not None:
            self._cancel(self.job)
            self.job = None
        self.active = False
        self.entries = []
        self.index = 0
        self.tail.clear()

    def _schedule_chunk(self) -> None:
        self.job = self._schedule(REPLAY_YIELD_MS, self._chunk)

    def _chunk(self) -> None:
        """插入一批历史日志；快照处理完后继续处理重放期间的新日志。"""
        self.job = None
        if not self.active:
            return
        if not self._exists():
            self.cancel()
            return

        end = min(self.index + REPLAY_BATCH_SIZE, len(self.entries))
        if self.index < end:
            self._add_entries(self.entries[self.index : end])
            self.index = end

        if self.index < len(self.entries):
            self._schedule_chunk()
            return

        if self.tail:
            self.entries = list(self.tail)
            self.tail.clear()
            self.index = 0
            self._schedule_chunk()
            return

        self._finish()

    def _finish(self) -> None:
        self.active = False
        self.entries = []
        self.index = 0
        self._on_finished()
