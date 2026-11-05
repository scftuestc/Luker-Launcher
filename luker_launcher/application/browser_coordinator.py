"""浏览器打开协调：手动/自动打开、去重与等待服务就绪。"""

import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

from luker_launcher.application.lifecycle_state import LifecycleState
from luker_launcher.application.protocols import LogSink, UiPoster
from luker_launcher.application.task_runner import TaskRunner

logger = logging.getLogger(__name__)

BROWSER_WAIT_TIMEOUT_SECONDS = 30
BROWSER_WAIT_INTERVAL_SECONDS = 1


class BrowserConfig(Protocol):
    """浏览器协调需要的配置能力。"""

    use_pwa_mode: bool

    def get_server_url(self) -> str: ...


def is_server_ready(url: str, timeout: float = BROWSER_WAIT_INTERVAL_SECONDS) -> bool:
    """探测本地服务是否已经响应；4xx/5xx 也视为已就绪。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except urllib.error.HTTPError as error:
        error.close()
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


class BrowserCoordinator:
    """手动/自动打开浏览器，并保证同一时刻只启动一次。"""

    def __init__(
        self,
        *,
        config: BrowserConfig,
        task_runner: TaskRunner,
        post_ui: UiPoster,
        log: LogSink,
        open_browser: Callable[..., bool],
        lifecycle: LifecycleState,
        is_running: Callable[[], bool],
        probe: Callable[[str], bool] = is_server_ready,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        wait_timeout: float = BROWSER_WAIT_TIMEOUT_SECONDS,
        wait_interval: float = BROWSER_WAIT_INTERVAL_SECONDS,
    ) -> None:
        self.config = config
        self.task_runner = task_runner
        self.post_ui = post_ui
        self.log = log
        self.open_browser = open_browser
        self.lifecycle = lifecycle
        self.is_running = is_running
        self.probe = probe
        self.clock = clock
        self.sleep = sleep
        self.wait_timeout = wait_timeout
        self.wait_interval = wait_interval
        self._busy = False
        self._auto_pending = False

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def auto_pending(self) -> bool:
        return self._auto_pending

    def open(self, *, automatic: bool = False) -> None:
        """打开浏览器；自动打开只执行一次，手动打开会取消待执行的自动请求。"""
        if automatic:
            if not self._auto_pending:
                return
            self._auto_pending = False
        else:
            self._auto_pending = False

        if self.lifecycle.exiting or self._busy:
            return

        self._busy = True

        def worker() -> None:
            try:
                self._open_now()
            finally:
                if not self.post_ui.post_control(self._finish_open):
                    self._busy = False

        if not self.task_runner.run(worker):
            self._busy = False
            logger.error("启动浏览器打开线程失败")

    def _finish_open(self) -> None:
        self._busy = False

    def _open_now(self) -> None:
        self.open_browser(
            self.config.get_server_url(),
            prefer_pwa=self.config.use_pwa_mode,
        )

    def schedule_auto_open_if_needed(self) -> None:
        """PWA 模式下在后台等待服务就绪，然后自动打开浏览器。"""
        if self.config.use_pwa_mode:
            self._auto_pending = True
            self.schedule_auto_open()

    def schedule_auto_open(self) -> None:
        if not self.task_runner.run(self._wait_and_open):
            logger.error("启动自动打开浏览器线程失败")

    def _wait_and_open(self) -> None:
        url = self.config.get_server_url()
        deadline = self.clock() + self.wait_timeout

        while self.is_running() and self.clock() < deadline:
            if self.probe(url):
                self.log("[启动器] 检测到 Luker 已启动，正在打开沉浸应用窗口...")
                # 回到主线程复用 busy 标志，避免自动和手动同时打开
                self.post_ui.post(lambda: self.open(automatic=True))
                return
            self.sleep(self.wait_interval)

        if self.is_running():
            self._auto_pending = False
            self.log("[启动器] 等待 Luker 启动超时，请手动打开浏览器")
