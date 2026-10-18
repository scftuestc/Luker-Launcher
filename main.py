"""Luker 启动器入口：创建日志窗口、托盘和进程管理器，并进入 Tk 主循环。"""

import ctypes
import logging
import queue
import time
import urllib.error
import urllib.request
import webbrowser
from ctypes import windll
from pathlib import Path
from threading import Thread
from typing import Callable

import customtkinter as ctk

from config import config
from dialogs import SettingsWindow, TrayMenu
from log_window import LogWindow
from path_dialogs import ensure_luker_path_configured
from process_manager import GCLProcessManager, ProcessManager
from pwa_browser import open_in_browser
from tray_icon import TrayIcon

logger = logging.getLogger(__name__)

# 轮询与等待时间（秒）
STATUS_POLL_INTERVAL = 2
BROWSER_WAIT_TIMEOUT_SECONDS = 30
BROWSER_WAIT_INTERVAL_SECONDS = 1
# 后台线程投递的 UI 操作由主线程按此间隔取走
UI_QUEUE_POLL_MS = 50


def setup_dpi_awareness() -> None:
    """从新到旧逐级尝试设置 DPI 感知，保证高分屏下坐标计算不模糊。

    DPI 感知必须在创建任何窗口之前设置，但只影响之后创建的窗口，
    所以放在 main() 里调用即可。
    """
    try:
        # Windows 10 1703+ 使用 SetProcessDpiAwarenessContext
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            # Windows 8.1+ 使用 SetProcessDpiAwareness
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                # Windows Vista+ 使用 SetProcessDPIAware
                windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                # 极老系统连这也没有，交给系统默认的 DPI 缩放处理
                pass


class LukerLauncher:
    """协调日志窗口、托盘菜单和两个进程管理器的应用主体。"""

    def __init__(self) -> None:
        self.process_manager: ProcessManager | None = None
        self.gcl_process_manager: GCLProcessManager | None = None
        self.tray_icon: TrayIcon | None = None
        self.log_window: LogWindow | None = None
        self.tray_menu: TrayMenu | None = None
        self._running = False
        self._process_busy = False  # 防止启停/重启操作重入
        self._exiting = False  # 退出流程只执行一次
        self._last_status: bool | None = None  # 上一次通知给界面的运行状态
        # 托盘/进程线程不能直接操作 Tk，统一投递到这里由主线程执行
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._ui_active = False

        # 注册 GCL 配置变更回调
        config.add_gcl_change_callback(self._on_gcl_config_change)

    def _post_ui(self, callback: Callable[[], None]) -> None:
        """从任意线程投递 UI 操作，由 Tk 主线程取出执行。"""
        self._ui_queue.put(callback)

    def _pump_ui_queue(self) -> None:
        if not self._ui_active:
            return

        try:
            while self._ui_active:
                try:
                    callback = self._ui_queue.get_nowait()
                except queue.Empty:
                    break

                try:
                    callback()
                except Exception:
                    logger.exception("界面操作执行失败")
        finally:
            if self._ui_active and self.log_window:
                self.log_window.after(UI_QUEUE_POLL_MS, self._pump_ui_queue)

    def _on_show_window(self) -> None:
        self._post_ui(self._show_window)

    def _show_window(self) -> None:
        if self.log_window:
            self.log_window.show()
        if self.tray_icon:
            self.tray_icon.set_window_visible(True)

    def _on_hide_window(self) -> None:
        self._post_ui(self._hide_window)

    def _hide_window(self) -> None:
        if self.log_window:
            self.log_window.hide()
        if self.tray_icon:
            self.tray_icon.set_window_visible(False)

    def _on_log(self, line: str) -> None:
        if self.log_window:
            self.log_window.add_log(line)

    def _on_start(self) -> None:
        self._do_process_action(lambda manager: manager.start())

    def _on_stop(self) -> None:
        self._do_process_action(lambda manager: manager.stop())

    def _on_restart(self) -> None:
        self._do_process_action(lambda manager: manager.restart())

    def _on_exit(self) -> None:
        if self._exiting:
            return
        self._exiting = True
        self._running = False

        # 停止进程可能耗时数秒，放到后台，完成后再结束主循环
        managers = [m for m in (self.process_manager, self.gcl_process_manager) if m]

        def worker():
            for manager in managers:
                manager.stop()
            self._post_ui(self._finish_exit)

        self._run_async(worker)

    def _finish_exit(self) -> None:
        self._ui_active = False
        if self.tray_icon:
            self.tray_icon.stop()
        if self.log_window:
            self.log_window.quit()

    def _run_async(self, func) -> None:
        """在守护线程中执行耗时操作，不阻塞 Tk 主循环。"""
        Thread(target=func, daemon=True).start()

    def _ensure_process_manager(self) -> ProcessManager | None:
        """确保进程管理器与当前配置的 Luker 路径保持一致。"""
        if not config.luker_path:
            return None

        path = config.luker_path
        if self.process_manager is None or str(self.process_manager.luker_path) != str(Path(path)):
            if self.process_manager and self.process_manager.is_running:
                # 运行中不热切换，避免意外中断正在工作的进程
                return self.process_manager

            self.process_manager = ProcessManager(
                path, let_luker_open_browser=not config.use_pwa_mode
            )
            self.process_manager.add_log_callback(self._on_log)
            self._last_status = None
        else:
            self.process_manager.let_luker_open_browser = not config.use_pwa_mode

        return self.process_manager

    def _do_process_action(self, action) -> None:
        """在后台线程执行进程操作，避免停止/重启时阻塞界面。"""
        if self._process_busy or self._exiting:
            return

        manager = self._ensure_process_manager()
        if manager is None:
            self._on_log("[错误] 未配置 Luker 路径")
            return

        self._process_busy = True

        def worker():
            try:
                action(manager)
            finally:
                self._post_ui(self._finish_process_action)

        self._run_async(worker)

    def _finish_process_action(self) -> None:
        self._process_busy = False
        self._update_status()

    def _on_settings(self) -> None:
        self._post_ui(self._open_settings_window)

    def _on_open_browser(self) -> None:
        """打开浏览器；PWA 发现可能调用 PowerShell，放到后台避免卡住界面。"""
        self._run_async(self._open_browser_now)

    def _open_browser_now(self) -> None:
        url = config.get_server_url()
        if config.use_pwa_mode:
            # 使用 PWA 模式打开浏览器，标题栏颜色会自动跟随 Luker 主题
            open_in_browser(url, prefer_pwa=True)
        else:
            # 使用默认浏览器
            webbrowser.open(url)

    def _open_settings_window(self) -> None:
        if self.log_window:
            settings_win = SettingsWindow(self.log_window)
            settings_win.focus_force()

    def _on_gcl_start(self) -> None:
        manager = self.gcl_process_manager
        if manager:
            self._run_async(manager.start)

    def _on_gcl_stop(self) -> None:
        manager = self.gcl_process_manager
        if manager:
            self._run_async(manager.stop)

    def _on_gcl_log(self, line: str) -> None:
        if self.log_window:
            self.log_window.add_gcl_log(line)

    def _on_gcl_config_change(self, enabled: bool, bat_path: str | None) -> None:
        """GCL 配置变更回调，动态创建或销毁 GCL 进程管理器"""
        active = bool(enabled and bat_path and config.is_valid_gcl_path(bat_path))

        if active:
            # 如果之前没有 GCL 进程管理器，或者路径变了，需要重新创建
            if self.gcl_process_manager is None or Path(self.gcl_process_manager.bat_path) != Path(bat_path):
                old_manager = self.gcl_process_manager
                if old_manager and old_manager.is_running:
                    self._run_async(old_manager.stop)

                self.gcl_process_manager = GCLProcessManager(bat_path)
                self.gcl_process_manager.add_log_callback(self._on_gcl_log)

                if self.log_window:
                    self._post_ui(lambda: self.log_window.set_gcl_enabled(True))
                self._on_log("[启动器] GCL 功能已启用")
        else:
            # 禁用 GCL，或在没有有效路径时不创建管理器
            old_manager = self.gcl_process_manager
            self.gcl_process_manager = None
            if old_manager and old_manager.is_running:
                self._run_async(old_manager.stop)

            if self.log_window:
                self._post_ui(lambda: self.log_window.set_gcl_enabled(False))
            if old_manager is not None:
                self._on_log("[启动器] GCL 功能已禁用")

    def _on_show_menu(self, x: int, y: int) -> None:
        # 托盘线程只传坐标，状态读取和菜单显示都回到主线程
        self._post_ui(lambda: self._show_tray_menu(x, y))

    def _show_tray_menu(self, x: int, y: int) -> None:
        if not (self.tray_menu and self.log_window):
            return

        is_running = self.process_manager.is_running if self.process_manager else False
        window_visible = self.log_window.is_visible()
        gcl_enabled = self.gcl_process_manager is not None
        gcl_running = self.gcl_process_manager.is_running if self.gcl_process_manager else False
        self.tray_menu.update_state(is_running, window_visible, gcl_enabled, gcl_running)
        self.tray_menu.show_at(x, y)

    def _update_status(self) -> None:
        if not self.process_manager:
            return
        is_running = self.process_manager.is_running
        # 状态未变化时不重复更新图标和标签
        if is_running == self._last_status:
            return
        self._last_status = is_running
        if self.tray_icon:
            self.tray_icon.update_status(is_running)
        if self.log_window:
            self.log_window.update_status(is_running)

    def _schedule_status_poll(self) -> None:
        """在 Tk 主线程按固定间隔检查进程状态，不再单独占用监控线程。"""
        if not self._running:
            return

        self._update_status()
        if self.log_window:
            self.log_window.after(STATUS_POLL_INTERVAL * 1000, self._schedule_status_poll)

    def run(self) -> None:
        """
        依次创建四大组件，最后进入 GUI 主循环。

        本方法运行在 GUI 主线程上（由底部的 mainloop() 接管）。
        线程全景：GUI 主线程 / 托盘消息循环线程 / stdout 读取线程 / 浏览器等待线程。
        所有跨线程 UI 操作都通过 _ui_queue 投递，由主线程的 _pump_ui_queue 执行；
        进程状态也在主线程用 after 定时检查。
        """
        # 首次运行检查：配置缺失时弹对话框引导用户选择 Luker 路径，
        # 选不出来就放弃启动。配置读写的实现在 config.py，全局单例。
        if not ensure_luker_path_configured():
            print("未配置 Luker 路径，程序退出")
            return

        # 创建主窗口（log_window.py，最大的模块）。
        # on_hide_callback / on_start / on_stop 都是回调注入
        self.log_window = LogWindow(
            on_hide_callback=lambda: self.tray_icon.set_window_visible(False) if self.tray_icon else None,
            on_start=self._on_start,
            on_stop=self._on_stop
        )

        # 启动主线程 UI 队列泵，之后后台线程可以安全地请求界面操作
        self._ui_active = True
        self._pump_ui_queue()

        # 创建进程管理器（process_manager.py）。
        # let_luker_open_browser：PWA 模式下要禁止 Luker 自己开浏览器，
        # 改由启动器打开 PWA 窗口。设置里修改路径后可自动重建。
        self._ensure_process_manager()

        # 创建托盘弹出菜单（dialogs.py 的 TrayMenu）。
        self.tray_menu = TrayMenu(self.log_window, {
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
        })

        # 初始化 GCL 进程管理器（如果启用且路径有效）
        if config.gcl_enabled and config.gcl_bat_path and config.is_valid_gcl_path(config.gcl_bat_path):
            self.gcl_process_manager = GCLProcessManager(config.gcl_bat_path)
            self.gcl_process_manager.add_log_callback(self._on_gcl_log)
            self.log_window.set_gcl_enabled(True)
        else:
            self.log_window.set_gcl_enabled(False)

        # 创建托盘图标；启动/停止/重启等操作都通过右键菜单完成
        self.tray_icon = TrayIcon(
            on_show_window=self._on_show_window,
            on_hide_window=self._on_hide_window,
            on_show_menu=self._on_show_menu,
        )

        # 设置运行标志，供自动打开浏览器和状态轮询使用
        self._running = True

        # 托盘线程在此启动：内部跑 Windows 消息循环 GetMessageW，
        # 会永久阻塞等消息，所以必须独立线程（run_detached = 分离线程运行）。
        self.tray_icon.run_detached()

        # 状态检查改为 Tk 主线程的 after 定时任务
        self._schedule_status_poll()

        self._on_log("[启动器] 正在启动 Luker...")
        self._on_start()
        # 隐藏主窗口，只保留系统托盘图标。
        self.log_window.hide()
        self._on_log("[启动器] 已最小化到系统托盘，单击图标可显示日志窗口")

        # 如果 GCL 已启用，显示提示
        if self.gcl_process_manager:
            self._on_log("[启动器] GCL 功能已启用，可通过右键菜单控制")

        # 如果开启了 PWA 模式，等待 Luker 启动后自动打开浏览器
        if config.use_pwa_mode:
            self._schedule_auto_open_browser()

        # 进入 Tk GUI 主循环。
        self.log_window.mainloop()

        # 主循环退出后做最后清理；正常退出时 _finish_exit 已处理过，这里是幂等的
        self._ui_active = False
        self._running = False
        if self.tray_icon:
            self.tray_icon.stop()

    def _schedule_auto_open_browser(self) -> None:
        """延迟打开浏览器，等待 Luker 服务启动"""
        def check_and_open():
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
                    # 当前已在后台线程中，直接打开即可
                    self._open_browser_now()
                    return

                time.sleep(BROWSER_WAIT_INTERVAL_SECONDS)

            if self._running:
                self._on_log("[启动器] 等待 Luker 启动超时，请手动打开浏览器")

        # 在后台线程中执行检查
        Thread(target=check_and_open, daemon=True).start()


def main() -> None:
    # import 阶段不碰任何窗口系统，进入 main() 才正式初始化 GUI 相关设置
    setup_dpi_awareness()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    launcher = LukerLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
