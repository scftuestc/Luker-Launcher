"""Luker 进程管理协调：启动、停止、重启、路径切换与忙碌标志。"""

import logging
from collections.abc import Callable
from typing import Protocol

from application.lifecycle_state import LifecycleState
from application.protocols import LogSink, UiPoster
from application.task_runner import TaskRunner
from luker_launcher.process.managers import LukerProcessManager
from luker_launcher.services.version import same_path

logger = logging.getLogger(__name__)


class ProcessConfig(Protocol):
    """进程协调需要的配置能力。"""

    @property
    def luker_path(self) -> str | None: ...

    @property
    def use_pwa_mode(self) -> bool: ...

    def get_server_port(self) -> int: ...


class ProcessCoordinator:
    """持有当前 Luker 进程管理器，并串行化启停操作。"""

    def __init__(
        self,
        *,
        config: ProcessConfig,
        task_runner: TaskRunner,
        post_ui: UiPoster,
        log: LogSink,
        lifecycle: LifecycleState,
        manager_factory: Callable[..., LukerProcessManager] = LukerProcessManager,
        on_status_reset: Callable[[], None] | None = None,
        on_manager_replaced: Callable[[], None] | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self.task_runner = task_runner
        self.post_ui = post_ui
        self.log = log
        self.lifecycle = lifecycle
        self.manager_factory = manager_factory
        self.on_status_reset = on_status_reset or (lambda: None)
        self.on_manager_replaced = on_manager_replaced or (lambda: None)
        self.on_finished = on_finished or (lambda: None)
        self.manager: LukerProcessManager | None = None
        self.busy = False

    def ensure_manager(self) -> LukerProcessManager | None:
        """确保进程管理器与当前配置的 Luker 路径保持一致。"""
        path = self.config.luker_path
        if not path:
            return None

        manager = self.manager
        if manager is None or not same_path(str(manager.luker_path), path):
            if manager is not None and manager.is_running:
                # 运行中不热切换，避免意外中断正在工作的进程
                return manager

            manager = self._create_manager(path)
            self.manager = manager
            self.on_manager_replaced()
        else:
            manager.let_luker_open_browser = not self.config.use_pwa_mode
            manager.server_port = self.config.get_server_port()

        return manager

    def _create_manager(self, path: str) -> LukerProcessManager:
        manager = self.manager_factory(
            path,
            let_luker_open_browser=not self.config.use_pwa_mode,
            server_port=self.config.get_server_port(),
        )
        manager.add_log_callback(self.log)
        return manager

    def start(self) -> None:
        if self.busy or self.lifecycle.exiting:
            return
        self.on_status_reset()
        self.run_action(lambda manager: manager.start())

    def stop(self) -> None:
        self.run_action(lambda manager: manager.stop())

    def restart(self) -> None:
        if self.busy or self.lifecycle.exiting:
            return

        self.on_status_reset()
        desired_path = self.config.luker_path
        current = self.manager
        if desired_path and current and not same_path(str(current.luker_path), desired_path):
            self._restart_with_path(desired_path)
            return

        self.run_action(lambda manager: manager.restart())

    def _restart_with_path(self, path: str) -> None:
        """路径变化时先停旧进程，再创建并启动新管理器。"""
        self.on_status_reset()
        old_manager = self.manager

        def worker() -> None:
            try:
                if old_manager is not None and not old_manager.stop():
                    self.log("[错误] 旧 Luker 进程未停止，已取消切换路径")
                    return
                if self.lifecycle.exiting:
                    return

                manager = self._create_manager(path)
                self.post_ui.post_control(lambda: self.adopt_manager(manager))
                # 先切换 UI 持有的管理器，再启动；退出过程中不再拉起新进程
                if not self.lifecycle.exiting:
                    manager.start()
                    if self.lifecycle.exiting and manager.is_running:
                        manager.stop()
            except Exception:
                logger.exception("切换 Luker 路径失败")
                self.log("[错误] 切换 Luker 路径失败，请查看日志")
            finally:
                if not self.post_ui.post_control(self.finish_action):
                    self.busy = False

        self.start_worker(worker, context="路径切换")

    def adopt_manager(self, manager: LukerProcessManager) -> None:
        if self.lifecycle.exiting:
            # 退出已开始，拒绝接管；新实例交给后台线程停止
            logger.debug("退出中，拒绝接管新的进程管理器")

            def stop_incoming() -> None:
                manager.stop()

            if not self.task_runner.run(stop_incoming):
                logger.error("停止退出期间创建的进程管理器失败")
            return

        self.manager = manager
        self.on_manager_replaced()

    def run_action(self, action: Callable[[LukerProcessManager], object]) -> None:
        """在后台线程执行进程操作，避免停止/重启时阻塞界面。"""
        if self.busy or self.lifecycle.exiting:
            return

        manager = self.ensure_manager()
        if manager is None:
            self.log("[错误] 未配置 Luker 路径")
            return

        def worker() -> None:
            try:
                action(manager)
            except Exception:
                logger.exception("执行进程操作失败")
                self.log("[错误] 进程操作失败，请查看日志")
            finally:
                if not self.post_ui.post_control(self.finish_action):
                    # UI 泵已停止（通常正在退出），没有主线程来复位忙碌标志
                    self.busy = False

        self.start_worker(worker)

    def start_worker(
        self,
        worker: Callable[[], None],
        *,
        on_failure: Callable[[], None] | None = None,
        context: str = "进程操作",
    ) -> bool:
        """启动一次进程操作；线程创建失败时复位 busy 并执行 on_failure。"""
        self.busy = True
        if not self.task_runner.run(worker):
            self.busy = False
            logger.error("%s线程启动失败", context)
            if on_failure is not None:
                on_failure()
            return False
        return True

    def finish_action(self) -> None:
        """结束一次进程操作：复位 busy 并刷新状态。"""
        self.busy = False
        self.on_finished()

    def stop_all(self) -> None:
        """停止当前所有管理器，并覆盖退出期间新接管的实例。"""
        seen: set[int] = set()
        for _ in range(3):
            manager = self.manager
            if manager is None:
                return
            if id(manager) in seen:
                return
            seen.add(id(manager))
            try:
                manager.stop()
            except Exception:
                logger.exception("停止进程失败")
