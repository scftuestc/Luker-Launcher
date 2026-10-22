"""日志管线控制器：双队列排水、日志源切换、显示刷新与分批重放。"""

from collections.abc import Callable, Sequence
from typing import Literal

from log_queue import BoundedLogQueue
from log_replay import LogReplay
from log_store import MAX_LOG_BYTES, LogEntry, LogStore

LogSource = Literal['luker', 'gcl']

# 每条队列每轮最多处理的日志行数
MAX_LOG_LINES_PER_CYCLE = 10
# 等待渲染的日志队列上限，超出条数或字节时丢弃最旧的行
MAX_LOG_QUEUE_SIZE = 5000
# 日志泵的轮询间隔（毫秒）
ACTIVE_POLL_MS = 10
VISIBLE_POLL_MS = 100
HIDDEN_POLL_MS = 500


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
