"""关闭窗口、退出流程与幂等清理。"""

import logging
from collections.abc import Callable
from tkinter import messagebox
from typing import Any, Protocol

from application.lifecycle_state import LifecycleState
from application.process_coordinator import ProcessCoordinator
from application.protocols import LogSink, UiPoster
from application.status_coordinator import StatusCoordinator
from application.task_runner import TaskRunner
from dialogs import show_close_choice
from luker_launcher.services.readiness import LukerState
from ui.dispatch import UiDispatcher

logger = logging.getLogger(__name__)


class LifecycleWindow(Protocol):
    def hide(self) -> None: ...

    def focus_force(self) -> None: ...

    def quit(self) -> None: ...


class LifecycleTray(Protocol):
    def stop(self) -> None: ...


class LifecycleConfig(Protocol):
    @property
    def close_behavior(self) -> str: ...

    @close_behavior.setter
    def close_behavior(self, value: str) -> None: ...


class LifecycleCoordinator:
    """按配置隐藏、退出或询问，并统一执行幂等清理。"""

    def __init__(
        self,
        *,
        config: LifecycleConfig,
        process: ProcessCoordinator,
        status: StatusCoordinator,
        ui: UiDispatcher,
        task_runner: TaskRunner,
        post_ui: UiPoster,
        log: LogSink,
        lifecycle: LifecycleState,
        window_provider: Callable[[], LifecycleWindow | None],
        tray_icon_provider: Callable[[], LifecycleTray | None],
        tray_ready: Callable[[], bool],
        hide_window: Callable[[], None],
        current_state: Callable[[], LukerState],
        is_updating: Callable[[], bool],
        set_running: Callable[[bool], None],
        close_dialog: Callable[..., None] = show_close_choice,
        messagebox_api: Any = messagebox,
        exit_key: str = "exit",
    ) -> None:
        self.config = config
        self.process = process
        self.status = status
        self.ui = ui
        self.task_runner = task_runner
        self.post_ui = post_ui
        self.log = log
        self.lifecycle = lifecycle
        self.window_provider = window_provider
        self.tray_icon_provider = tray_icon_provider
        self.tray_ready = tray_ready
        self.hide_window = hide_window
        self.current_state = current_state
        self.is_updating = is_updating
        self.set_running = set_running
        self.close_dialog = close_dialog
        self.messagebox_api = messagebox_api
        self.exit_key = exit_key
        self._exit_dialog_open = False
        self._shutdown_done = False

    @property
    def exit_dialog_open(self) -> bool:
        return self._exit_dialog_open

    def request_exit(self) -> None:
        """日志窗口关闭按钮：按配置隐藏到托盘、退出或询问。"""
        if self.is_updating():
            self.log("[警告] 正在更新 Luker，请等待完成后再退出")
            return

        window = self.window_provider()
        if self.lifecycle.exiting or self._exit_dialog_open or window is None:
            return

        behavior = self.config.close_behavior
        allow_hide = self.tray_ready() and self.tray_icon_provider() is not None

        if behavior == "exit":
            window.hide()
            self.exit()
            return

        if behavior == "tray" and allow_hide:
            self.hide_window()
            return

        self._exit_dialog_open = True
        state = self.current_state()

        def on_hide(remember: bool) -> None:
            self._exit_dialog_open = False
            if remember:
                self.config.close_behavior = "tray"
            self.hide_window()

        def on_exit(remember: bool) -> None:
            self._exit_dialog_open = False
            if remember:
                self.config.close_behavior = "exit"
            current = self.window_provider()
            if current is not None:
                current.hide()
            self.exit()

        def on_cancel() -> None:
            self._exit_dialog_open = False
            current = self.window_provider()
            if current is not None:
                current.focus_force()

        try:
            self.close_dialog(
                window,
                state,
                allow_hide=allow_hide,
                on_hide=on_hide,
                on_exit=on_exit,
                on_cancel=on_cancel,
            )
        except Exception:
            logger.exception("显示关闭窗口选择框失败，回退到系统对话框")
            self._exit_dialog_open = False
            try:
                if allow_hide:
                    answer = self.messagebox_api.askyesnocancel(
                        "关闭窗口",
                        "要隐藏到系统托盘吗？\n选择“否”将退出 Luker Launcher，选择“取消”返回。",
                        parent=window,
                    )
                    if answer is None:
                        on_cancel()
                    elif answer:
                        on_hide(False)
                    else:
                        on_exit(False)
                else:
                    confirmed = self.messagebox_api.askyesno(
                        "关闭窗口",
                        "系统托盘不可用，关闭窗口将退出 Luker Launcher。\n确定要退出吗？",
                        parent=window,
                    )
                    if confirmed:
                        on_exit(False)
                    else:
                        on_cancel()
            except Exception:
                logger.exception("显示系统关闭窗口对话框失败")

    def exit(self) -> None:
        if self.is_updating():
            self.log("[警告] 正在更新 Luker，请等待完成后再退出")
            return
        if self.lifecycle.exiting:
            return
        self.lifecycle.exiting = True
        self.set_running(False)

        # 停止进程可能耗时数秒，放到后台，完成后再结束主循环
        def worker() -> None:
            self.status.stop()
            self.process.stop_all()
            self.post_ui.post(self.finish_exit, self.exit_key)

        if not self.task_runner.run(worker):
            logger.error("启动退出线程失败")
            self.finish_exit()

    def finish_exit(self) -> None:
        """停止托盘并结束 Tk 主循环。"""
        try:
            self.shutdown()
        finally:
            window = self.window_provider()
            if window is not None:
                window.quit()

    def shutdown(self) -> None:
        """幂等清理：正常退出和 mainloop 返回后的兜底共用同一套逻辑。"""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.set_running(False)

        self.status.stop()
        self.ui.stop()
        tray = self.tray_icon_provider()
        if tray is not None:
            tray.stop()
