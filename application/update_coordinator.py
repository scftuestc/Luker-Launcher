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
    UpdateProgress,
    UpdateResult,
    UpdateTarget,
    VersionCheck,
    apply_luker_update,
    check_luker_versions,
    read_local_version,
    same_path,
)
from process.managers import LukerProcessManager

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
        apply_update: Callable[..., UpdateResult] = apply_luker_update,
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
        self.apply_update = apply_update
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

    def post_update_progress(
        self,
        window: SettingsView,
        progress: UpdateProgress,
    ) -> None:
        # 更新阶段数量很少，统一走 control 队列：
        # 普通合并队列会在最终结果之后才执行旧的阶段回调，覆盖完成状态。
        self.post_ui.post_control(lambda: self.deliver_update_progress(window, progress))

    def deliver_update_progress(
        self,
        window: SettingsView,
        progress: UpdateProgress,
    ) -> None:
        current = self.settings_provider()
        if current is window and window.is_alive():
            window.set_update_progress(progress)

    @staticmethod
    def start_luker_safely(manager: LukerProcessManager) -> str | None:
        """启动 Luker；返回 None 表示成功，否则返回可展示的失败原因。"""
        try:
            return None if manager.start() else "启动失败"
        except Exception as error:
            logger.exception("更新后启动 Luker 失败")
            return f"启动异常：{error}"

    def apply_update_target(self, target: UpdateTarget) -> bool:
        """停止 Luker、切换版本、安装依赖并按原状态重启。"""
        if self.updating or self.process.busy or self.checking or self.lifecycle.exiting:
            return False
        window = self.settings_provider()
        if window is None:
            return False

        manager = self.process.ensure_manager()
        if manager is None:
            self.post_update_progress(
                window,
                UpdateProgress("error", "未配置 Luker 路径", "error", False),
            )
            return False

        configured_path = self.config.luker_path
        if (
            manager.is_running
            and configured_path
            and not same_path(str(manager.luker_path), configured_path)
        ):
            self.post_update_progress(
                window,
                UpdateProgress(
                    "error",
                    "Luker 路径已更改，请先重启应用新路径",
                    "warning",
                    False,
                ),
            )
            return False

        active_manager = manager
        was_running = manager.is_running
        self.updating = True
        self.version_check_cache = None
        self.version_check_seq += 1

        def worker() -> None:
            try:
                self.post_update_progress(
                    window,
                    UpdateProgress("checking", "正在检查更新条件...", "info", True),
                )
                local = self.read_local(str(active_manager.luker_path))
                if local.error:
                    message = local.error
                    self.log(f"[错误] {message}")
                    self.post_update_progress(
                        window,
                        UpdateProgress("error", message, "error", False),
                    )
                    return
                if not local.npm_available:
                    message = "未找到 npm，无法安装依赖"
                    self.log(f"[错误] {message}")
                    self.post_update_progress(
                        window,
                        UpdateProgress("error", message, "error", False),
                    )
                    return
                if local.dirty:
                    message = "检测到未提交的修改，已取消更新"
                    self.log(f"[警告] {message}")
                    self.post_update_progress(
                        window,
                        UpdateProgress("error", message, "warning", False),
                    )
                    return

                if was_running:
                    self.log("[启动器] 正在停止 Luker 以更新版本...")
                    self.post_update_progress(
                        window,
                        UpdateProgress("stopping", "正在停止 Luker...", "info", True),
                    )
                    self.status.reset()
                    if not active_manager.stop():
                        message = "Luker 未能完全停止，已取消更新"
                        self.log(f"[错误] {message}")
                        self.post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                        )
                        return

                def on_stage(stage: str, message: str) -> None:
                    self.post_update_progress(
                        window,
                        UpdateProgress(stage, message, "info", True),
                    )
                    self.log(f"[启动器] {message}")

                result = self.apply_update(
                    str(active_manager.luker_path),
                    target,
                    on_stage=on_stage,
                )

                if result.success:
                    if not was_running:
                        message = f"{result.message}；Luker 未运行，未自动启动"
                        self.log(f"[启动器] {message}")
                        self.post_update_progress(
                            window,
                            UpdateProgress("done", message, "success", False),
                        )
                        return

                    self.post_update_progress(
                        window,
                        UpdateProgress("restarting", "正在重启 Luker...", "info", True),
                    )
                    start_error = self.start_luker_safely(active_manager)
                    if start_error is not None:
                        message = f"{result.message}，但 Luker {start_error}，请手动启动"
                        self.log(f"[错误] {message}")
                        self.post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                        )
                        return
                    message = f"{result.message}，Luker 已重启"
                    self.log(f"[启动器] {message}")
                    self.post_update_progress(
                        window,
                        UpdateProgress("done", message, "success", False),
                    )
                    return

                if was_running:
                    if result.code_changed and not result.rolled_back:
                        message = f"{result.message}；自动回滚失败，未自动启动 Luker，请手动检查"
                        self.log(f"[错误] {message}")
                        self.post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                        )
                        return

                    self.post_update_progress(
                        window,
                        UpdateProgress("restarting", "正在恢复原版本...", "warning", True),
                    )
                    start_error = self.start_luker_safely(active_manager)
                    if start_error is not None:
                        message = f"{result.message}；原版本{start_error}，请手动启动"
                        self.log(f"[错误] {message}")
                        self.post_update_progress(
                            window,
                            UpdateProgress("error", message, "error", False),
                        )
                        return

                self.log(f"[错误] {result.message}")
                self.post_update_progress(
                    window,
                    UpdateProgress("error", result.message, "error", False),
                )
            except Exception as error:
                logger.exception("更新 Luker 失败")
                message = f"更新 Luker 失败：{error}"
                self.log(f"[错误] {message}")
                self.post_update_progress(
                    window,
                    UpdateProgress("error", message, "error", False),
                )
            finally:
                self.updating = False
                if not self.post_ui.post_control(self.process.finish_action):
                    self.process.busy = False

        if not self.process.start_worker(
            worker,
            context="Luker 更新",
            on_failure=lambda: self.post_update_progress(
                window,
                UpdateProgress("error", "无法启动更新线程", "error", False),
            ),
        ):
            self.updating = False
            return False
        return True
