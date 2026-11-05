"""Coordinator 之间共享的退出状态。"""

from dataclasses import dataclass


@dataclass
class LifecycleState:
    """Lifecycle 写入，其余 Coordinator 只读。"""

    exiting: bool = False
