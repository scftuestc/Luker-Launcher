"""启动器应用主体：协调日志窗口、托盘、进程与退出流程。"""

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

import logging_setup
import win32_api
from application.browser_coordinator import BrowserCoordinator
from application.lifecycle_coordinator import LifecycleCoordinator
from application.lifecycle_state import LifecycleState
from application.process_coordinator import ProcessCoordinator
from application.status_coordinator import StatusCoordinator
from application.task_runner import TaskRunner
from application.update_coordinator import UpdateCoordinator
from config import config
from core.browser import open_in_browser
from core.readiness import LukerState
from core.version import same_path
from dialogs import ensure_luker_path_configured
from log_window import LogWindow
from settings_window import SettingsWindow
from tray.icon import TrayIcon
from tray.menu import TrayMenu
from ui.dispatch import UiDispatcher

logger = logging.getLogger(__name__)

# 合并键：同一键只保留最后一次请求
UI_KEY_VISIBILITY = "visibility"
UI_KEY_TRAY_MENU = "tray_menu"
UI_KEY_SETTINGS = "settings"


class LukerLauncher:
    """协调日志窗口、托盘菜单和 Luker 进程管理器的应用主体。"""

    def __init__(self) -> None:
        self.tray_icon: TrayIcon | None = None
        self.log_window: LogWindow | None = None
        self.tray_menu: TrayMenu | None = None
        self._running = False
        self._tray_ready = False
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
            on_status_reset=lambda: self._status.reset(),
            on_manager_replaced=lambda: self._status.clear_last_state(),
            on_finished=lambda: self._status.update(),
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
        self._lifecycle_coordinator = LifecycleCoordinator(
            config=config,
            process=self._process,
            status=self._status,
            ui=self._ui,
            task_runner=self._task_runner,
            post_ui=self._ui,
            log=self._on_log,
            lifecycle=self._lifecycle,
            window_provider=lambda: self.log_window,
            tray_icon_provider=lambda: self.tray_icon,
            tray_ready=lambda: self._tray_ready,
            hide_window=self._hide_window,
            current_state=self._status.current_state,
            is_updating=lambda: self._update.updating,
            set_running=self._set_running,
        )
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

    def _set_running(self, value: bool) -> None:
        self._running = value

    def _on_settings(self) -> None:
        if self._lifecycle.exiting:
            return
        self._post_ui(self._open_settings_window, UI_KEY_SETTINGS)

    def _open_settings_window(self) -> None:
        """打开或聚焦设置窗口；已打开时只置前，不移动。"""
        if self._lifecycle.exiting or not self.log_window:
            return

        window = self.settings_window
        if window is not None and window.is_alive():
            window.focus_force()
            return

        cached = self._update.version_check_cache
        current_path = config.luker_path
        if cached is not None and (
            not current_path or not same_path(cached.repo_path, current_path)
        ):
            self._update.version_check_cache = None
            cached = None

        self.settings_window = SettingsWindow(
            self.log_window,
            anchor_point=self._tray_anchor,
            on_close=self._on_settings_closed,
            on_check_luker_update=self._update.request_check,
            on_apply_luker_update=self._update.apply_update_target,
            on_luker_path_changed=self._update.path_changed,
            initial_version_check=cached,
            initial_version_checking=self._update.checking,
        )
        self.settings_window.focus_force()

    def _on_settings_closed(self) -> None:
        """设置窗口销毁后清理引用。"""
        self.settings_window = None

    def _on_show_menu(self, x: int, y: int) -> None:
        if self._lifecycle.exiting:
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
        state = self._status.current_state()
        window_visible = self.log_window.is_visible()
        self.tray_menu.update_state(
            state is not LukerState.STOPPED,
            window_visible,
            state,
        )
        self.tray_menu.show_at(x, y, previous_foreground)

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
        self._process.ensure_manager()
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
            on_start=self._process.start,
            on_stop=self._process.stop,
            on_exit=self._lifecycle_coordinator.request_exit,
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
                'start': self._process.start,
                'stop': self._process.stop,
                'restart': self._process.restart,
                'settings': self._on_settings,
                'open_browser': self._browser.open,
                'exit': self._lifecycle_coordinator.exit,
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
        self._status.schedule_poll()
        return tray_ready

    def _start_first_run(self, tray_ready: bool) -> None:
        window = self.log_window
        if window is None:
            return

        self._on_log("[启动器] 正在启动 Luker...")
        self._process.start()
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
        # 与正常退出共用同一套幂等清理
        self._lifecycle_coordinator.shutdown()
