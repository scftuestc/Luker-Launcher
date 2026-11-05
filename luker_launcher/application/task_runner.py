"""后台任务线程的创建入口，便于测试注入同步实现。"""

import logging
from collections.abc import Callable
from threading import Thread

logger = logging.getLogger(__name__)


class TaskRunner:
    """在守护线程中执行一次性任务；线程创建失败时返回 False。"""

    def run(self, func: Callable[[], None], *, name: str | None = None) -> bool:
        try:
            Thread(target=func, daemon=True, name=name).start()
        except Exception:
            logger.exception("启动后台任务线程失败")
            return False
        return True
