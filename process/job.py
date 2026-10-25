"""把子进程放入启用 KILL_ON_JOB_CLOSE 的 Windows Job Object。

启动器被任务管理器结束或异常退出时，Windows 会随 Job 句柄关闭终止其中的
所有进程，避免 node/GCL 继续占用端口变成孤儿进程。
"""

import ctypes
import logging
import subprocess
from ctypes import wintypes

logger = logging.getLogger(__name__)

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
_kernel32.CreateJobObjectW.restype = wintypes.HANDLE
_kernel32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
]
_kernel32.SetInformationJobObject.restype = wintypes.BOOL
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
_kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_job_handle: int | None = None


def _get_job_handle() -> int | None:
    """懒创建全局 Job Object；句柄随启动器进程生命周期存在。"""
    global _job_handle

    if _job_handle is not None:
        return _job_handle

    handle = _kernel32.CreateJobObjectW(None, None)
    if not handle:
        logger.warning("创建 Job Object 失败: %s", ctypes.get_last_error())
        return None

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not _kernel32.SetInformationJobObject(
        handle,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        logger.warning("设置 Job Object 失败: %s", ctypes.get_last_error())
        _kernel32.CloseHandle(handle)
        return None

    _job_handle = handle
    return _job_handle


def assign_to_job(process: subprocess.Popen[str]) -> bool:
    """把 Popen 子进程加入 Job；失败时返回 False，调用方可继续运行。"""
    job = _get_job_handle()
    if not job:
        return False

    process_handle = _kernel32.OpenProcess(
        PROCESS_SET_QUOTA | PROCESS_TERMINATE,
        False,
        process.pid,
    )
    if not process_handle:
        logger.warning(
            "打开子进程句柄失败 (PID %s): %s",
            process.pid,
            ctypes.get_last_error(),
        )
        return False

    try:
        if not _kernel32.AssignProcessToJobObject(job, process_handle):
            logger.warning(
                "将子进程加入 Job Object 失败 (PID %s): %s",
                process.pid,
                ctypes.get_last_error(),
            )
            return False
        return True
    finally:
        _kernel32.CloseHandle(process_handle)
