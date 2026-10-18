"""单实例保护：同一个 Windows 会话只允许运行一个启动器。"""

import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\LukerLauncher.SingleInstance"

_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_mutex_handle = None


def acquire() -> bool:
    """获取单实例互斥体；已有实例时返回 False。"""
    global _mutex_handle

    if _mutex_handle:
        return True

    handle = _kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        # 创建失败时放行，不能因为系统限制而阻止用户使用启动器
        logger.warning("创建单实例互斥体失败: %s", ctypes.get_last_error())
        return True

    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return False

    _mutex_handle = handle
    return True


def release() -> None:
    """进程退出前释放互斥体。"""
    global _mutex_handle

    if _mutex_handle:
        _kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None
