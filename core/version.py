"""Luker 版本检查与 Git 更新。

只负责 Git、GitHub API 和 npm，不操作 Tk，也不负责启动/停止 Luker。
"""

import contextlib
import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import psutil

logger = logging.getLogger(__name__)

LUKER_REPO = "funnycups/Luker"
API_ROOT = f"https://api.github.com/repos/{LUKER_REPO}"
USER_AGENT = "Luker-Launcher"
GITHUB_TIMEOUT = 8
GIT_TIMEOUT = 60
GIT_FETCH_TIMEOUT = 120
NPM_TIMEOUT = 600
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
NPM_INSTALL_ARGS = (
    "install",
    "--no-save",
    "--no-audit",
    "--no-fund",
    "--loglevel=error",
    "--no-progress",
    "--omit=dev",
    "--ignore-scripts",
)

Relation = Literal["up_to_date", "ahead", "behind", "diverged", "unknown"]
TargetKind = Literal["release", "commit"]
ProgressLevel = Literal["info", "success", "warning", "error"]


class VersionError(Exception):
    """可转换为界面提示的版本检查/更新错误。"""


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    short_sha: str
    date: str
    subject: str


@dataclass(frozen=True)
class TargetInfo:
    kind: TargetKind
    label: str
    tag: str | None
    branch: str | None
    published_at: str
    commit: CommitInfo
    relation: Relation
    ahead: int
    behind: int
    actionable: bool
    downgrade: bool
    status: str


@dataclass(frozen=True)
class LocalVersion:
    repo_path: str
    git_available: bool
    npm_available: bool
    is_git_repo: bool
    describe: str = ""
    branch: str = ""
    head: str = ""
    short_head: str = ""
    date: str = ""
    subject: str = ""
    current_tag: str | None = None
    dirty: bool = False
    path_matches: bool = True
    error: str | None = None


@dataclass(frozen=True)
class VersionCheck:
    repo_path: str
    local: LocalVersion
    release: TargetInfo | None
    commit: TargetInfo | None
    error: str | None = None


@dataclass(frozen=True)
class UpdateTarget:
    kind: TargetKind
    label: str
    sha: str
    tag: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class UpdateProgress:
    stage: str
    message: str
    level: ProgressLevel = "info"
    busy: bool = True


@dataclass(frozen=True)
class UpdateResult:
    success: bool
    rolled_back: bool
    message: str
    code_changed: bool = False


@dataclass(frozen=True)
class _RemoteVersions:
    default_branch: str
    release_tag: str
    release_published_at: str
    release_commit: CommitInfo
    latest_commit: CommitInfo


def _cut(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            env=env,
            check=False,
        )
    except FileNotFoundError as error:
        raise VersionError(f"未找到 {command[0]}，请先安装") from error
    except subprocess.TimeoutExpired as error:
        raise VersionError(f"{command[0]} 操作超时") from error
    except OSError as error:
        raise VersionError(f"执行 {command[0]} 失败：{error}") from error


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _looks_like_proxy_error(stderr: str) -> bool:
    text = stderr.lower()
    markers = (
        "proxy",
        "could not connect",
        "failed to connect",
        "connection refused",
        "couldn't connect",
    )
    return any(marker in text for marker in markers)


def _git(
    repo: Path,
    *args: str,
    timeout: int = GIT_TIMEOUT,
    network: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = _git_env()
    result = _run(["git", "-C", str(repo), *args], timeout=timeout, env=env)
    if network and result.returncode != 0 and _looks_like_proxy_error(result.stderr):
        # 用户的 Git 代理失效时，仅对本次网络操作绕过代理，不修改全局配置
        env = _git_env()
        result = _run(
            ["git", "-c", "http.proxy=", "-c", "https.proxy=", "-C", str(repo), *args],
            timeout=timeout,
            env=env,
        )
    return result


def _git_output(repo: Path, *args: str, timeout: int = GIT_TIMEOUT, network: bool = False) -> str:
    result = _git(repo, *args, timeout=timeout, network=network)
    if result.returncode != 0:
        detail = _cut(result.stderr or result.stdout)
        raise VersionError(f"Git 操作失败：{detail}" if detail else "Git 操作失败")
    return result.stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = _cut(result.stderr or result.stdout)
    raise VersionError(f"Git 比较提交失败：{detail}" if detail else "Git 比较提交失败")


def _count_commits(repo: Path, revision_range: str) -> int:
    try:
        return int(_git_output(repo, "rev-list", "--count", revision_range))
    except ValueError as error:
        raise VersionError("Git 提交数量格式异常") from error


def _relation(repo: Path, head: str, target: str) -> tuple[Relation, int, int]:
    if not head or not target:
        return "unknown", 0, 0
    if head == target:
        return "up_to_date", 0, 0
    try:
        if _is_ancestor(repo, target, head):
            return "ahead", _count_commits(repo, f"{target}..{head}"), 0
        if _is_ancestor(repo, head, target):
            return "behind", 0, _count_commits(repo, f"{head}..{target}")
    except VersionError:
        return "unknown", 0, 0
    return "diverged", 0, 0


def _short_sha(sha: str) -> str:
    return sha[:7] if sha else ""


def _commit_from_api(data: object) -> CommitInfo:
    if not isinstance(data, dict):
        raise VersionError("GitHub 提交数据格式异常")
    try:
        sha = str(data["sha"])
        commit = data["commit"]
        if not isinstance(commit, dict):
            raise TypeError
        date = str(commit["committer"]["date"])[:10]
        subject = str(commit["message"]).splitlines()[0]
    except (KeyError, TypeError, IndexError) as error:
        raise VersionError("GitHub 提交数据格式异常") from error
    return CommitInfo(
        sha=sha,
        short_sha=_short_sha(sha),
        date=date,
        subject=subject,
    )


def _github_payload(path: str) -> Any:
    request = urllib.request.Request(
        API_ROOT + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_TIMEOUT) as response:
            payload = response.read(MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as error:
        with contextlib.suppress(Exception):
            error.close()
        if error.code in (403, 429):
            raise VersionError("GitHub API 请求受限，请稍后再试") from error
        if error.code == 404:
            raise VersionError("GitHub 上找不到 Luker 的版本信息") from error
        raise VersionError(f"GitHub API 返回 {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise VersionError(f"无法连接 GitHub：{error}") from error

    try:
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise VersionError("GitHub API 返回了无法解析的数据") from error


def _github_json(path: str) -> dict[str, Any]:
    data = _github_payload(path)
    if not isinstance(data, dict):
        raise VersionError("GitHub API 返回了意外的数据结构")
    return data


def _github_json_list(path: str) -> list[Any]:
    data = _github_payload(path)
    if not isinstance(data, list):
        raise VersionError("GitHub API 返回了意外的数据结构")
    return data


def _fetch_remote_versions() -> _RemoteVersions:
    repo_data = _github_json("")
    default_branch = repo_data.get("default_branch") or "release"
    if not isinstance(default_branch, str):
        raise VersionError("GitHub 仓库信息缺少默认分支")

    release_data = _github_json("/releases/latest")
    release_tag = release_data.get("tag_name")
    if not isinstance(release_tag, str) or not release_tag:
        raise VersionError("GitHub 上没有可用的 Luker 发行版")
    published_at = str(release_data.get("published_at") or "")[:10]

    encoded_tag = urllib.parse.quote(release_tag, safe="")
    ref_data = _github_json(f"/git/ref/tags/{encoded_tag}")
    ref_object = ref_data.get("object")
    if not isinstance(ref_object, dict):
        raise VersionError("GitHub 标签数据格式异常")
    object_type = ref_object.get("type")
    object_sha = ref_object.get("sha")
    if not isinstance(object_sha, str):
        raise VersionError("GitHub 标签数据缺少提交")

    if object_type == "tag":
        tag_data = _github_json(f"/git/tags/{object_sha}")
        tag_target = tag_data.get("object")
        if not isinstance(tag_target, dict):
            raise VersionError("GitHub 标签目标格式异常")
        release_commit_sha = tag_target.get("sha")
        if not isinstance(release_commit_sha, str):
            raise VersionError("GitHub 标签没有指向有效提交")
    else:
        release_commit_sha = object_sha

    release_commit = _commit_from_api(_github_json(f"/commits/{release_commit_sha}"))

    encoded_branch = urllib.parse.quote(default_branch, safe="")
    latest_data = _github_json_list(f"/commits?per_page=1&sha={encoded_branch}")
    if not latest_data:
        raise VersionError("GitHub 上没有可用的 Luker 提交")
    latest_commit = _commit_from_api(latest_data[0])

    return _RemoteVersions(
        default_branch=default_branch,
        release_tag=release_tag,
        release_published_at=published_at,
        release_commit=release_commit,
        latest_commit=latest_commit,
    )


def same_path(first: str, second: str) -> bool:
    try:
        return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))
    except OSError:
        return first == second


def _npm_executable() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


def read_local_version(
    repo_path: str | None,
    running_path: str | None = None,
) -> LocalVersion:
    """读取本地 Luker 的 Git 信息；不访问网络。"""
    path = Path(repo_path) if repo_path else None
    git_available = shutil.which("git") is not None
    npm_available = _npm_executable() is not None
    is_git_repo = bool(path is not None and path.is_dir() and (path / ".git").exists())
    path_matches = running_path is None or not repo_path or same_path(repo_path, running_path)
    local = LocalVersion(
        repo_path=str(path) if path is not None else "",
        git_available=git_available,
        npm_available=npm_available,
        is_git_repo=is_git_repo,
        path_matches=path_matches,
    )

    if not repo_path:
        return replace(local, error="未配置 Luker 路径")
    if path is None or not path.is_dir():
        return replace(local, error="Luker 路径不存在")
    if not git_available:
        return replace(local, error="未找到 Git，请先安装 Git")
    if not is_git_repo:
        return replace(local, error="当前 Luker 目录不是 Git 仓库")

    try:
        head = _git_output(path, "rev-parse", "HEAD")
        short_head = _git_output(path, "rev-parse", "--short", "HEAD")
        try:
            describe = _git_output(path, "describe", "--tags", "--always", "--dirty")
        except VersionError:
            describe = short_head
        branch = _git_output(path, "rev-parse", "--abbrev-ref", "HEAD")
        date = _git_output(path, "log", "-1", "--format=%ci")[:10]
        subject = _git_output(path, "log", "-1", "--format=%s")
        tags = _git_output(path, "tag", "--points-at", "HEAD").splitlines()
        status = _git_output(path, "status", "--porcelain", "--untracked-files=no")
    except VersionError as error:
        return replace(local, error=str(error))

    return replace(
        local,
        describe=describe,
        branch=branch,
        head=head,
        short_head=short_head,
        date=date,
        subject=subject,
        current_tag=", ".join(tags) if tags else None,
        dirty=bool(status.strip()),
    )


def _blockers(local: LocalVersion, git_error: str | None, relation: Relation) -> list[str]:
    blockers: list[str] = []
    if local.dirty:
        blockers.append("工作区有未提交的修改")
    if not local.npm_available:
        blockers.append("未找到 npm，无法安装依赖")
    if not local.path_matches:
        blockers.append("Luker 路径已更改，请先重启应用新路径")
    if git_error:
        blockers.append("Git 更新失败")
    if relation == "unknown" and not git_error:
        blockers.append("无法比较本地与目标提交")
    return blockers


def _release_target(
    local: LocalVersion,
    remote: _RemoteVersions,
    relation: Relation,
    ahead: int,
    behind: int,
    git_error: str | None,
) -> TargetInfo:
    tag = remote.release_tag
    if relation == "up_to_date":
        status = f"已是最新发行版 {tag}"
        base_actionable = False
    elif relation == "ahead":
        status = f"当前已包含最新发行版 {tag}（领先 {ahead} 个提交），更新会回退"
        base_actionable = True
    elif relation == "behind":
        status = f"有新发行版 {tag} 可用，目前落后 {behind} 个提交"
        base_actionable = True
    elif relation == "diverged":
        status = f"当前提交与最新发行版 {tag} 不在同一历史线"
        base_actionable = False
    else:
        status = f"无法比较本地与最新发行版 {tag}"
        base_actionable = False

    blockers = _blockers(local, git_error, relation)
    if blockers:
        status = f"{status}；{'；'.join(blockers)}"

    return TargetInfo(
        kind="release",
        label=tag,
        tag=tag,
        branch=None,
        published_at=remote.release_published_at,
        commit=remote.release_commit,
        relation=relation,
        ahead=ahead,
        behind=behind,
        actionable=base_actionable and not blockers,
        downgrade=relation == "ahead",
        status=status,
    )


def _commit_target(
    local: LocalVersion,
    remote: _RemoteVersions,
    relation: Relation,
    ahead: int,
    behind: int,
    git_error: str | None,
) -> TargetInfo:
    short = remote.latest_commit.short_sha
    if relation == "up_to_date":
        status = f"已是最新提交 {short}"
        base_actionable = False
    elif relation == "behind":
        status = f"有新提交可用，目前落后 {behind} 个提交"
        base_actionable = True
    elif relation == "ahead":
        status = f"当前领先最新提交 {ahead} 个提交（存在本地提交），已禁用更新"
        base_actionable = False
    elif relation == "diverged":
        status = "当前提交与远程分支分叉，无法自动更新"
        base_actionable = False
    else:
        status = "无法比较本地与最新提交"
        base_actionable = False

    blockers = _blockers(local, git_error, relation)
    if blockers:
        status = f"{status}；{'；'.join(blockers)}"

    return TargetInfo(
        kind="commit",
        label=f"最新提交 {short}",
        tag=None,
        branch=remote.default_branch,
        published_at="",
        commit=remote.latest_commit,
        relation=relation,
        ahead=ahead,
        behind=behind,
        actionable=base_actionable and not blockers,
        downgrade=False,
        status=status,
    )


def check_luker_versions(
    repo_path: str | None,
    running_path: str | None = None,
) -> VersionCheck:
    """检查本地版本、最新发行版和最新提交；不修改工作区。"""
    local = read_local_version(repo_path, running_path)
    if not local.is_git_repo or not local.git_available or local.error:
        return VersionCheck(
            repo_path=local.repo_path,
            local=local,
            release=None,
            commit=None,
            error=local.error,
        )

    git_error: str | None = None
    path = Path(repo_path)  # type: ignore[arg-type]
    try:
        _git_output(
            path,
            "fetch",
            "--tags",
            "--prune",
            "origin",
            timeout=GIT_FETCH_TIMEOUT,
            network=True,
        )
    except VersionError as error:
        git_error = str(error)

    try:
        remote = _fetch_remote_versions()
    except VersionError as error:
        message = str(error)
        if git_error:
            message = f"{message}；{git_error}"
        return VersionCheck(
            repo_path=local.repo_path,
            local=local,
            release=None,
            commit=None,
            error=message,
        )

    release_relation, release_ahead, release_behind = _relation(
        path, local.head, remote.release_commit.sha
    )
    commit_relation, commit_ahead, commit_behind = _relation(
        path, local.head, remote.latest_commit.sha
    )

    return VersionCheck(
        repo_path=local.repo_path,
        local=local,
        release=_release_target(
            local,
            remote,
            release_relation,
            release_ahead,
            release_behind,
            git_error,
        ),
        commit=_commit_target(
            local,
            remote,
            commit_relation,
            commit_ahead,
            commit_behind,
            git_error,
        ),
        error=git_error,
    )


def _terminate_process_tree(pid: int) -> None:
    """超时后强制结束 npm 及其 Node 子进程，避免残留进程继续改 node_modules。"""
    taskkill = shutil.which("taskkill")
    if taskkill is not None:
        try:
            result = subprocess.run(
                [taskkill, "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
            if result.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            logger.debug("taskkill 终止 npm 进程树失败", exc_info=True)

    # taskkill 不可用或失败时，用 psutil 兜底清理整棵进程树
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            with contextlib.suppress(psutil.Error):
                child.kill()
        with contextlib.suppress(psutil.Error):
            parent.kill()
        psutil.wait_procs([*children, parent], timeout=5)
    except psutil.Error:
        logger.debug("psutil 终止 npm 进程树失败", exc_info=True)


def _run_npm_process(
    command: list[str],
    repo: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.Popen(
            command,
            cwd=str(repo),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        )
    except FileNotFoundError as error:
        raise VersionError("未找到 npm，无法安装依赖") from error
    except OSError as error:
        raise VersionError(f"执行 npm 失败：{error}") from error

    try:
        stdout, stderr = process.communicate(timeout=NPM_TIMEOUT)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process.pid)
        try:
            process.communicate(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            with contextlib.suppress(OSError):
                process.kill()
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.communicate(timeout=5)
        raise VersionError(
            f"npm install 超时（{NPM_TIMEOUT // 60} 分钟），已终止 npm 及其子进程"
        ) from None
    except OSError as error:
        _terminate_process_tree(process.pid)
        raise VersionError(f"执行 npm 失败：{error}") from error

    return subprocess.CompletedProcess(
        command,
        process.returncode if process.returncode is not None else -1,
        stdout,
        stderr,
    )


def _run_npm(repo: Path) -> None:
    npm = _npm_executable()
    if npm is None:
        raise VersionError("未找到 npm，无法安装依赖")
    command = [npm, *NPM_INSTALL_ARGS]
    # Start.bat 在安装前设置 NODE_ENV=production；这里只对齐 npm 安装步骤。
    env = os.environ.copy()
    env["NODE_ENV"] = "production"
    result = _run_npm_process(command, repo, env=env)
    if result.returncode != 0:
        detail = _cut(result.stderr or result.stdout)
        raise VersionError(f"npm install 失败：{detail}" if detail else "npm install 失败")


def _rollback(repo: Path, old_head: str, old_branch: str | None) -> bool:
    try:
        if old_branch:
            try:
                _git_output(repo, "checkout", old_branch)
            except VersionError:
                _git_output(repo, "checkout", "--detach", old_head)
            _git_output(repo, "reset", "--hard", old_head)
        else:
            _git_output(repo, "checkout", "--detach", old_head)
        return True
    except VersionError:
        logger.exception("回滚 Luker 版本失败")
        return False


def apply_luker_update(
    repo_path: str,
    target: UpdateTarget,
    on_stage: Callable[[str, str], None] | None = None,
) -> UpdateResult:
    """切换 Luker 到指定提交并安装依赖；失败时尝试回滚代码。"""

    def stage(name: str, message: str) -> None:
        if on_stage is not None:
            try:
                on_stage(name, message)
            except Exception:
                logger.debug("版本更新阶段回调失败", exc_info=True)

    local = read_local_version(repo_path)
    if local.error:
        return UpdateResult(False, False, local.error)
    if not local.is_git_repo:
        return UpdateResult(False, False, "当前 Luker 目录不是 Git 仓库")
    if not local.git_available:
        return UpdateResult(False, False, "未找到 Git，请先安装 Git")
    if not local.npm_available:
        return UpdateResult(False, False, "未找到 npm，无法安装依赖")
    if local.dirty:
        return UpdateResult(False, False, "检测到未提交的修改，已取消更新")

    repo = Path(repo_path)
    old_head = ""
    old_branch: str | None = None
    code_changed = False
    try:
        old_head = _git_output(repo, "rev-parse", "HEAD")
        branch = _git_output(repo, "rev-parse", "--abbrev-ref", "HEAD")
        old_branch = branch if branch != "HEAD" else None

        stage("fetching", "正在获取远程版本...")
        _git_output(
            repo,
            "fetch",
            "--tags",
            "--prune",
            "origin",
            timeout=GIT_FETCH_TIMEOUT,
            network=True,
        )
        _git_output(repo, "cat-file", "-e", f"{target.sha}^{{commit}}")

        stage("switching", f"正在切换到 {target.label}...")
        code_changed = True
        _git_output(repo, "checkout", "--detach", target.sha)

        stage("installing", "正在安装依赖（可能需要几分钟）...")
        _run_npm(repo)
    except VersionError as error:
        rolled_back = _rollback(repo, old_head, old_branch) if old_head else False
        dependencies_restored = True
        if rolled_back:
            try:
                _run_npm(repo)
            except VersionError:
                dependencies_restored = False
                logger.exception("回滚后恢复 Luker 依赖失败")
        if rolled_back:
            suffix = "；已回滚到原版本"
            if not dependencies_restored:
                suffix += "（依赖恢复失败）"
        else:
            suffix = "；自动回滚失败，请手动处理"
        return UpdateResult(False, rolled_back, f"{error}{suffix}", code_changed)

    stage("done", f"已更新到 {target.label}")
    return UpdateResult(True, False, f"已更新到 {target.label}", True)
