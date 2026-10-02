import time
from threading import Thread
from typing import Optional
import ctypes
from ctypes import windll

# 在任何 GUI 初始化之前设置 DPI 感知模式
# 这确保所有坐标计算使用正确的 DPI 缩放
def setup_dpi_awareness():
    try:
        # Windows 10 1703+ 使用 SetProcessDpiAwarenessContext
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            # Windows 8.1+ 使用 SetProcessDpiAwareness
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # Windows Vista+ 使用 SetProcessDPIAware
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass

setup_dpi_awareness()

import customtkinter as ctk

from config import config
from process_manager import ProcessManager, GCLProcessManager
from tray_icon import TrayIcon
from log_window import LogWindow
import webbrowser
from dialogs import TrayMenu, SettingsWindow
from pwa_browser import open_in_browser

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class LukerLauncher:
    def __init__(self):
        self.process_manager: Optional[ProcessManager] = None
        self.gcl_process_manager: Optional[GCLProcessManager] = None
        self.tray_icon: Optional[TrayIcon] = None
        self.log_window: Optional[LogWindow] = None
        self.tray_menu: Optional[TrayMenu] = None
        self._running = False

        # 注册 GCL 配置变更回调
        config.add_gcl_change_callback(self._on_gcl_config_change)

    def _on_show_window(self) -> None:
        if self.log_window:
            self.log_window.after(0, self.log_window.show)
        if self.tray_icon:
            self.tray_icon.set_window_visible(True)

    def _on_hide_window(self) -> None:
        if self.log_window:
            self.log_window.after(0, self.log_window.hide)
        if self.tray_icon:
            self.tray_icon.set_window_visible(False)

    def _on_log(self, line: str) -> None:
        if self.log_window:
            self.log_window.add_log(line)

    def _on_start(self) -> None:
        if self.process_manager:
            self.process_manager.start()
            self._update_status()

    def _on_stop(self) -> None:
        if self.process_manager:
            self.process_manager.stop()
            self._update_status()

    def _on_restart(self) -> None:
        if self.process_manager:
            self.process_manager.restart()
            self._update_status()

    def _on_exit(self) -> None:
        self._running = False
        if self.process_manager:
            self.process_manager.stop()
        if self.gcl_process_manager:
            self.gcl_process_manager.stop()
        if self.log_window:
            self.log_window.after(0, self.log_window.quit)

    def _on_settings(self) -> None:
        if self.log_window:
            self.log_window.after(0, self._open_settings_window)

    def _on_open_browser(self) -> None:
        """打开浏览器，根据配置决定使用 PWA 模式还是默认浏览器"""
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
        if self.gcl_process_manager:
            self.gcl_process_manager.start()
            self._update_status()

    def _on_gcl_stop(self) -> None:
        if self.gcl_process_manager:
            self.gcl_process_manager.stop()
            self._update_status()

    def _on_gcl_log(self, line: str) -> None:
        if self.log_window:
            self.log_window.add_gcl_log(line)

    def _on_gcl_config_change(self, enabled: bool, bat_path: Optional[str]) -> None:
        """GCL 配置变更回调，动态创建或销毁 GCL 进程管理器"""
        if enabled and bat_path:
            # 如果之前没有 GCL 进程管理器，或者路径变了，需要重新创建
            if self.gcl_process_manager is None or str(self.gcl_process_manager.bat_path) != bat_path:
                # 如果有旧的进程管理器且正在运行，先停止
                if self.gcl_process_manager and self.gcl_process_manager.is_running:
                    self.gcl_process_manager.stop()

                # 创建新的 GCL 进程管理器
                self.gcl_process_manager = GCLProcessManager(bat_path)
                self.gcl_process_manager.add_log_callback(self._on_gcl_log)

                if self.log_window:
                    self.log_window.after(0, lambda: self.log_window.set_gcl_enabled(True))
                    self._on_log("[启动器] GCL 功能已启用")
        else:
            # 禁用 GCL
            if self.gcl_process_manager:
                if self.gcl_process_manager.is_running:
                    self.gcl_process_manager.stop()
                self.gcl_process_manager = None

            if self.log_window:
                self.log_window.after(0, lambda: self.log_window.set_gcl_enabled(False))
                self._on_log("[启动器] GCL 功能已禁用")

    def _on_show_menu(self, x: int, y: int) -> None:
        if self.tray_menu and self.log_window:
            is_running = self.process_manager.is_running if self.process_manager else False
            window_visible = self.log_window.is_visible()
            gcl_enabled = config.gcl_enabled
            gcl_running = self.gcl_process_manager.is_running if self.gcl_process_manager else False
            self.log_window.after(0, lambda: self._show_tray_menu(x, y, is_running, window_visible, gcl_enabled, gcl_running))

    def _show_tray_menu(self, x: int, y: int, is_running: bool, window_visible: bool, gcl_enabled: bool = False, gcl_running: bool = False):
        if self.tray_menu:
            self.tray_menu.update_state(is_running, window_visible, gcl_enabled, gcl_running)
            self.tray_menu.show_at(x, y)

    def _update_status(self) -> None:
        if self.process_manager:
            is_running = self.process_manager.is_running
            if self.tray_icon:
                self.tray_icon.update_status(is_running)
            if self.log_window:
                self.log_window.after(0, lambda: self.log_window.update_status(is_running))

    def _status_monitor(self) -> None:
        while self._running:
            self._update_status()
            time.sleep(2)

    def run(self) -> None:
        if not config.ensure_path_configured():
            print("未配置 Luker 路径，程序退出")
            return

        self.log_window = LogWindow(
            on_hide_callback=lambda: self.tray_icon.set_window_visible(False) if self.tray_icon else None,
            on_start=self._on_start,
            on_stop=self._on_stop
        )

        # 如果开启了 PWA 模式，禁止 Luker 自动打开浏览器（由启动器来打开 PWA）
        autorun = not config.use_pwa_mode
        self.process_manager = ProcessManager(config.luker_path, autorun=autorun)
        self.process_manager.add_log_callback(self._on_log)

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

        # 初始化 GCL 进程管理器（如果启用且路径已配置）
        if config.gcl_enabled and config.gcl_bat_path:
            self.gcl_process_manager = GCLProcessManager(config.gcl_bat_path)
            self.gcl_process_manager.add_log_callback(self._on_gcl_log)
            self.log_window.set_gcl_enabled(True)
        else:
            self.log_window.set_gcl_enabled(False)

        self.tray_icon = TrayIcon(
            on_show_window=self._on_show_window,
            on_hide_window=self._on_hide_window,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_restart=self._on_restart,
            on_exit=self._on_exit,
            on_settings=self._on_settings,
            on_show_menu=self._on_show_menu,
        )

        self._running = True

        monitor_thread = Thread(target=self._status_monitor, daemon=True)
        monitor_thread.start()

        self.tray_icon.run_detached()

        self._on_log("[启动器] 正在启动 Luker...")
        self._on_start()

        self.log_window.hide()
        self._on_log("[启动器] 已最小化到系统托盘，单击图标可显示日志窗口")

        # 如果 GCL 已启用，显示提示
        if config.gcl_enabled:
            self._on_log("[启动器] GCL 功能已启用，可通过右键菜单控制")

        # 如果开启了 PWA 模式，等待 Luker 启动后自动打开浏览器
        if config.use_pwa_mode:
            self._schedule_auto_open_browser()

        self.log_window.mainloop()

    def _schedule_auto_open_browser(self) -> None:
        """延迟打开浏览器，等待 Luker 服务启动"""
        def check_and_open():
            import urllib.request
            import urllib.error

            url = config.get_server_url()
            max_attempts = 30  # 最多等待 30 秒
            attempt = 0

            while attempt < max_attempts and self._running:
                try:
                    # 尝试连接 Luker
                    urllib.request.urlopen(url, timeout=1)
                    # 连接成功，打开浏览器
                    self._on_log("[启动器] 检测到 Luker 已启动，正在打开 PWA 浏览器...")
                    self._on_open_browser()
                    return
                except (urllib.error.URLError, TimeoutError):
                    # 连接失败，等待后重试
                    attempt += 1
                    time.sleep(1)

            if self._running:
                self._on_log("[启动器] 等待 Luker 启动超时，请手动打开浏览器")

        # 在后台线程中执行检查
        Thread(target=check_and_open, daemon=True).start()


def main():
    launcher = LukerLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
