"""Luker 版本检查与更新协调。"""

import logging
from collections.abc import Callable
from typing import Protocol

from application.lifecycle_state import LifecycleState
from application.process_coordinator import ProcessCoordinator
from application.protocols import LogSink, SettingsView, UiPoster
from application.status_coordinator import StatusCoordinator
from application.task_runner import TaskRunner
from core.version import (
    LocalVersion,
    VersionCheck,
    check_luker_versions,
    read_local_version,
    same_path,
)

logger = logging.getLogger(__name__)


class UpdateConfig(Protocol):
    """更新协调需要的配置能力。"""

    @property
    def luker_path(self) -> str | None: ...


class UpdateCoordinator:
    """管理版本检查缓存、请求序号和检查结果投递。"""

    def __init__(
        self,
        *,
        config: UpdateConfig,
        process: ProcessCoordinator,
        status: StatusCoordinator,
        task_runner: TaskRunner,
        post_ui: UiPoster,
        log: LogSink,
        lifecycle: LifecycleState,
        settings_provider: Callable[[], SettingsView | None],
        check_versions: Callable[..., VersionCheck] = check_luker_versions,
        read_local: Callable[..., LocalVersion] = read_local_version,
    ) -> None:
        self.config = config
        self.process = process
        self.status = status
        self.task_runner = task_runner
        self.post_ui = post_ui
        self.log = log
        self.lifecycle = lifecycle
        self.settings_provider = settings_provider
        self.check_versions = check_versions
        self.read_local = read_local
        self.checking = False
        self.updating = False
        self.version_check_cache: VersionCheck | None = None
        self.version_check_seq = 0

    def path_changed(self) -> None:
        """路径变更后丢弃旧路径的检查结果和进行中的请求。"""
        self.version_check_seq += 1
        self.version_check_cache = None
        self.checking = False

    def request_check(self) -> bool:
        """在后台检查本地版本、最新发行版和最新提交。"""
        if self.checking or self.updating or self.lifecycle.exiting:
            return False
        window = self.settings_provider()
        if window is None:
            return False

        repo_path = self.config.luker_path
        manager = self.process.manager
        running_path = (
            str(manager.luker_path) if manager is not None and manager.is_running else None
        )
        self.checking = True
        self.version_check_seq += 1
        seq = self.version_check_seq
        self.log("[启动器] 正在检查 Luker 版本...")
        failed = False

        def worker() -> None:
            nonlocal failed
            try:
                result = self.check_versions(repo_path, running_path=running_path)
            except Exception as error:
                failed = True
                logger.exception("检查 Luker 版本失败：%s", error)
                local = self.read_local(repo_path, running_path=running_path)
                result = VersionCheck(
                    repo_path=local.repo_path,
                    local=local,
                    release=None,
                    commit=None,
                    error=f"检查版本失败：{error}",
                )
            finally:
                if seq == self.version_check_seq:
                    self.checking = False
            if not failed:
                self.log_check(result)
            self.post_ui.post_control(lambda: self.deliver_check(result, seq))

        if not self.task_runner.run(worker):
            self.checking = False
            logger.error("启动 Luker 版本检查线程失败")
            return False
        return True

    def deliver_check(self, result: VersionCheck, seq: int) -> None:
        if seq != self.version_check_seq:
            return
        current_path = self.config.luker_path
        if not current_path or not same_path(result.repo_path, current_path):
            return
        if result.release is not None or result.commit is not None:
            self.version_check_cache = result
        window = self.settings_provider()
        if window is not None and window.is_alive():
            window.set_version_check(result)

    def log_check(self, result: VersionCheck) -> None:
        """把检查结果显示到日志窗口。"""
        local = result.local
        if not local.error:
            head = local.head or local.short_head
            parts = []
            if local.current_tag:
                parts.append(f"Tag {local.current_tag}")
            if head:
                parts.append(f"提交 {head}")
            if local.date:
                parts.append(local.date)
            if parts:
                self.log(f"[启动器] 当前版本：{' · '.join(parts)}")

        release = result.release
        if release is not None:
            self.log(
                f"[启动器] 最新发行版：{release.tag or release.label} · "
                f"发布于 {release.published_at or '未知'} · 提交 {release.commit.sha}"
            )

        commit = result.commit
        if commit is not None:
            self.log(f"[启动器] 最新提交：{commit.commit.date or '未知'} · {commit.commit.sha}")

        if result.error:
            has_target = release is not None or commit is not None
            self.log(f"[{'警告' if has_target else '错误'}] {result.error}")
