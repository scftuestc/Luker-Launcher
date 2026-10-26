"""启动器应用主体：协调日志窗口、托盘、进程与退出流程。"""

import logging
import time
import tkinter as tk
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from tkinter import messagebox

import logging_setup
from config import config
from core.browser import open_in_browser
from core.readiness import LukerReadinessMonitor, LukerState
from core.version import (
    UpdateProgress,
    UpdateTarget,
    VersionCheck,
    apply_luker_update,
    check_luker_versions,
    read_local_version,
)
from dialogs import ensure_luker_path_configured, show_close_choice
from log_window import LogWindow
from process.managers import GCLProcessManager, LukerProcessManager
from settings_window import SettingsWindow
from tray.icon import TrayIcon
from tray.menu import TrayMenu
from ui.dispatch import UiDispatcher

logger = logging.getLogger(__name__)

STATUS_POLL_INTERVAL = 2
BROWSER_WAIT_TIMEOUT_SECONDS = 30
BROWSER_WAIT_INTERVAL_SECONDS = 1
# 合并键：同一键只保留最后一次请求
UI_KEY_VISIBILITY = "visibility"
UI_KEY_TRAY_MENU = "tray_menu"
UI_KEY_SETTINGS = "settings"
UI_KEY_GCL_UI = "gcl_ui"
UI_KEY_LUKER_STATE = "luker_state"
UI_KEY_EXIT = "exit"


class LukerLauncher:
    """协调日志窗口、托盘菜单和两个进程管理器的应用主体。"""

    def __init__(self) -> None:
        self.process_manager: LukerProcessManager | None = None
        self.gcl_process_manager: GCLProcessManager | None = None
        self.tray_icon: TrayIcon | None = None
        self.log_window: LogWindow | None = None
        self.tray_menu: TrayMenu | None = None
        self._running = False
        self._process_busy = False  # 防止启停/重启操作重入
        # 进程操作期间收到的 GCL 配置变更，等操作结束后再应用
        self._pending_gcl_config: tuple[bool, str | None] | None = None
        self._browser_busy = False  # 防止重复启动 PWA 发现线程
        self._exiting = False  # 退出流程只执行一次
        self._exit_dialog_open = False
        self._tray_ready = False
        self._version_checking = False
        self._updating = False
        self._shutdown_done = False
        self._last_status: LukerState | None = None  # 上一次通知给界面的运行状态
        self._readiness: LukerReadinessMonitor | None = None
        # 托盘/进程线程不能直接操作 Tk，统一投递到这里由主线程执行
        self._ui = UiDispatcher(self._schedule_ui)
        # 最近一次托盘点击位置，用于把设置窗口放到点击所在显示器
        self._tray_anchor: tuple[int, int] | None = None
        self.settings_window: SettingsWindow | None = None

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
        """综合进程存活和本地服务探测结果，返回界面使用的三态。"""
        manager = self.process_manager
        if manager is None or not manager.is_running:
            return LukerState.STOPPED

        readiness = self._readiness
        if readiness is not None and readiness.state is LukerState.READY:
            return LukerState.READY
        return LukerState.STARTING

    def _on_luker_state_change(self, _state: LukerState) -> None:
        """就绪探测线程回调；只唤醒主线程重新计算当前状态。

        回调携带的状态可能已在队列中过期，不能直接应用，否则旧的
        STARTING 会覆盖新的 READY。
        """
        self._post_ui(self._refresh_luker_state, UI_KEY_LUKER_STATE)

    def _refresh_luker_state(self) -> None:
        self._apply_luker_state(self._current_luker_state())

    def _apply_luker_state(self, state: LukerState) -> None:
        if state is self._last_status:
            return
        self._last_status = state
        window = self.log_window
        if window is not None:
            window.update_status(state)
        menu = self.tray_menu
        if menu is not None:
            menu.set_luker_state(state)

    def _reset_luker_readiness(self) -> None:
        """启动/重启前清空旧的就绪结果，避免沿用上一次的 READY。"""
        self._last_status = None
        readiness = self._readiness
        if readiness is not None:
            readiness.reset()

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
        if self._process_busy or self._exiting:
            return
        self._reset_luker_readiness()
        self._do_process_action(lambda manager: manager.start())

    def _on_stop(self) -> None:
        self._do_process_action(lambda manager: manager.stop())

    def _on_restart(self) -> None:
        if self._process_busy or self._exiting:
            return

        self._reset_luker_readiness()
        desired_path = config.luker_path
        current = self.process_manager
        if desired_path and current and str(current.luker_path) != str(Path(desired_path)):
            self._restart_with_path(desired_path)
            return

        self._do_process_action(lambda manager: manager.restart())

    def _restart_with_path(self, path: str) -> None:
        """路径变化时先停旧进程，再创建并启动新管理器。"""
        self._reset_luker_readiness()
        old_manager = self.process_manager

        def worker() -> None:
            try:
                if old_manager and not old_manager.stop():
                    self._on_log("[错误] 旧 Luker 进程未停止，已取消切换路径")
                    return
                if self._exiting:
                    return

                manager = LukerProcessManager(
                    path,
                    let_luker_open_browser=not config.use_pwa_mode,
                    server_port=config.get_server_port(),
                )
                manager.add_log_callback(self._on_log)
                self._post_ui(lambda: self._adopt_process_manager(manager), control=True)
                # 先切换 UI 持有的管理器，再启动；退出过程中不再拉起新进程
                if not self._exiting:
                    manager.start()
                    if self._exiting and manager.is_running:
                        manager.stop()
            finally:
                if self._post_ui(self._finish_process_action, control=True) is False:
                    self._process_busy = False

        self._start_process_worker(worker, context="路径切换")

    def _adopt_process_manager(self, manager: LukerProcessManager) -> None:
        if self._exiting:
            # 退出已开始，拒绝接管；新实例交给后台线程停止
            logger.debug("退出中，拒绝接管新的进程管理器")

            def stop_incoming() -> None:
                manager.stop()

            try:
                self._run_async(stop_incoming)
            except Exception:
                logger.exception("停止退出期间创建的进程管理器失败")
            return
        self.process_manager = manager
        self._last_status = None

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
        self._running = False

        # 停止进程可能耗时数秒，放到后台，完成后再结束主循环
        def worker() -> None:
            readiness = self._readiness
            if readiness is not None:
                readiness.stop()
            self._stop_all_process_managers()
            self._post_ui(self._finish_exit, UI_KEY_EXIT)

        try:
            self._run_async(worker)
        except Exception:
            logger.exception("启动退出线程失败")
            self._finish_exit()

    def _stop_all_process_managers(self) -> None:
        """停止当前所有管理器，并覆盖退出期间新接管的实例。

        `_on_exit` 不再对管理器列表做快照；每轮重新读取，最多三轮，
        避免路径切换在退出过程中安装的新实例逃过清理。
        """
        seen: set[int] = set()
        for _ in range(3):
            managers = [
                manager
                for manager in (self.process_manager, self.gcl_process_manager)
                if manager is not None
            ]
            pending = [manager for manager in managers if id(manager) not in seen]
            if not pending:
                return
            for manager in pending:
                seen.add(id(manager))
                try:
                    manager.stop()
                except Exception:
                    logger.exception("停止进程失败")

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

        readiness = self._readiness
        if readiness is not None:
            readiness.stop()
        self._ui.stop()
        config.remove_gcl_change_callback(self._on_gcl_config_change)
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
        """启动一次进程操作；线程创建失败时复位 busy 并执行 on_failure。"""
        self._process_busy = True
        try:
            self._run_async(worker)
        except Exception:
            self._process_busy = False
            logger.exception("%s线程启动失败", context)
            if on_failure is not None:
                on_failure()
            return False
        return True

    def _ensure_process_manager(self) -> LukerProcessManager | None:
        """确保进程管理器与当前配置的 Luker 路径保持一致。"""
        if not config.luker_path:
            return None

        path = config.luker_path
        if self.process_manager is None or str(self.process_manager.luker_path) != str(Path(path)):
            if self.process_manager and self.process_manager.is_running:
                # 运行中不热切换，避免意外中断正在工作的进程
                return self.process_manager

            self.process_manager = LukerProcessManager(
                path,
                let_luker_open_browser=not config.use_pwa_mode,
                server_port=config.get_server_port(),
            )
            self.process_manager.add_log_callback(self._on_log)
            self._last_status = None
        else:
            self.process_manager.let_luker_open_browser = not config.use_pwa_mode
            self.process_manager.server_port = config.get_server_port()

        return self.process_manager

    def _do_process_action(self, action: Callable[[LukerProcessManager], bool]) -> None:
        """在后台线程执行进程操作，避免停止/重启时阻塞界面。"""
        if self._process_busy or self._exiting:
            return

        manager = self._ensure_process_manager()
        if manager is None:
            self._on_log("[错误] 未配置 Luker 路径")
            return

        def worker() -> None:
            try:
                action(manager)
            finally:
                if self._post_ui(self._finish_process_action, control=True) is False:
                    # UI 泵已停止（通常正在退出），没有主线程来复位忙碌标志
                    self._process_busy = False

        self._start_process_worker(worker)

    def _finish_process_action(self) -> None:
        """结束一次进程操作：复位 busy 并应用等待中的 GCL 配置。

        每个把 busy 置 True 的操作都必须且只能在 finally 中投递一次本方法；
        漏投或重复投递会让后续启停和 GCL 配置切换失去保护。
        """
        self._process_busy = False
        self._update_status()

        # 操作期间收到过 GCL 配置变更，现在才安全应用
        pending = self._pending_gcl_config
        if pending is not None:
            self._pending_gcl_config = None
            if not self._exiting:
                self._apply_gcl_config_change(*pending)

    def _do_gcl_action(self, action: Callable[[GCLProcessManager], bool]) -> None:
        """GCL 启停也走统一的忙碌/退出保护。"""
        if self._process_busy or self._exiting:
            return

        manager = self.gcl_process_manager
        if manager is None:
            return

        def worker() -> None:
            try:
                action(manager)
            finally:
                if self._post_ui(self._finish_process_action, control=True) is False:
                    self._process_busy = False

        self._start_process_worker(worker, context="GCL 进程操作")

    def _on_settings(self) -> None:
        if self._exiting:
            return
        self._post_ui(self._open_settings_window, UI_KEY_SETTINGS)

    def _on_open_browser(self) -> None:
        """打开浏览器；PWA 发现可能调用 PowerShell，放到后台避免卡住界面。"""
        if self._exiting or self._browser_busy:
            return

        self._browser_busy = True

        def worker() -> None:
            try:
                self._open_browser_now()
            finally:
                if self._post_ui(self._finish_browser_open, control=True) is False:
                    self._browser_busy = False

        try:
            self._run_async(worker)
        except Exception:
            self._browser_busy = False
            logger.exception("启动浏览器打开线程失败")

    def _finish_browser_open(self) -> None:
        self._browser_busy = False

    def _open_browser_now(self) -> None:
        open_in_browser(config.get_server_url(), prefer_pwa=config.use_pwa_mode)

    def _open_settings_window(self) -> None:
        """打开或聚焦设置窗口；已打开时只置前，不移动。"""
        if self._exiting or not self.log_window:
            return

        window = self.settings_window
        if window is not None and window.is_alive():
            window.focus_force()
            return

        self.settings_window = SettingsWindow(
            self.log_window,
            anchor_point=self._tray_anchor,
            on_close=self._on_settings_closed,
            on_check_luker_update=self._request_luker_version_check,
            on_apply_luker_update=self._apply_luker_update,
        )
        self.settings_window.focus_force()

    def _on_settings_closed(self) -> None:
        """设置窗口销毁后清理引用。"""
        self.settings_window = None

    def _request_luker_version_check(self) -> bool:
        """在后台检查本地版本、最新发行版和最新提交。"""
        if self._version_checking or self._exiting:
            return False
        window = self.settings_window
        if window is None:
            return False

        repo_path = config.luker_path
        manager = self.process_manager
        running_path = (
            str(manager.luker_path) if manager is not None and manager.is_running else None
        )
        self._version_checking = True
        self._on_log("[启动器] 正在检查 Luker 版本...")
        failed = False

        def worker() -> None:
            nonlocal failed
            try:
                result = check_luker_versions(repo_path, running_path=running_path)
            except Exception as error:
                failed = True
                logger.exception("检查 Luker 版本失败：%s", error)
                local = read_local_version(repo_path, running_path=running_path)
                result = VersionCheck(
                    repo_path=local.repo_path,
                    local=local,
                    release=None,
                    commit=None,
                    error=f"检查版本失败：{error}",
                )
            finally:
                self._version_checking = False
            if not failed:
                self._log_version_check(result)
            self._post_ui(
                lambda: self._deliver_version_check(window, result),
                control=True,
            )

        try:
            self._run_async(worker)
        except Exception:
            self._version_checking = False
            logger.exception("启动 Luker 版本检查线程失败")
            return False
        return True

    def _deliver_version_check(
        self,
        window: SettingsWindow,
        result: VersionCheck,
    ) -> None:
        if self.settings_window is window and window.is_alive():
            window.set_version_check(result)

    def _log_version_check(self, result: VersionCheck) -> None:
        """把检查结果显示到日志窗口。"""
        local = result.local
        version = local.describe or local.short_head
        if not local.error and version:
            branch = local.branch if local.branch and local.branch != "HEAD" else "分离 HEAD"
            meta = " · ".join(part for part in (branch, local.date) if part)
            line = f"[启动器] 当前版本：{version}"
            self._on_log(f"{line} · {meta}" if meta else line)

        release = result.release
        if release is not None:
            self._on_log(
                f"[启动器] 最新发行版：{release.tag or release.label} · "
                f"发布于 {release.published_at or '未知'} · 提交 {release.commit.sha}"
            )

        commit = result.commit
        if commit is not None:
            self._on_log(f"[启动器] 最新提交：{commit.commit.date or '未知'} · {commit.commit.sha}")

        if result.error:
            has_target = release is not None or commit is not None
            self._on_log(f"[{'警告' if has_target else '错误'}] {result.error}")

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

    def _apply_luker_update(self, target: UpdateTarget) -> bool:
        """停止 Luker、切换版本、安装依赖并按原状态重启。"""
        if self._updating or self._process_busy or self._exiting:
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
            and str(manager.luker_path) != str(Path(configured_path))
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

        local = read_local_version(str(manager.luker_path))
        if local.error:
            self._post_update_progress(
                window,
                UpdateProgress("error", local.error, "error", False),
                control=True,
            )
            return False
        if not local.npm_available:
            self._post_update_progress(
                window,
                UpdateProgress("error", "未找到 npm，无法安装依赖", "error", False),
                control=True,
            )
            return False
        if local.dirty:
            self._post_update_progress(
                window,
                UpdateProgress(
                    "error",
                    "检测到未提交的修改，已取消更新",
                    "warning",
                    False,
                ),
                control=True,
            )
            return False

        active_manager = manager
        was_running = manager.is_running
        self._updating = True

        def worker() -> None:
            try:
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
                    if not active_manager.start():
                        message = f"{result.message}，但 Luker 启动失败，请手动启动"
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
                    if not active_manager.start():
                        message = f"{result.message}；原版本启动失败，请手动启动"
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

    def _on_gcl_start(self) -> None:
        self._do_gcl_action(lambda manager: manager.start())

    def _on_gcl_stop(self) -> None:
        self._do_gcl_action(lambda manager: manager.stop())

    def _on_gcl_log(self, line: str) -> None:
        if self.log_window:
            self.log_window.add_gcl_log(line)

    def _on_gcl_config_change(self, enabled: bool, bat_path: str | None) -> None:
        """GCL 配置变更回调，动态创建或销毁 GCL 进程管理器"""
        if self._exiting:
            return

        # 启动/停止是异步的，进行中判断 is_running 可能尚未反映真实状态。
        # 此时只记录最新配置，等操作结束再由 _finish_process_action 应用。
        if self._process_busy:
            self._pending_gcl_config = (enabled, bat_path)
            return

        self._apply_gcl_config_change(enabled, bat_path)

    def _apply_gcl_config_change(self, enabled: bool, bat_path: str | None) -> None:
        """在进程空闲时切换 GCL 管理器，旧进程确认停止前不安装新实例。"""
        active = bool(enabled and bat_path and config.is_valid_gcl_path(bat_path))
        current = self.gcl_process_manager

        new_path = str(bat_path) if active else None
        current_path = str(current.bat_path) if current is not None else None
        if active and current_path == new_path:
            return
        if not active and current is None:
            self._sync_gcl_ui()
            return

        def worker() -> None:
            try:
                stopped = current is None or current.stop()
            except Exception:
                logger.exception("停止旧 GCL 进程失败")
                stopped = False

            if stopped:
                accepted = self._post_ui(
                    lambda: self._finish_gcl_config_change(current, new_path, True),
                    control=True,
                )
            else:
                accepted = self._post_ui(
                    lambda: self._finish_gcl_config_change(current, None, False),
                    control=True,
                )
            if accepted is False:
                # UI 泵已停止，完成回调不会再执行，直接释放忙碌标志
                self._process_busy = False

        self._start_process_worker(
            worker,
            on_failure=self._sync_gcl_ui,
            context="GCL 配置切换",
        )

    def _finish_gcl_config_change(
        self,
        old_manager: GCLProcessManager | None,
        new_path: str | None,
        stopped: bool,
    ) -> None:
        """在主线程安装或保留 GCL 管理器，并结束本次进程操作。"""
        try:
            if not stopped:
                self._on_log("[错误] 旧 GCL 进程未停止，已取消配置切换")
                # 保留旧实例，菜单里仍能看到并重试停止
                self._sync_gcl_ui()
                return

            if new_path is None:
                self.gcl_process_manager = None
                if old_manager is not None:
                    self._on_log("[启动器] GCL 功能已禁用")
            else:
                manager = GCLProcessManager(new_path)
                manager.add_log_callback(self._on_gcl_log)
                self.gcl_process_manager = manager
                self._on_log("[启动器] GCL 功能已启用")

            self._sync_gcl_ui()
        finally:
            self._finish_process_action()

    def _sync_gcl_ui(self) -> None:
        """同步日志窗口里的 GCL 控件状态；唯一入口。"""
        window = self.log_window
        if window is None:
            return
        enabled = self.gcl_process_manager is not None
        self._post_ui(
            lambda: window.set_gcl_enabled(enabled),
            UI_KEY_GCL_UI,
        )

    def _on_show_menu(self, x: int, y: int) -> None:
        if self._exiting:
            return
        # 托盘线程只传坐标，状态读取和菜单显示都回到主线程
        self._post_ui(
            lambda: self._show_tray_menu(x, y),
            UI_KEY_TRAY_MENU,
        )

    def _show_tray_menu(self, x: int, y: int) -> None:
        if not (self.tray_menu and self.log_window):
            return

        # 记录托盘点击位置，设置窗口按该显示器打开
        self._tray_anchor = (x, y)
        state = self._current_luker_state()
        window_visible = self.log_window.is_visible()
        gcl_enabled = self.gcl_process_manager is not None
        gcl_running = self.gcl_process_manager.is_running if self.gcl_process_manager else False
        self.tray_menu.update_state(
            state is not LukerState.STOPPED,
            window_visible,
            gcl_enabled,
            gcl_running,
            state,
        )
        self.tray_menu.show_at(x, y)

    def _update_status(self) -> None:
        if not self.process_manager:
            return
        is_running = self.process_manager.is_running
        if self.tray_icon:
            self.tray_icon.update_status(is_running)
        self._apply_luker_state(self._current_luker_state())

    def _schedule_status_poll(self) -> None:
        """在 Tk 主线程按固定间隔检查进程状态，不再单独占用监控线程。"""
        if not self._running:
            return

        try:
            self._update_status()
        except Exception:
            logger.exception("更新进程状态失败")
        finally:
            if self._running and self.log_window:
                self.log_window.after(STATUS_POLL_INTERVAL * 1000, self._schedule_status_poll)

    def run(self) -> None:
        """创建窗口、托盘和进程管理器，进入 Tk 主循环。"""
        # 首次运行：配置缺失时引导选择 Luker 路径
        if not ensure_luker_path_configured():
            logger.error("未配置 Luker 路径，程序退出")
            return

        self._create_log_window()
        # 启动主线程 UI 队列泵，后台线程才能安全地请求界面操作
        self._ui.start()
        # UI 泵就绪后再接收配置变更，避免完成回调被静默丢弃
        config.add_gcl_change_callback(self._on_gcl_config_change)
        self._ensure_process_manager()
        self._create_readiness()
        self._create_tray_menu()
        self._ensure_gcl_manager()
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

    def _create_readiness(self) -> None:
        self._readiness = LukerReadinessMonitor(
            lambda: bool(self.process_manager and self.process_manager.is_running),
            config.get_server_url,
            self._on_luker_state_change,
        )
        self._readiness.start()

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
                'gcl_start': self._on_gcl_start,
                'gcl_stop': self._on_gcl_stop,
                'exit': self._on_exit,
            },
        )

    def _ensure_gcl_manager(self) -> None:
        """按当前配置创建 GCL 管理器，并统一同步一次界面状态。"""
        path = config.gcl_bat_path
        valid = bool(config.gcl_enabled and path and config.is_valid_gcl_path(path))
        if not valid or path is None:
            self.gcl_process_manager = None
        elif self.gcl_process_manager is None:
            manager = GCLProcessManager(path)
            manager.add_log_callback(self._on_gcl_log)
            self.gcl_process_manager = manager
        self._sync_gcl_ui()

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
            # 没有托盘时保留窗口作为唯一入口，关闭窗口直接退出
            window.set_tray_available(False)
            window.on_hide_callback = self._on_exit
            window.show()
            self._on_log("[错误] 托盘图标创建失败，日志窗口保持显示；关闭窗口将退出")

        if self.gcl_process_manager:
            self._on_log("[启动器] GCL 功能已启用，可通过右键菜单控制")

    def _schedule_auto_open_browser_if_needed(self) -> None:
        if config.use_pwa_mode:
            self._schedule_auto_open_browser()

    def _cleanup_after_mainloop(self) -> None:
        # 与 _finish_exit 共用同一套幂等清理
        self._shutdown()

    def _schedule_auto_open_browser(self) -> None:
        """延迟打开浏览器，等待 Luker 服务启动"""

        def check_and_open() -> None:
            url = config.get_server_url()
            deadline = time.monotonic() + BROWSER_WAIT_TIMEOUT_SECONDS

            while self._running and time.monotonic() < deadline:
                ready = False
                try:
                    # 尝试连接 Luker，响应由 with 负责关闭
                    with urllib.request.urlopen(url, timeout=BROWSER_WAIT_INTERVAL_SECONDS):
                        ready = True
                except urllib.error.HTTPError as e:
                    # 服务已响应，只是返回了 4xx/5xx，同样说明已经就绪
                    e.close()
                    ready = True
                except (urllib.error.URLError, TimeoutError, OSError):
                    ready = False

                if ready:
                    self._on_log("[启动器] 检测到 Luker 已启动，正在打开 PWA 浏览器...")
                    # 回到主线程复用 _browser_busy，避免自动和手动同时打开
                    self._post_ui(self._on_open_browser)
                    return

                time.sleep(BROWSER_WAIT_INTERVAL_SECONDS)

            if self._running:
                self._on_log("[启动器] 等待 Luker 启动超时，请手动打开浏览器")

        Thread(target=check_and_open, daemon=True).start()
