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

import app_logging
from config import config
from dialogs import show_exit_confirmation
from log_window import LogWindow
from luker_readiness import LukerReadinessMonitor, LukerState
from path_dialogs import ensure_luker_path_configured
from process_manager import GCLProcessManager, LukerProcessManager
from pwa_browser import open_in_browser
from settings_window import SettingsWindow
from tray_icon import TrayIcon
from tray_menu import TrayMenu
from ui_dispatch import UiDispatcher

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
        self._last_status: LukerState | None = None  # 上一次通知给界面的运行状态
        self._readiness: LukerReadinessMonitor | None = None
        # 托盘/进程线程不能直接操作 Tk，统一投递到这里由主线程执行
        self._ui = UiDispatcher(self._schedule_ui)
        # 最近一次托盘点击位置，用于把设置窗口放到点击所在显示器
        self._tray_anchor: tuple[int, int] | None = None
        self.settings_window: SettingsWindow | None = None

        config.add_gcl_change_callback(self._on_gcl_config_change)

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
    ) -> None:
        """从任意线程投递 UI 操作；同一 coalesce_key 只保留最后一次。"""
        self._ui.post(callback, coalesce_key)

    def _current_luker_state(self) -> LukerState:
        """综合进程存活和本地服务探测结果，返回界面使用的三态。"""
        manager = self.process_manager
        if manager is None or not manager.is_running:
            return LukerState.STOPPED

        readiness = self._readiness
        if readiness is not None and readiness.state is LukerState.READY:
            return LukerState.READY
        return LukerState.STARTING

    def _on_luker_state_change(self, state: LukerState) -> None:
        """就绪探测线程回调；回到 Tk 主线程后再更新界面。"""
        self._post_ui(
            lambda: self._apply_luker_state(state),
            UI_KEY_LUKER_STATE,
        )

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
                self._post_ui(lambda: self._adopt_process_manager(manager))
                # 先切换 UI 持有的管理器，再启动；退出过程中不再拉起新进程
                if not self._exiting:
                    manager.start()
                    if self._exiting and manager.is_running:
                        manager.stop()
            finally:
                self._post_ui(self._finish_process_action)

        self._start_process_worker(worker, context="路径切换")

    def _adopt_process_manager(self, manager: LukerProcessManager) -> None:
        self.process_manager = manager
        self._last_status = None

    def _on_request_exit(self) -> None:
        """日志窗口关闭按钮：先确认，再停止 Luker 并退出启动器。"""
        if self._exiting or self._exit_dialog_open or not self.log_window:
            return

        self._exit_dialog_open = True
        state = self._current_luker_state()

        def on_confirm() -> None:
            self._exit_dialog_open = False
            if self.log_window:
                self.log_window.hide()
            self._on_exit()

        def on_cancel() -> None:
            self._exit_dialog_open = False
            if self.log_window:
                self.log_window.focus_force()

        try:
            show_exit_confirmation(self.log_window, state, on_confirm, on_cancel)
        except Exception:
            logger.exception("显示退出确认框失败，回退到系统对话框")
            self._exit_dialog_open = False
            try:
                confirmed = messagebox.askyesno(
                    "退出 Luker",
                    "退出会停止 Luker 进程，并关闭 Luker Launcher。\n确定要退出吗？",
                    parent=self.log_window,
                )
            except Exception:
                logger.exception("显示系统退出确认框失败")
                return
            if confirmed:
                on_confirm()
            else:
                on_cancel()

    def _on_exit(self) -> None:
        if self._exiting:
            return
        self._exiting = True
        self._running = False

        # 停止进程可能耗时数秒，放到后台，完成后再结束主循环
        managers = [m for m in (self.process_manager, self.gcl_process_manager) if m]

        def worker() -> None:
            readiness = self._readiness
            if readiness is not None:
                readiness.stop()
            for manager in managers:
                manager.stop()
            self._post_ui(self._finish_exit, UI_KEY_EXIT)

        try:
            self._run_async(worker)
        except Exception:
            logger.exception("启动退出线程失败")
            self._finish_exit()

    def _finish_exit(self) -> None:
        """停止托盘并结束 Tk 主循环。"""
        try:
            # worker 通常已停过；线程创建失败时走的是没有 worker 的回退路径。
            # stop() 幂等，重复调用不会再次等待已结束的线程。
            readiness = self._readiness
            if readiness is not None:
                readiness.stop()
            self._ui.stop()
            config.remove_gcl_change_callback(self._on_gcl_config_change)
            if self.tray_icon:
                self.tray_icon.stop()
        finally:
            if self.log_window:
                self.log_window.quit()

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
                self._post_ui(self._finish_process_action)

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
                self._post_ui(self._finish_process_action)

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
                self._post_ui(self._finish_browser_open)

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
        )
        self.settings_window.focus_force()

    def _on_settings_closed(self) -> None:
        """设置窗口销毁后清理引用。"""
        self.settings_window = None

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
            self._sync_gcl_ui(False)
            return

        def worker() -> None:
            try:
                stopped = current is None or current.stop()
            except Exception:
                logger.exception("停止旧 GCL 进程失败")
                stopped = False

            if stopped:
                self._post_ui(lambda: self._finish_gcl_config_change(current, new_path, True))
            else:
                self._post_ui(lambda: self._finish_gcl_config_change(current, None, False))

        self._start_process_worker(
            worker,
            on_failure=lambda: self._sync_gcl_ui(current is not None),
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
                self._sync_gcl_ui(old_manager is not None)
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

            self._sync_gcl_ui(new_path is not None)
        finally:
            self._finish_process_action()

    def _sync_gcl_ui(self, enabled: bool) -> None:
        """同步日志窗口里的 GCL 控件状态。"""
        window = self.log_window
        if window is not None:
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
        self._ensure_process_manager()
        self._create_readiness()
        self._create_tray_menu()
        self._init_gcl_manager()
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
        app_logging.add_ui_log_sink(self._on_log)

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

    def _init_gcl_manager(self) -> None:
        window = self.log_window
        if window is None:
            return
        if (
            config.gcl_enabled
            and config.gcl_bat_path
            and config.is_valid_gcl_path(config.gcl_bat_path)
        ):
            self.gcl_process_manager = GCLProcessManager(config.gcl_bat_path)
            self.gcl_process_manager.add_log_callback(self._on_gcl_log)
            window.set_gcl_enabled(True)
        else:
            window.set_gcl_enabled(False)

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
        # 与 _finish_exit 互为兜底，正常退出时这里已是幂等操作
        self._ui.stop()
        config.remove_gcl_change_callback(self._on_gcl_config_change)
        self._running = False
        if self.tray_icon:
            self.tray_icon.stop()

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
