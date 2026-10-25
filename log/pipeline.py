"""日志管线：线程安全队列、分批重放与双源控制器。"""

from collections import deque
from collections.abc import Callable, Sequence
from threading import Lock
from typing import Literal

from log.store import MAX_LOG_BYTES, MAX_LOG_ENTRIES, LogEntry, LogStore

# 每条队列每轮最多处理的日志行数
MAX_LOG_LINES_PER_CYCLE = 10
# 等待渲染的日志队列上限，超出条数或字节时丢弃最旧的行
MAX_LOG_QUEUE_SIZE = 5000
# 日志泵的轮询间隔（毫秒）
ACTIVE_POLL_MS = 10
VISIBLE_POLL_MS = 100
HIDDEN_POLL_MS = 500
# 重放时每批插入的日志条数和让出主线程的间隔
REPLAY_BATCH_SIZE = 200
REPLAY_YIELD_MS = 1


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


LogSource = Literal['luker', 'gcl']


class LogController:
    """维护日志存储、队列、当前源和重放状态，不直接操作 Tk 控件。"""

    def __init__(
        self,
        *,
        schedule: Callable[[int, Callable[[], None]], str],
        cancel: Callable[[str], None],
        exists: Callable[[], bool],
        viewable: Callable[[], bool],
        reset_display: Callable[[], None],
        add_entries: Callable[[Sequence[LogEntry]], int],
        adjust_search: Callable[[int], None],
        has_query: Callable[[], bool],
        on_search_rerun: Callable[[], None],
    ) -> None:
        self._schedule = schedule
        self._cancel = cancel
        self._exists = exists
        self._viewable = viewable
        self._reset_display = reset_display
        self._add_entries = add_entries
        self._adjust_search = adjust_search
        self._has_query = has_query
        self._on_search_rerun = on_search_rerun

        self._stores: dict[LogSource, LogStore] = {
            'luker': LogStore(),
            'gcl': LogStore(),
        }
        self._queues: dict[LogSource, BoundedLogQueue] = {
            'luker': BoundedLogQueue(MAX_LOG_QUEUE_SIZE, MAX_LOG_BYTES),
            'gcl': BoundedLogQueue(MAX_LOG_QUEUE_SIZE, MAX_LOG_BYTES),
        }
        self._source: LogSource = 'luker'
        # 屏幕文本是否已与当前 store 脱节，下次可见时需要整段重建
        self._needs_rebuild = False
        self._started = False
        self._pump_job: str | None = None
        self._replay = LogReplay(
            schedule=schedule,
            cancel=cancel,
            add_entries=self._insert_entries,
            exists=exists,
            on_finished=self._on_replay_finished,
        )

    @property
    def source(self) -> LogSource:
        return self._source

    @property
    def replaying(self) -> bool:
        return self._replay.active

    @property
    def needs_rebuild(self) -> bool:
        return self._needs_rebuild

    def start(self) -> None:
        """启动日志泵；重复调用不产生第二条轮询链。"""
        if self._started:
            return
        self._started = True
        self._pump()

    def stop(self) -> None:
        """停止日志泵并取消当前重放。"""
        self._started = False
        self._replay.cancel()
        if self._pump_job is not None:
            self._cancel(self._pump_job)
            self._pump_job = None

    def add_log(self, line: str) -> None:
        """把一行 Luker 日志放入队列。"""
        self._queues['luker'].put(line)

    def add_gcl_log(self, line: str) -> None:
        """把一行 GCL 日志放入队列。"""
        self._queues['gcl'].put(line)

    def drain_once(self) -> None:
        """执行一轮日志泵，但不续排；供测试和调试使用。"""
        if not self._exists():
            return
        if self._needs_rebuild and self._viewable():
            self.refresh()
        self._drain_queue('luker')
        self._drain_queue('gcl')

    def refresh(self) -> None:
        """清空当前显示，并按当前源的分批快照重建。"""
        self._replay.cancel()
        self._reset_display()
        self._needs_rebuild = False

        logs = self._stores[self._source].snapshot()
        if not logs:
            if self._has_query():
                self._on_search_rerun()
            return

        self._replay.start(logs)

    def clear(self) -> None:
        """清空两个日志源的历史、队列和当前显示。"""
        self._replay.cancel()
        self._reset_display()
        for store in self._stores.values():
            store.clear()
        for queue in self._queues.values():
            queue.clear()
        self._needs_rebuild = False

    def toggle_source(self) -> None:
        """在 Luker 和 GCL 日志之间切换并重建显示。"""
        self._source = 'gcl' if self._source == 'luker' else 'luker'
        self.refresh()

    def set_gcl_enabled(self, enabled: bool) -> None:
        """GCL 被禁用时，如果正在显示 GCL 日志就切回 Luker。"""
        if not enabled and self._source == 'gcl':
            self._source = 'luker'
            self.refresh()

    def on_show(self) -> None:
        """窗口显示时补上隐藏期间积压的日志。"""
        if self._needs_rebuild and not self._replay.active:
            self.refresh()

    def on_hide(self) -> None:
        """窗口隐藏时中断重放，下次显示再重建。"""
        if self._replay.active:
            self._needs_rebuild = True
        self._replay.cancel()

    def _pump(self) -> None:
        self._pump_job = None
        if not self._started or not self._exists():
            self._started = False
            return

        self.drain_once()
        if not self._started:
            return
        if not self._queues['luker'].empty() or not self._queues['gcl'].empty():
            delay = ACTIVE_POLL_MS
        else:
            # 隐藏到托盘时降低轮询频率
            delay = VISIBLE_POLL_MS if self._viewable() else HIDDEN_POLL_MS
        self._pump_job = self._schedule(delay, self._pump)

    def _drain_queue(self, source: LogSource) -> None:
        """从指定源取一批日志写入存储；仅当前源且可见时渲染。"""
        log_queue = self._queues[source]
        log_store = self._stores[source]
        entries = []
        for _ in range(MAX_LOG_LINES_PER_CYCLE):
            line = log_queue.get_nowait()
            if line is None:
                break

            entry = log_store.append(line)
            if self._source == source:
                if self._replay.active:
                    # 重放的是开始时的快照，新日志留到快照结束后再插入
                    self._replay.append(entry)
                else:
                    entries.append(entry)

        if not entries:
            return

        if self._viewable():
            self._insert_entries(entries)
        else:
            # 隐藏时只存不渲染，显示时分批补上
            self._needs_rebuild = True

    def _insert_entries(self, entries: Sequence[LogEntry]) -> None:
        removed_lines = self._add_entries(entries)
        if removed_lines:
            self._adjust_search(removed_lines)

    def _on_replay_finished(self) -> None:
        self._needs_rebuild = False
        if self._has_query():
            self._on_search_rerun()
