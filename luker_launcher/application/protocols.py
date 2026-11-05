"""跨 Coordinator 的最小协议定义。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from luker_launcher.services.version import UpdateProgress, VersionCheck

LogSink = Callable[[str], None]


class UiPoster(Protocol):
    """把回调投递到 Tk 主线程。"""

    def post(self, callback: Callable[[], None], coalesce_key: str | None = None) -> bool: ...

    def post_control(self, callback: Callable[[], None]) -> bool: ...


class SettingsView(Protocol):
    """更新流程需要的设置窗口能力。"""

    def is_alive(self) -> bool: ...

    def set_version_check(self, check: VersionCheck) -> None: ...

    def set_update_progress(self, progress: UpdateProgress) -> None: ...
