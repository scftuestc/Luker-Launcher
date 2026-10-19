"""应用文件日志：windowed exe 没有控制台，内部错误需要写入 launcher.log。"""

import logging
import sys
import tempfile
import threading
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from config import get_app_dir

logger = logging.getLogger(__name__)

LOG_FILE_NAME = "launcher.log"
_MAX_LOG_BYTES = 1_000_000
_BACKUP_COUNT = 2

_configured = False
_ui_handler: logging.Handler | None = None


class _UiLogHandler(logging.Handler):
    """把 WARNING 及以上日志转发到日志窗口；回调内部自行保证线程安全。"""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__(level=logging.WARNING)
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            label = "错误" if record.levelno >= logging.ERROR else "警告"
            self._callback(f"[{label}] {record.getMessage()}")
        except Exception:
            self.handleError(record)


def _excepthook(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    logger.critical("未捕获异常", exc_info=(exc_type, exc, tb))
    sys.__excepthook__(exc_type, exc, tb)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    logger.critical(
        "线程 %s 未捕获异常",
        args.thread.name if args.thread else "?",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    threading.__excepthook__(args)


def setup_logging() -> None:
    """初始化文件日志和全局异常钩子；重复调用无副作用。"""
    global _configured
    if _configured:
        return

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    handler: logging.Handler
    log_path: Path | None = None
    for directory in (get_app_dir(), Path(tempfile.gettempdir())):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            log_path = directory / LOG_FILE_NAME
            handler = RotatingFileHandler(
                log_path,
                maxBytes=_MAX_LOG_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding='utf-8',
            )
            break
        except OSError:
            continue
    else:
        handler = logging.StreamHandler()
        log_path = None

    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _configured = True

    if log_path is not None:
        logger.info("日志文件: %s", log_path)

    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


def add_ui_log_sink(callback: Callable[[str], None]) -> None:
    """把警告/错误同步到日志窗口，方便用户直接看到内部错误。"""
    global _ui_handler
    if _ui_handler is not None:
        return

    _ui_handler = _UiLogHandler(callback)
    logging.getLogger().addHandler(_ui_handler)
