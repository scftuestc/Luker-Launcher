"""主线程 UI 操作投递：有界队列、同键合并和定时泵。"""

import contextlib
import logging
import queue
from collections import deque
from collections.abc import Callable
from threading import Lock

logger = logging.getLogger(__name__)

# 后台线程投递的 UI 操作由主线程按此间隔取走
UI_QUEUE_POLL_MS = 50
# 普通 UI 事件上限；幂等的界面请求走合并槽，不占这里的容量
UI_QUEUE_MAXSIZE = 256
# 每次泵最多执行的普通事件数，避免突发回调长时间占用 Tk 线程
UI_EVENTS_PER_TICK = 32


class UiDispatcher:
    """从任意线程接收 UI 回调，在主线程按帧执行。"""

    def __init__(
        self,
        schedule: Callable[[int, Callable[[], None]], object],
        *,
        poll_ms: int = UI_QUEUE_POLL_MS,
        maxsize: int = UI_QUEUE_MAXSIZE,
        events_per_tick: int = UI_EVENTS_PER_TICK,
    ) -> None:
        self._schedule = schedule
        self._poll_ms = poll_ms
        self._events_per_tick = events_per_tick
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue(maxsize=maxsize)
        self._state: dict[str, Callable[[], None]] = {}
        # 生命周期完成回调单独排队，不参与普通事件的满时丢弃
        self._control: deque[Callable[[], None]] = deque()
        self._lock = Lock()
        self._active = False
        self._stopped = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        """激活队列并立即开始泵；重复调用或停止后调用都不再生效。"""
        with self._lock:
            if self._active or self._stopped:
                return
            self._active = True
        self.pump()

    def stop(self) -> None:
        """停止派发并丢弃未执行的回调；停止后不可重新启动。"""
        with self._lock:
            if self._stopped:
                return
            self._active = False
            self._stopped = True
            self._state.clear()
            self._control.clear()
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

    def post(self, callback: Callable[[], None], coalesce_key: str | None = None) -> bool:
        """从任意线程投递 UI 操作；返回是否被接受。

        UI 泵未激活或已经停止时返回 False，调用方可以据此复位忙碌标志。
        """
        with self._lock:
            if not self._active:
                return False

            if coalesce_key is not None:
                self._state[coalesce_key] = callback
                return True

            try:
                self._queue.put_nowait(callback)
            except queue.Full:
                logger.warning("UI 事件队列已满，丢弃最旧事件")
                with contextlib.suppress(queue.Empty):
                    self._queue.get_nowait()
                try:
                    self._queue.put_nowait(callback)
                except queue.Full:
                    logger.warning("UI 事件队列已满，新事件也被丢弃")
                    return False
            return True

    def post_control(self, callback: Callable[[], None]) -> bool:
        """投递必须执行的生命周期完成回调；不参与普通队列的容量限制。"""
        with self._lock:
            if not self._active:
                return False
            self._control.append(callback)
            return True

    def pump(self) -> None:
        """在主线程执行合并后的界面状态和有界事件队列。"""
        if not self._active:
            return

        try:
            with self._lock:
                pending_control = list(self._control)
                self._control.clear()
                pending_state = list(self._state.values())
                self._state.clear()

            for callback in pending_control:
                if not self._active:
                    return
                self._run(callback)

            for callback in pending_state:
                if not self._active:
                    return
                self._run(callback)

            processed = 0
            while self._active and processed < self._events_per_tick:
                try:
                    callback = self._queue.get_nowait()
                except queue.Empty:
                    break
                self._run(callback)
                processed += 1
        finally:
            if self._active:
                # 还有积压时快速续跑，空闲时恢复轮询间隔
                delay = 1 if self._has_pending_work() else self._poll_ms
                self._schedule(delay, self.pump)

    def _has_pending_work(self) -> bool:
        with self._lock:
            return bool(self._control or self._state) or not self._queue.empty()

    @staticmethod
    def _run(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            logger.exception("界面操作执行失败")
