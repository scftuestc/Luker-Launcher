"""启动器应用主体：协调日志窗口、托盘、进程与退出流程。"""

import logging
import tkinter as tk
from collections.abc import Callable
from threading import Thread
from tkinter import messagebox

import logging_setup
import win32_api
from application.browser_coordinator import BrowserCoordinator
from application.lifecycle_state import LifecycleState
from application.process_coordinator import ProcessCoordinator
from application.status_coordinator import StatusCoordinator
from application.task_runner import TaskRunner
from application.update_coordinator import UpdateCoordinator
from config import config
from core.browser import open_in_browser
from core.readiness import LukerState
from core.version import (
    UpdateProgress,
    UpdateTarget,
    VersionCheck,
    apply_luker_update,
    read_local_version,
    same_path,
)
from dialogs import ensure_luker_path_configured, show_close_choice
from log_window import LogWindow
from process.managers import LukerProcessManager
from settings_window import SettingsWindow
from tray.icon import TrayIcon
from tray.menu import TrayMenu
from ui.dispatch import UiDispatcher

logger = logging.getLogger(__name__)

# 合并键：同一键只保留最后一次请求
UI_KEY_VISIBILITY = "visibility"
UI_KEY_TRAY_MENU = "tray_menu"
UI_KEY_SETTINGS = "settings"
UI_KEY_EXIT = "exit"


class LukerLauncher:
    """协调日志窗口、托盘菜单和 Luker 进程管理器的应用主体。"""

    def __init__(self) -> None:
        self.tray_icon: TrayIcon | None = None
        self.log_window: LogWindow | None = None
        self.tray_menu: TrayMenu | None = None
        self._running = False
        self._exiting = False  # 退出流程只执行一次
        self._exit_dialog_open = False
        self._tray_ready = False
        self._shutdown_done = False
        # 托盘/进程线程不能直接操作 Tk，统一投递到这里由主线程执行
        self._ui = UiDispatcher(self._schedule_ui)
        self._lifecycle = LifecycleState()
        self._task_runner = TaskRunner()
        self._process = ProcessCoordinator(
            config=config,
            task_runner=self._task_runner,
            post_ui=self._ui,
            log=self._on_log,
            lifecycle=self._lifecycle,
            on_status_reset=self._reset_luker_readiness,
            on_manager_replaced=self._clear_last_status,
            on_finished=self._update_status,
        )
        self._status = StatusCoordinator(
            process=self._process,
            config=config,
            post_ui=self._ui,
            log=self._on_log,
            apply_state=self._apply_luker_state,
            update_tray_status=self._update_tray_status,
            schedule=self._schedule_ui,
            is_running=lambda: self._running,
        )
        self._browser = BrowserCoordinator(
            config=config,
            task_runner=self._task_runner,
            post_ui=self._ui,
            log=self._on_log,
            open_browser=open_in_browser,
            lifecycle=self._lifecycle,
            is_running=lambda: self._running,
        )
        self._update = UpdateCoordinator(
            config=config,
            process=self._process,
            status=self._status,
            task_runner=self._task_runner,
            post_ui=self._ui,
            log=self._on_log,
            lifecycle=self._lifecycle,
            settings_provider=lambda: self.settings_window,
        )
        # 最近一次托盘点击位置，用于把设置窗口放到点击所在显示器
        self._tray_anchor: tuple[int, int] | None = None
        self.settings_window: SettingsWindow | None = None

    @property
    def process_manager(self) -> LukerProcessManager | None:
        return self._process.manager

    @process_manager.setter
    def process_manager(self, manager: LukerProcessManager | None) -> None:
        self._process.manager = manager

    @property
    def _process_busy(self) -> bool:
        return self._process.busy

    @_process_busy.setter
    def _process_busy(self, value: bool) -> None:
        self._process.busy = value

    @property
    def _version_checking(self) -> bool:
        return self._update.checking

    @_version_checking.setter
    def _version_checking(self, value: bool) -> None:
        self._update.checking = value

    @property
    def _version_check_cache(self) -> VersionCheck | None:
        return self._update.version_check_cache

    @_version_check_cache.setter
    def _version_check_cache(self, value: VersionCheck | None) -> None:
        self._update.version_check_cache = value

    @property
    def _version_check_seq(self) -> int:
        return self._update.version_check_seq

    @_version_check_seq.setter
    def _version_check_seq(self, value: int) -> None:
        self._update.version_check_seq = value

    @property
    def _updating(self) -> bool:
        return self._update.updating

    @_updating.setter
    def _updating(self, value: bool) -> None:
        self._update.updating = value

    def _schedule_ui(self, delay_ms: int, callback: Callable[[], None]) -> None:
        """在 Tk 主线程安排下一次 UI 泵；窗口不可用时停止续排。"""
        window = self.log_window
        if window is None:
            return
        try:
            if window.winfo_exists():
                window.after(delay_ms, callback)
        except tk.TclError:
            logger.debug("窗口已销毁，停止界面事件泵")

    def _post_ui(
        self,
        callback: Callable[[], None],
        coalesce_key: str | None = None,
        *,
        control: bool = False,
    ) -> bool:
        """从任意线程投递 UI 操作；返回是否被当前 UI 泵接受。

        ``control=True`` 用于进程/浏览器完成等必须执行的生命周期回调，
        这些回调不进入普通 UI 队列，不会被队列满时的丢弃策略挤掉。
        """
        if control:
            return self._ui.post_control(callback)
        return self._ui.post(callback, coalesce_key)

    def _current_luker_state(self) -> LukerState:
        return self._status.current_state()

    def _apply_luker_state(self, state: LukerState) -> None:
        window = self.log_window
        if window is not None:
            window.update_status(state)
        menu = self.tray_menu
        if menu is not None:
            menu.set_luker_state(state)

    def _update_tray_status(self, is_running: bool) -> None:
        if self.tray_icon:
            self.tray_icon.update_status(is_running)

    def _reset_luker_readiness(self) -> None:
        self._status.reset()

    def _on_show_window(self) -> None:
        self._post_ui(self._show_window, UI_KEY_VISIBILITY)

    def _show_window(self) -> None:
        if self.log_window:
            self.log_window.show()
        if self.tray_icon:
            self.tray_icon.set_window_visible(True)

    def _on_hide_window(self) -> None:
        self._post_ui(self._hide_window, UI_KEY_VISIBILITY)

    def _hide_window(self) -> None:
        if self.log_window:
            self.log_window.hide()
        if self.tray_icon:
            self.tray_icon.set_window_visible(False)

    def _on_log(self, line: str) -> None:
        if self.log_window:
            self.log_window.add_log(line)

    def _on_start(self) -> None:
        self._process.start()

    def _on_stop(self) -> None:
        self._process.stop()

    def _on_restart(self) -> None:
        self._process.restart()

    def _clear_last_status(self) -> None:
        self._status.clear_last_state()

    def _on_request_exit(self) -> None:
        """日志窗口关闭按钮：按配置隐藏到托盘、退出或询问。"""
        if getattr(self, '_updating', False):
            self._on_log("[警告] 正在更新 Luker，请等待完成后再退出")
            return
        if self._exiting or self._exit_dialog_open or not self.log_window:
            return

        behavior = config.close_behavior
        allow_hide = self._tray_ready and self.tray_icon is not None

        if behavior == 'exit':
            self.log_window.hide()
            self._on_exit()
            return

        if behavior == 'tray' and allow_hide:
            self._hide_window()
            return

        self._exit_dialog_open = True
        state = self._current_luker_state()

        def on_hide(remember: bool) -> None:
            self._exit_dialog_open = False
            if remember:
                config.close_behavior = 'tray'
            self._hide_window()

        def on_exit(remember: bool) -> None:
            self._exit_dialog_open = False
            if remember:
                config.close_behavior = 'exit'
            if self.log_window:
                self.log_window.hide()
            self._on_exit()

        def on_cancel() -> None:
            self._exit_dialog_open = False
            if self.log_window:
                self.log_window.focus_force()

        try:
            show_close_choice(
                self.log_window,
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
                    answer = messagebox.askyesnocancel(
                        "关闭窗口",
                        "要隐藏到系统托盘吗？\n选择“否”将退出 Luker Launcher，选择“取消”返回。",
                        parent=self.log_window,
                    )
                    if answer is None:
                        on_cancel()
                    elif answer:
                        on_hide(False)
                    else:
                        on_exit(False)
                else:
                    confirmed = messagebox.askyesno(
                        "关闭窗口",
                        "系统托盘不可用，关闭窗口将退出 Luker Launcher。\n确定要退出吗？",
                        parent=self.log_window,
                    )
                    if confirmed:
                        on_exit(False)
                    else:
                        on_cancel()
            except Exception:
                logger.exception("显示系统关闭窗口对话框失败")

    def _on_exit(self) -> None:
        if getattr(self, '_updating', False):
            self._on_log("[警告] 正在更新 Luker，请等待完成后再退出")
            return
        if self._exiting:
            return
        self._exiting = True
        self._lifecycle.exiting = True
        self._running = False

        # 停止进程可能耗时数秒，放到后台，完成后再结束主循环
        def worker() -> None:
            self._status.stop()
            self._process.stop_all()
            self._post_ui(self._finish_exit, UI_KEY_EXIT)

        try:
            self._run_async(worker)
        except Exception:
            logger.exception("启动退出线程失败")
            self._finish_exit()

    def _finish_exit(self) -> None:
        """停止托盘并结束 Tk 主循环。"""
        try:
            self._shutdown()
        finally:
            if self.log_window:
                self.log_window.quit()

    def _shutdown(self) -> None:
        """幂等清理：正常退出和 mainloop 返回后的兜底共用同一套逻辑。"""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._running = False

        self._status.stop()
        self._ui.stop()
        if self.tray_icon:
            self.tray_icon.stop()

    def _run_async(self, func: Callable[[], None]) -> None:
        """在守护线程中执行耗时操作，不阻塞 Tk 主循环。"""
        Thread(target=func, daemon=True).start()

    def _start_process_worker(
        self,
        worker: Callable[[], None],
        *,
        on_failure: Callable[[], None] | None = None,
        context: str = "进程操作",
    ) -> bool:
        return self._process.start_worker(worker, on_failure=on_failure, context=context)

    def _ensure_process_manager(self) -> LukerProcessManager | None:
        return self._process.ensure_manager()

    def _finish_process_action(self) -> None:
        self._process.finish_action()

    def _on_settings(self) -> None:
        if self._exiting:
            return
        self._post_ui(self._open_settings_window, UI_KEY_SETTINGS)

    def _on_open_browser(self, *, automatic: bool = False) -> None:
        """打开浏览器；具体去重与等待逻辑由 BrowserCoordinator 负责。"""
        self._browser.open(automatic=automatic)

    def _open_settings_window(self) -> None:
        """打开或聚焦设置窗口；已打开时只置前，不移动。"""
        if self._exiting or not self.log_window:
            return

        window = self.settings_window
        if window is not None and window.is_alive():
            window.focus_force()
            return

        cached = self._version_check_cache
        current_path = config.luker_path
        if cached is not None and (
            not current_path or not same_path(cached.repo_path, current_path)
        ):
            self._version_check_cache = None
            cached = None

        self.settings_window = SettingsWindow(
            self.log_window,
            anchor_point=self._tray_anchor,
            on_close=self._on_settings_closed,
            on_check_luker_update=self._request_luker_version_check,
            on_apply_luker_update=self._apply_luker_update,
            on_luker_path_changed=self._on_luker_path_changed,
            initial_version_check=cached,
            initial_version_checking=self._version_checking,
        )
        self.settings_window.focus_force()

    def _on_settings_closed(self) -> None:
        """设置窗口销毁后清理引用。"""
        self.settings_window = None

    def _on_luker_path_changed(self) -> None:
        self._update.path_changed()

    def _request_luker_version_check(self) -> bool:
        return self._update.request_check()

    def _post_update_progress(
        self,
        window: SettingsWindow,
        progress: UpdateProgress,
        *,
        control: bool = False,
    ) -> None:
        # 更新阶段数量很少，统一走 control 队列：
        # 普通合并队列会在最终结果之后才执行旧的阶段回调，覆盖完成状态。
        self._post_ui(
            lambda: self._deliver_update_progress(window, progress),
            control=True,
        )

    def _deliver_update_progress(
        self,
        window: SettingsWindow,
        progress: UpdateProgress,
    ) -> None:
        if self.settings_window is window and window.is_alive():
            window.set_update_progress(progress)

    @staticmethod
    def _start_luker_safely(manager: LukerProcessManager) -> str | None:
        """启动 Luker；返回 None 表示成功，否则返回可展示的失败原因。"""
        try:
            return None if manager.start() else "启动失败"
        except Exception as error:
            logger.exception("更新后启动 Luker 失败")
            return f"启动异常：{error}"

    def _apply_luker_update(self, target: UpdateTarget) -> bool:
        """停止 Luker、切换版本、安装依赖并按原状态重启。"""
        if self._updating or self._process_busy or self._version_checking or self._exiting:
            return False
        window = self.settings_window
        if window is None:
            return False

        manager = self._ensure_process_manager()
        if manager is None:
            self._post_update_progress(
                window,
                UpdateProgress("error", "未配置 Luker 路径", "error", False),
                control=True,
            )
            return False

        configured_path = config.luker_path
        if (
            manager.is_running
            and configured_path
            and not same_path(str(manager.luker_path), configured_path)
        ):
            self._post_update_progress(
                window,
                UpdateProgress(
                    "error",
                    "Luker 路径已更改，请先重启应用新路径",
                    "warning",
                    False,
                ),
                control=True,
            )
            return False

        active_manager = manager
        was_running = manager.is_running
        self._updating = True
        self._version_check_cache = None
        self._version_check_seq += 1

        def worker() -> None:
            try:
                self._post_update_progress(
                    window,
                    UpdateProgress("checking", "正在检查更新条件...", "info", True),
                )
                local = read_local_version(str(active_manager.luker_path))
                if local.error:
                    message = local.error
                    self._on_log(f"[错误] {message}")
                    self._post_update_progress(
                        window,
                        UpdateProgress("error", message, "error", False),
                        control=True,
                    )
                    return
                if not local.npm_available:
                    message = "未找到 npm，无法安装依赖"
                    self._on_log(f"[错误] {message}")
                    self._post_update_progress(
                        window,
                        UpdateProgress("error", message, "error", False),
                        control=True,
                    )
                    return
                if local.dirty:
                    message = "检测到未提交的修改，已取消更新"
                    self._on_log(f"[警告] {message}")
                    self._post_update_progress(
                        window,
                        UpdateProgress("error", message, "warning", False),
                        control=True,
                    )
                    return

                if was_running:
                    self._on_log("[启动器] 正在停止 Luker 以更新版本...")
                    self._post_update_progress(
                        window,
                        UpdateProgress("stopping", "正在停止 Luker...", "info", True),
                    )
                    self._reset_luker_readiness()
                    if not active_manager.stop():
                        message = "Luker 未能完全停止，已取消更新"
                        self._on_log(f"[错误] {message}")
                        self._post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                            control=True,
                        )
                        return

                def on_stage(stage: str, message: str) -> None:
                    self._post_update_progress(
                        window,
                        UpdateProgress(stage, message, "info", True),
                    )
                    self._on_log(f"[启动器] {message}")

                result = apply_luker_update(
                    str(active_manager.luker_path),
                    target,
                    on_stage=on_stage,
                )

                if result.success:
                    if not was_running:
                        message = f"{result.message}；Luker 未运行，未自动启动"
                        self._on_log(f"[启动器] {message}")
                        self._post_update_progress(
                            window,
                            UpdateProgress("done", message, "success", False),
                            control=True,
                        )
                        return

                    self._post_update_progress(
                        window,
                        UpdateProgress("restarting", "正在重启 Luker...", "info", True),
                    )
                    start_error = self._start_luker_safely(active_manager)
                    if start_error is not None:
                        message = f"{result.message}，但 Luker {start_error}，请手动启动"
                        self._on_log(f"[错误] {message}")
                        self._post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                            control=True,
                        )
                        return
                    message = f"{result.message}，Luker 已重启"
                    self._on_log(f"[启动器] {message}")
                    self._post_update_progress(
                        window,
                        UpdateProgress("done", message, "success", False),
                        control=True,
                    )
                    return

                if was_running:
                    if result.code_changed and not result.rolled_back:
                        message = f"{result.message}；自动回滚失败，未自动启动 Luker，请手动检查"
                        self._on_log(f"[错误] {message}")
                        self._post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                            control=True,
                        )
                        return

                    self._post_update_progress(
                        window,
                        UpdateProgress("restarting", "正在恢复原版本...", "warning", True),
                    )
                    start_error = self._start_luker_safely(active_manager)
                    if start_error is not None:
                        message = f"{result.message}；原版本{start_error}，请手动启动"
                        self._on_log(f"[错误] {message}")
                        self._post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                            control=True,
                        )
                        return

                self._on_log(f"[错误] {result.message}")
                self._post_update_progress(
                    window,
                    UpdateProgress("error", result.message, "error", False),
                    control=True,
                )
            except Exception as error:
                logger.exception("更新 Luker 失败")
                message = f"更新 Luker 失败：{error}"
                self._on_log(f"[错误] {message}")
                self._post_update_progress(
                    window,
                    UpdateProgress("error", message, "error", False),
                    control=True,
                )
            finally:
                self._updating = False
                if self._post_ui(self._finish_process_action, control=True) is False:
                    self._process_busy = False

        if not self._start_process_worker(
            worker,
            context="Luker 更新",
            on_failure=lambda: self._post_update_progress(
                window,
                UpdateProgress("error", "无法启动更新线程", "error", False),
                control=True,
            ),
        ):
            self._updating = False
            return False
        return True

    def _on_show_menu(self, x: int, y: int) -> None:
        if self._exiting:
            return
        # 托盘线程在右键当下记录前台窗口，主线程稍后可能已被任务栏抢走
        try:
            previous_foreground = int(win32_api.user32.GetForegroundWindow())
        except Exception:
            previous_foreground = 0
        self._post_ui(
            lambda: self._show_tray_menu(x, y, previous_foreground),
            UI_KEY_TRAY_MENU,
        )

    def _show_tray_menu(self, x: int, y: int, previous_foreground: int = 0) -> None:
        if not (self.tray_menu and self.log_window):
            return

        # 记录托盘点击位置，设置窗口按该显示器打开
        self._tray_anchor = (x, y)
        state = self._current_luker_state()
        window_visible = self.log_window.is_visible()
        self.tray_menu.update_state(
            state is not LukerState.STOPPED,
            window_visible,
            state,
        )
        self.tray_menu.show_at(x, y, previous_foreground)

    def _update_status(self) -> None:
        self._status.update()

    def _schedule_status_poll(self) -> None:
        self._status.schedule_poll()

    def run(self) -> None:
        """创建窗口、托盘和进程管理器，进入 Tk 主循环。"""
        # 首次运行：配置缺失时引导选择 Luker 路径
        if not ensure_luker_path_configured():
            logger.error("未配置 Luker 路径，程序退出")
            messagebox.showinfo("Luker 启动器", "未配置 Luker 路径，程序将退出。")
            return

        self._create_log_window()
        # 启动主线程 UI 队列泵，后台线程才能安全地请求界面操作
        self._ui.start()
        self._ensure_process_manager()
        self._status.start()
        self._create_tray_menu()
        self._create_tray_icon()

        self._running = True
        tray_ready = self._start_tray()
        self._start_first_run(tray_ready)
        self._schedule_auto_open_browser_if_needed()

        window = self.log_window
        if window is not None:
            window.mainloop()
        self._cleanup_after_mainloop()

    def _create_log_window(self) -> None:
        self.log_window = LogWindow(
            on_hide_callback=lambda: (
                self.tray_icon.set_window_visible(False) if self.tray_icon else None
            ),
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_exit=self._on_request_exit,
        )
        # 内部警告/错误同步到日志窗口
        logging_setup.add_ui_log_sink(self._on_log)

    def _create_tray_menu(self) -> None:
        window = self.log_window
        if window is None:
            return
        self.tray_menu = TrayMenu(
            window,
            {
                'show_window': self._on_show_window,
                'hide_window': self._on_hide_window,
                'start': self._on_start,
                'stop': self._on_stop,
                'restart': self._on_restart,
                'settings': self._on_settings,
                'open_browser': self._on_open_browser,
                'exit': self._on_exit,
            },
        )

    def _create_tray_icon(self) -> None:
        self.tray_icon = TrayIcon(
            on_show_window=self._on_show_window,
            on_hide_window=self._on_hide_window,
            on_show_menu=self._on_show_menu,
        )

    def _start_tray(self) -> bool:
        """托盘消息循环会永久阻塞，必须放在独立线程。"""
        icon = self.tray_icon
        if icon is None:
            return False
        tray_ready = icon.run_detached()
        self._tray_ready = tray_ready
        self._schedule_status_poll()
        return tray_ready

    def _start_first_run(self, tray_ready: bool) -> None:
        window = self.log_window
        if window is None:
            return

        self._on_log("[启动器] 正在启动 Luker...")
        self._on_start()
        if tray_ready:
            window.hide()
            self._on_log("[启动器] 已最小化到系统托盘，单击图标可显示日志窗口")
        else:
            # 没有托盘时保留窗口作为唯一入口，关闭按钮仍走确认框
            window.set_tray_available(False)
            window.show()
            self._on_log("[错误] 托盘图标创建失败，日志窗口保持显示；关闭窗口会询问是否退出")

    def _schedule_auto_open_browser_if_needed(self) -> None:
        self._browser.schedule_auto_open_if_needed()

    def _cleanup_after_mainloop(self) -> None:
        # 与 _finish_exit 共用同一套幂等清理
        self._shutdown()
