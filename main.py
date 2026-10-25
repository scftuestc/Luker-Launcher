"""Luker 启动器入口：初始化 DPI、单实例和 Tk 主循环。"""

import contextlib
import ctypes
import logging
from ctypes import windll

import customtkinter as ctk

import app_logging
import single_instance
from config import APP_VERSION
from launcher_app import LukerLauncher
from ui.dpi import get_process_dpi_awareness

logger = logging.getLogger(__name__)


def setup_dpi_awareness() -> None:
    """在创建任何窗口前启用 DPI 感知，保证高分屏下坐标计算正确。"""
    try:
        # Windows 10 1703+ 使用 SetProcessDpiAwarenessContext
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            _log_dpi_awareness()
            return
    except (AttributeError, OSError):
        pass

    try:
        # Windows 8.1+ 使用 SetProcessDpiAwareness
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        if windll.shcore.SetProcessDpiAwareness(2) == 0:
            _log_dpi_awareness()
            return
    except (AttributeError, OSError):
        pass

    # Windows Vista+ 使用 SetProcessDPIAware；极老系统交给默认缩放
    with contextlib.suppress(AttributeError, OSError):
        windll.user32.SetProcessDPIAware()
    _log_dpi_awareness()


def _log_dpi_awareness() -> None:
    awareness = get_process_dpi_awareness()
    if awareness == 2:
        logger.info("DPI 感知模式: Per-Monitor")
    elif awareness == 1:
        logger.warning("DPI 感知模式: System（混合 DPI 下窗口可能偏移）")
    elif awareness == 0:
        logger.warning("DPI 感知模式: Unaware（高分屏可能缩放异常）")
    else:
        logger.warning("无法读取 DPI 感知模式")


def main() -> None:
    # import 阶段不碰任何窗口系统，进入 main() 才正式初始化 GUI 相关设置
    app_logging.setup_logging()
    logger.info("Luker Launcher v%s 启动", APP_VERSION)

    setup_dpi_awareness()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    # 同一会话只允许一个启动器，避免两个托盘和两个 node 抢同一端口
    if not single_instance.acquire():
        windll.user32.MessageBoxW(
            None,
            "Luker 启动器已在运行。\n请从系统托盘图标打开。",
            "Luker 启动器",
            0x00000040 | 0x00040000,  # MB_ICONINFORMATION | MB_TOPMOST
        )
        return

    try:
        launcher = LukerLauncher()
        launcher.run()
    finally:
        single_instance.release()


if __name__ == "__main__":
    main()
