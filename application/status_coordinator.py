"""Luker 运行状态协调：就绪探测、三态计算与状态轮询。"""

import logging
from collections.abc import Callable
from typing import Protocol

from application.process_coordinator import ProcessCoordinator
from application.protocols import LogSink, UiPoster
from luker_launcher.services.readiness import LukerReadinessMonitor, LukerState

logger = logging.getLogger(__name__)

STATUS_POLL_INTERVAL = 2
STATUS_POLL_INTERVAL_MS = STATUS_POLL_INTERVAL * 1000
UI_KEY_LUKER_STATE = "luker_state"


class StatusConfig(Protocol):
    """状态协调需要的配置能力。"""

    def get_server_url(self) -> str: ...


class StatusCoordinator:
    """综合进程存活和本地服务探测结果，向界面通知三态。"""

    def __init__(
        self,
        *,
        process: ProcessCoordinator,
        config: StatusConfig,
        post_ui: UiPoster,
        log: LogSink,
        apply_state: Callable[[LukerState], None],
        update_tray_status: Callable[[bool], None],
        schedule: Callable[[int, Callable[[], None]], object],
        is_running: Callable[[], bool],
        readiness_factory: Callable[..., LukerReadinessMonitor] = LukerReadinessMonitor,
        poll_interval_ms: int = STATUS_POLL_INTERVAL_MS,
    ) -> None:
        self.process = process
        self.config = config
        self.post_ui = post_ui
        self.log = log
        self.apply = apply_state
        self.update_tray_status = update_tray_status
        self.schedule = schedule
        self.is_running = is_running
        self.readiness_factory = readiness_factory
        self.poll_interval_ms = poll_interval_ms
        self.last_state: LukerState | None = None
        self._readiness: LukerReadinessMonitor | None = None

    def start(self) -> None:
        self._readiness = self.readiness_factory(
            lambda: bool(self.process.manager and self.process.manager.is_running),
            self.config.get_server_url,
            self.on_luker_state_change,
        )
        self._readiness.start()

    def stop(self) -> None:
        readiness = self._readiness
        if readiness is not None:
            readiness.stop()

    def current_state(self) -> LukerState:
        """综合进程存活和本地服务探测结果，返回界面使用的三态。"""
        manager = self.process.manager
        if manager is None or not manager.is_running:
            return LukerState.STOPPED

        readiness = self._readiness
        if readiness is not None and readiness.state is LukerState.READY:
            return LukerState.READY
        return LukerState.STARTING

    def on_luker_state_change(self, _state: LukerState) -> None:
        """就绪探测线程回调；只唤醒主线程重新计算当前状态。

        回调携带的状态可能已在队列中过期，不能直接应用，否则旧的
        STARTING 会覆盖新的 READY。
        """
        self.post_ui.post(self.refresh, UI_KEY_LUKER_STATE)

    def refresh(self) -> None:
        self.apply_state(self.current_state())

    def apply_state(self, state: LukerState) -> None:
        if state is self.last_state:
            return
        self.last_state = state
        self.apply(state)

    def reset(self) -> None:
        """启动/重启前清空旧的就绪结果，避免沿用上一次的 READY。"""
        self.last_state = None
        readiness = self._readiness
        if readiness is not None:
            readiness.reset()

    def clear_last_state(self) -> None:
        """管理器切换后允许同一状态重新通知，但不中断当前就绪探测。"""
        self.last_state = None

    def update(self) -> None:
        manager = self.process.manager
        if manager is None:
            return
        self.update_tray_status(manager.is_running)
        self.apply_state(self.current_state())

    def schedule_poll(self) -> None:
        """在 Tk 主线程按固定间隔检查进程状态，不再单独占用监控线程。"""
        if not self.is_running():
            return

        try:
            self.update()
        except Exception:
            logger.exception("更新进程状态失败")
        finally:
            if self.is_running():
                self.schedule(self.poll_interval_ms, self.schedule_poll)
