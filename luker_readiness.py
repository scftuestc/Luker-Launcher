"""Luker 进程与本地服务的就绪状态探测。"""

import http.client
import logging
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from enum import Enum

logger = logging.getLogger(__name__)


class LukerState(Enum):
    """界面使用的 Luker 运行状态。"""

    STOPPED = 'stopped'
    STARTING = 'starting'
    READY = 'ready'


class LukerReadinessMonitor:
    """在后台探测 Luker 本地服务，就绪后通知界面。

    进程存活只是启动条件；本地服务连续 required_successes 次响应后才算
    READY。进入 READY 后保持到进程退出，避免网络抖动导致呼吸灯反复闪烁。
    """

    def __init__(
        self,
        is_running: Callable[[], bool],
        get_url: Callable[[], str],
        on_change: Callable[[LukerState], None],
        *,
        interval: float = 1.0,
        timeout: float = 1.0,
        required_successes: int = 2,
    ) -> None:
        self._is_running = is_running
        self._get_url = get_url
        self._on_change = on_change
        self._interval = max(0.01, interval)
        self._timeout = max(0.05, timeout)
        self._required_successes = max(1, required_successes)
        self._state = LukerState.STOPPED
        self._successes = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def state(self) -> LukerState:
        with self._lock:
            return self._state

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="LukerReadiness",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        self._thread = None

    def reset(self) -> None:
        """进程启动/重启时清空就绪进度，立即回到启动中/已停止。"""
        state = LukerState.STARTING if self._read_running() else LukerState.STOPPED
        self._transition(state, reset_successes=True)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self._read_running():
                self._transition(LukerState.STOPPED, reset_successes=True)
                self._stop_event.wait(self._interval)
                continue

            with self._lock:
                is_ready = self._state is LukerState.READY
            if is_ready:
                # 已经就绪后不再持续请求；进程退出时上面的分支会复位
                self._stop_event.wait(self._interval)
                continue

            self._transition(LukerState.STARTING)
            if self._probe():
                with self._lock:
                    self._successes += 1
                    ready = self._successes >= self._required_successes
                if ready:
                    self._transition(LukerState.READY)
            else:
                with self._lock:
                    self._successes = 0
            self._stop_event.wait(self._interval)

    def _read_running(self) -> bool:
        try:
            return bool(self._is_running())
        except Exception:
            logger.exception("读取 Luker 进程状态失败")
            return False

    def _probe(self) -> bool:
        try:
            with urllib.request.urlopen(self._get_url(), timeout=self._timeout):
                return True
        except urllib.error.HTTPError as error:
            # 4xx/5xx 也说明本地服务已经在监听
            error.close()
            return True
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
            ValueError,
        ):
            return False

    def _transition(self, state: LukerState, *, reset_successes: bool = False) -> None:
        with self._lock:
            if reset_successes:
                self._successes = 0
            changed = self._state is not state
            self._state = state
        if not changed:
            return
        try:
            self._on_change(state)
        except Exception:
            logger.exception("Luker 就绪状态回调失败")
