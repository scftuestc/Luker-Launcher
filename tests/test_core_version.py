import io
import subprocess
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import core.version as version
from core.version import (
    CommitInfo,
    LocalVersion,
    UpdateTarget,
    VersionError,
)


def completed(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git"], returncode, stdout, stderr)


def commit_json(
    sha: str,
    *,
    date: str = "2026-10-01T00:00:00Z",
    message: str = "subject",
) -> dict:
    return {
        "sha": sha,
        "commit": {
            "committer": {"date": date},
            "message": message,
        },
    }


def local_version(**overrides) -> LocalVersion:
    base = LocalVersion(
        repo_path="C:/Luker",
        git_available=True,
        npm_available=True,
        is_git_repo=True,
        describe="v2.8.0-75-g755925947",
        branch="release",
        head="a" * 40,
        short_head="aaaaaaa",
        date="2026-10-26",
        subject="local subject",
        current_tag=None,
        dirty=False,
        path_matches=True,
    )
    return replace(base, **overrides)


def remote_versions() -> version._RemoteVersions:
    return version._RemoteVersions(
        default_branch="release",
        release_tag="v2.8.0",
        release_published_at="2026-10-01",
        release_commit=CommitInfo(
            sha="b" * 40,
            short_sha="bbbbbbb",
            date="2026-10-01",
            subject="release commit",
        ),
        latest_commit=CommitInfo(
            sha="c" * 40,
            short_sha="ccccccc",
            date="2026-10-26",
            subject="latest commit",
        ),
    )


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self.payload


class ShortShaTests(unittest.TestCase):
    def test_short_sha(self):
        self.assertEqual(version._short_sha("abcdef123456"), "abcdef1")
        self.assertEqual(version._short_sha(""), "")


class GitProxyFallbackTests(unittest.TestCase):
    def test_network_command_retries_without_proxy(self):
        first = completed(1, stderr="Failed to connect over proxy 127.0.0.1")
        second = completed(0, stdout="ok")
        with patch.object(version, "_run", side_effect=[first, second]) as run:
            result = version._git(Path("C:/Luker"), "fetch", network=True)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(run.call_count, 2)
        second_command = run.call_args_list[1].args[0]
        self.assertIn("-c", second_command)
        self.assertIn("http.proxy=", second_command)
        self.assertIn("https.proxy=", second_command)

    def test_non_proxy_failure_is_not_retried(self):
        failure = completed(1, stderr="fatal: not a git repository")
        with patch.object(version, "_run", return_value=failure) as run:
            result = version._git(Path("C:/Luker"), "fetch", network=True)

        self.assertEqual(result.returncode, 1)
        run.assert_called_once()

    def test_local_command_does_not_retry(self):
        failure = completed(1, stderr="Failed to connect over proxy")
        with patch.object(version, "_run", return_value=failure) as run:
            version._git(Path("C:/Luker"), "status")

        run.assert_called_once()


class GitOutputTests(unittest.TestCase):
    def test_strips_output(self):
        with patch.object(version, "_git", return_value=completed(stdout=" value \n")):
            self.assertEqual(version._git_output(Path("C:/Luker"), "status"), "value")

    def test_failure_raises_readable_error(self):
        with (
            patch.object(version, "_git", return_value=completed(1, stderr="boom")),
            self.assertRaisesRegex(VersionError, "boom"),
        ):
            version._git_output(Path("C:/Luker"), "status")


class RelationTests(unittest.TestCase):
    HEAD = "a" * 40
    TARGET = "b" * 40

    def test_same_commit_is_up_to_date(self):
        self.assertEqual(
            version._relation(Path("C:/Luker"), self.HEAD, self.HEAD),
            ("up_to_date", 0, 0),
        )

    def test_current_ahead(self):
        with (
            patch.object(version, "_is_ancestor", return_value=True),
            patch.object(version, "_count_commits", return_value=3),
        ):
            self.assertEqual(
                version._relation(Path("C:/Luker"), self.HEAD, self.TARGET),
                ("ahead", 3, 0),
            )

    def test_current_behind(self):
        with (
            patch.object(version, "_is_ancestor", side_effect=[False, True]),
            patch.object(version, "_count_commits", return_value=4),
        ):
            self.assertEqual(
                version._relation(Path("C:/Luker"), self.HEAD, self.TARGET),
                ("behind", 0, 4),
            )

    def test_diverged(self):
        with patch.object(version, "_is_ancestor", side_effect=[False, False]):
            self.assertEqual(
                version._relation(Path("C:/Luker"), self.HEAD, self.TARGET),
                ("diverged", 0, 0),
            )

    def test_unknown_on_git_error(self):
        with patch.object(version, "_is_ancestor", side_effect=VersionError("boom")):
            self.assertEqual(
                version._relation(Path("C:/Luker"), self.HEAD, self.TARGET),
                ("unknown", 0, 0),
            )


class CountCommitsTests(unittest.TestCase):
    def test_counts_output(self):
        with patch.object(version, "_git_output", return_value="42"):
            self.assertEqual(version._count_commits(Path("C:/Luker"), "a..b"), 42)

    def test_invalid_output(self):
        with (
            patch.object(version, "_git_output", return_value="not-a-number"),
            self.assertRaises(VersionError),
        ):
            version._count_commits(Path("C:/Luker"), "a..b")


class GithubJsonTests(unittest.TestCase):
    def test_reads_json_and_sets_headers(self):
        with patch.object(
            version.urllib.request,
            "urlopen",
            return_value=FakeResponse(b'{"default_branch": "release"}'),
        ) as urlopen:
            data = version._github_json("/repos")

        self.assertEqual(data["default_branch"], "release")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "Luker-Launcher")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")

    def test_reads_list_payload(self):
        with patch.object(
            version.urllib.request,
            "urlopen",
            return_value=FakeResponse(b'[{"sha": "abc"}]'),
        ):
            data = version._github_json_list("/commits")

        self.assertEqual(data[0]["sha"], "abc")

    def test_rate_limit_error(self):
        error = urllib.error.HTTPError("https://api.github.com", 403, "rate", {}, io.BytesIO(b""))
        with (
            patch.object(version.urllib.request, "urlopen", side_effect=error),
            self.assertRaisesRegex(VersionError, "请求受限"),
        ):
            version._github_json("/repos")

    def test_not_found_error(self):
        error = urllib.error.HTTPError(
            "https://api.github.com", 404, "missing", {}, io.BytesIO(b"")
        )
        with (
            patch.object(version.urllib.request, "urlopen", side_effect=error),
            self.assertRaisesRegex(VersionError, "找不到"),
        ):
            version._github_json("/repos")

    def test_network_error(self):
        with (
            patch.object(
                version.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("refused"),
            ),
            self.assertRaisesRegex(VersionError, "无法连接 GitHub"),
        ):
            version._github_json("/repos")

    def test_invalid_json(self):
        with (
            patch.object(
                version.urllib.request,
                "urlopen",
                return_value=FakeResponse(b"not json"),
            ),
            self.assertRaisesRegex(VersionError, "无法解析"),
        ):
            version._github_json("/repos")


class FetchRemoteVersionsTests(unittest.TestCase):
    def test_annotated_tag_resolves_release_commit(self):
        release_commit = commit_json("b" * 40, message="release commit")
        latest_commit = commit_json("c" * 40, message="latest commit")
        responses = {
            "": {"default_branch": "release"},
            "/releases/latest": {
                "tag_name": "v2.8.0",
                "published_at": "2026-10-01T07:42:14Z",
            },
            "/git/ref/tags/v2.8.0": {"object": {"type": "tag", "sha": "tagsha"}},
            "/git/tags/tagsha": {"object": {"sha": "b" * 40}},
            f"/commits/{'b' * 40}": release_commit,
            "/commits?per_page=1&sha=release": [latest_commit],
        }

        with patch.object(version, "_github_payload", side_effect=responses.__getitem__):
            remote = version._fetch_remote_versions()

        self.assertEqual(remote.default_branch, "release")
        self.assertEqual(remote.release_tag, "v2.8.0")
        self.assertEqual(remote.release_published_at, "2026-10-01")
        self.assertEqual(remote.release_commit.sha, "b" * 40)
        self.assertEqual(remote.latest_commit.sha, "c" * 40)

    def test_lightweight_tag_uses_commit(self):
        responses = {
            "": {"default_branch": "release"},
            "/releases/latest": {"tag_name": "v2.8.0", "published_at": "2026-10-01"},
            "/git/ref/tags/v2.8.0": {"object": {"type": "commit", "sha": "b" * 40}},
            f"/commits/{'b' * 40}": commit_json("b" * 40),
            "/commits?per_page=1&sha=release": [commit_json("c" * 40)],
        }

        with patch.object(version, "_github_payload", side_effect=responses.__getitem__):
            remote = version._fetch_remote_versions()

        self.assertEqual(remote.release_commit.sha, "b" * 40)

    def test_missing_release_tag(self):
        with (
            patch.object(
                version,
                "_github_payload",
                side_effect=lambda path: {"default_branch": "release"} if path == "" else {},
            ),
            self.assertRaisesRegex(VersionError, "发行版"),
        ):
            version._fetch_remote_versions()


class ReadLocalVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "Luker"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def which(name: str) -> str | None:
        if name == "git":
            return "git"
        if name in ("npm", "npm.cmd"):
            return "npm"
        return None

    def test_reads_valid_repository(self):
        outputs = {
            ("rev-parse", "HEAD"): "a" * 40,
            ("rev-parse", "--short", "HEAD"): "aaaaaaa",
            ("describe", "--tags", "--always", "--dirty"): "v2.8.0-75-gaaaaaaa",
            ("rev-parse", "--abbrev-ref", "HEAD"): "release",
            ("log", "-1", "--format=%ci"): "2026-10-26 10:00:00 +0800",
            ("log", "-1", "--format=%s"): "local subject",
            ("tag", "--points-at", "HEAD"): "",
            ("status", "--porcelain", "--untracked-files=no"): "",
        }

        def fake_git(_repo, *args, **_kwargs):
            return outputs[args]

        with (
            patch.object(version.shutil, "which", side_effect=self.which),
            patch.object(version, "_git_output", side_effect=fake_git),
        ):
            local = version.read_local_version(str(self.repo))

        self.assertTrue(local.is_git_repo)
        self.assertEqual(local.describe, "v2.8.0-75-gaaaaaaa")
        self.assertEqual(local.branch, "release")
        self.assertEqual(local.head, "a" * 40)
        self.assertEqual(local.date, "2026-10-26")
        self.assertEqual(local.subject, "local subject")
        self.assertIsNone(local.current_tag)
        self.assertFalse(local.dirty)

    def test_dirty_and_current_tag(self):
        outputs = {
            ("rev-parse", "HEAD"): "a" * 40,
            ("rev-parse", "--short", "HEAD"): "aaaaaaa",
            ("describe", "--tags", "--always", "--dirty"): "v2.8.0-dirty",
            ("rev-parse", "--abbrev-ref", "HEAD"): "HEAD",
            ("log", "-1", "--format=%ci"): "2026-10-26 10:00:00 +0800",
            ("log", "-1", "--format=%s"): "local subject",
            ("tag", "--points-at", "HEAD"): "v2.8.0",
            ("status", "--porcelain", "--untracked-files=no"): " M file.txt",
        }

        with (
            patch.object(version.shutil, "which", side_effect=self.which),
            patch.object(
                version,
                "_git_output",
                side_effect=lambda _repo, *args, **_kwargs: outputs[args],
            ),
        ):
            local = version.read_local_version(str(self.repo))

        self.assertTrue(local.dirty)
        self.assertEqual(local.current_tag, "v2.8.0")
        self.assertEqual(local.branch, "HEAD")

    def test_missing_path(self):
        with patch.object(version.shutil, "which", side_effect=self.which):
            local = version.read_local_version("C:/missing/Luker")

        self.assertFalse(local.is_git_repo)
        self.assertIn("不存在", local.error)

    def test_non_git_directory(self):
        with patch.object(version.shutil, "which", side_effect=self.which):
            local = version.read_local_version(self.temp.name)

        self.assertFalse(local.is_git_repo)
        self.assertIn("不是 Git 仓库", local.error)

    def test_git_missing(self):
        with patch.object(version.shutil, "which", return_value=None):
            local = version.read_local_version(str(self.repo))

        self.assertFalse(local.git_available)
        self.assertIn("未找到 Git", local.error)

    def test_path_mismatch(self):
        with (
            patch.object(version.shutil, "which", side_effect=self.which),
            patch.object(version, "_git_output", side_effect=lambda *_args, **_kwargs: ""),
        ):
            local = version.read_local_version(str(self.repo), running_path="C:/Other")

        self.assertFalse(local.path_matches)


class CheckVersionsTests(unittest.TestCase):
    def test_release_ahead_and_commit_behind(self):
        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", return_value=""),
            patch.object(version, "_fetch_remote_versions", return_value=remote_versions()),
            patch.object(
                version,
                "_relation",
                side_effect=[("ahead", 75, 0), ("behind", 0, 77)],
            ),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertIsNotNone(check.release)
        self.assertIsNotNone(check.commit)
        self.assertTrue(check.release.actionable)
        self.assertTrue(check.release.downgrade)
        self.assertIn("领先 75", check.release.status)
        self.assertIn("回退", check.release.status)
        self.assertTrue(check.commit.actionable)
        self.assertIn("落后 77", check.commit.status)
        self.assertEqual(check.release.tag, "v2.8.0")
        self.assertEqual(check.release.published_at, "2026-10-01")
        self.assertEqual(check.release.commit.sha, "b" * 40)
        self.assertEqual(check.commit.commit.date, "2026-10-26")

    def test_up_to_date_targets_are_not_actionable(self):
        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", return_value=""),
            patch.object(version, "_fetch_remote_versions", return_value=remote_versions()),
            patch.object(
                version,
                "_relation",
                side_effect=[("up_to_date", 0, 0), ("up_to_date", 0, 0)],
            ),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertFalse(check.release.actionable)
        self.assertIn("已是最新发行版", check.release.status)
        self.assertFalse(check.commit.actionable)
        self.assertIn("已是最新提交", check.commit.status)

    def test_commit_ahead_is_not_actionable(self):
        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", return_value=""),
            patch.object(version, "_fetch_remote_versions", return_value=remote_versions()),
            patch.object(
                version,
                "_relation",
                side_effect=[("behind", 0, 2), ("ahead", 3, 0)],
            ),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertFalse(check.commit.actionable)
        self.assertIn("当前领先", check.commit.status)

    def test_local_blockers_disable_updates(self):
        dirty = local_version(dirty=True)
        with (
            patch.object(version, "read_local_version", return_value=dirty),
            patch.object(version, "_git_output", return_value=""),
            patch.object(version, "_fetch_remote_versions", return_value=remote_versions()),
            patch.object(version, "_relation", return_value=("behind", 0, 1)),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertFalse(check.release.actionable)
        self.assertFalse(check.commit.actionable)
        self.assertIn("未提交", check.release.status)

    def test_missing_npm_disables_updates(self):
        no_npm = local_version(npm_available=False)
        with (
            patch.object(version, "read_local_version", return_value=no_npm),
            patch.object(version, "_git_output", return_value=""),
            patch.object(version, "_fetch_remote_versions", return_value=remote_versions()),
            patch.object(version, "_relation", return_value=("behind", 0, 1)),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertFalse(check.commit.actionable)
        self.assertIn("npm", check.commit.status)

    def test_path_mismatch_disables_updates(self):
        mismatch = local_version(path_matches=False)
        with (
            patch.object(version, "read_local_version", return_value=mismatch),
            patch.object(version, "_git_output", return_value=""),
            patch.object(version, "_fetch_remote_versions", return_value=remote_versions()),
            patch.object(version, "_relation", return_value=("behind", 0, 1)),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertFalse(check.release.actionable)
        self.assertIn("路径", check.release.status)

    def test_fetch_failure_still_returns_remote_info(self):
        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(
                version,
                "_git_output",
                side_effect=VersionError("git fetch failed"),
            ),
            patch.object(version, "_fetch_remote_versions", return_value=remote_versions()),
            patch.object(version, "_relation", return_value=("unknown", 0, 0)),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertEqual(check.error, "git fetch failed")
        self.assertFalse(check.release.actionable)
        self.assertIn("Git 更新失败", check.release.status)

    def test_api_failure_returns_error_without_targets(self):
        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", return_value=""),
            patch.object(
                version,
                "_fetch_remote_versions",
                side_effect=VersionError("api failed"),
            ),
        ):
            check = version.check_luker_versions("C:/Luker")

        self.assertIsNone(check.release)
        self.assertIsNone(check.commit)
        self.assertEqual(check.error, "api failed")

    def test_local_error_skips_remote_checks(self):
        broken = local_version(is_git_repo=False, error="not a repo")
        with (
            patch.object(version, "read_local_version", return_value=broken),
            patch.object(version, "_fetch_remote_versions") as remote,
        ):
            check = version.check_luker_versions("C:/Luker")

        remote.assert_not_called()
        self.assertEqual(check.error, "not a repo")


class ApplyUpdateTests(unittest.TestCase):
    TARGET = UpdateTarget(
        kind="release",
        label="v2.8.0",
        sha="b" * 40,
        tag="v2.8.0",
    )
    OLD_HEAD = "a" * 40

    def test_successful_update(self):
        calls: list[tuple] = []

        def fake_git(_repo, *args, **_kwargs):
            calls.append(args)
            if args == ("rev-parse", "HEAD"):
                return self.OLD_HEAD
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return "release"
            return ""

        stages: list[tuple[str, str]] = []
        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", side_effect=fake_git),
            patch.object(version, "_run_npm") as npm,
        ):
            result = version.apply_luker_update(
                "C:/Luker",
                self.TARGET,
                on_stage=lambda stage, message: stages.append((stage, message)),
            )

        self.assertTrue(result.success)
        self.assertFalse(result.rolled_back)
        self.assertIn(("checkout", "--detach", self.TARGET.sha), calls)
        self.assertIn(("fetch", "--tags", "--prune", "origin"), calls)
        npm.assert_called_once()
        self.assertEqual(
            [stage for stage, _ in stages],
            ["fetching", "switching", "installing", "done"],
        )

    def test_checkout_failure_rolls_back_and_restores_dependencies(self):
        def fake_git(_repo, *args, **_kwargs):
            if args == ("rev-parse", "HEAD"):
                return self.OLD_HEAD
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return "release"
            if args == ("checkout", "--detach", self.TARGET.sha):
                raise VersionError("checkout failed")
            return ""

        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", side_effect=fake_git),
            patch.object(version, "_run_npm") as npm,
        ):
            result = version.apply_luker_update("C:/Luker", self.TARGET)

        self.assertFalse(result.success)
        self.assertTrue(result.rolled_back)
        self.assertIn("checkout failed", result.message)
        npm.assert_called_once()

    def test_npm_failure_rolls_back_and_retries_install(self):
        def fake_git(_repo, *args, **_kwargs):
            if args == ("rev-parse", "HEAD"):
                return self.OLD_HEAD
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return "release"
            return ""

        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", side_effect=fake_git),
            patch.object(
                version,
                "_run_npm",
                side_effect=[VersionError("npm failed"), None],
            ) as npm,
        ):
            result = version.apply_luker_update("C:/Luker", self.TARGET)

        self.assertFalse(result.success)
        self.assertTrue(result.rolled_back)
        self.assertIn("npm failed", result.message)
        self.assertEqual(npm.call_count, 2)

    def test_rollback_failure_is_reported(self):
        def fake_git(_repo, *args, **_kwargs):
            if args == ("rev-parse", "HEAD"):
                return self.OLD_HEAD
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return "release"
            if args[0] == "checkout":
                raise VersionError("checkout failed")
            if args[0] == "reset":
                raise VersionError("reset failed")
            return ""

        with (
            patch.object(version, "read_local_version", return_value=local_version()),
            patch.object(version, "_git_output", side_effect=fake_git),
            patch.object(version, "_run_npm") as npm,
        ):
            result = version.apply_luker_update("C:/Luker", self.TARGET)

        self.assertFalse(result.success)
        self.assertFalse(result.rolled_back)
        self.assertIn("自动回滚失败", result.message)
        npm.assert_not_called()

    def test_dirty_worktree_is_rejected_before_git(self):
        with (
            patch.object(
                version,
                "read_local_version",
                return_value=local_version(dirty=True),
            ),
            patch.object(version, "_git_output") as git,
        ):
            result = version.apply_luker_update("C:/Luker", self.TARGET)

        self.assertFalse(result.success)
        self.assertFalse(result.rolled_back)
        self.assertIn("未提交", result.message)
        git.assert_not_called()

    def test_missing_npm_is_rejected_before_git(self):
        with (
            patch.object(
                version,
                "read_local_version",
                return_value=local_version(npm_available=False),
            ),
            patch.object(version, "_git_output") as git,
        ):
            result = version.apply_luker_update("C:/Luker", self.TARGET)

        self.assertFalse(result.success)
        self.assertIn("npm", result.message)
        git.assert_not_called()


class FakeNpmProcess:
    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        *,
        timeout_once: bool = False,
    ) -> None:
        self.pid = 4242
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timeout_once = timeout_once
        self.communicate_calls = 0
        self.killed = False

    def communicate(self, timeout: int | None = None):
        self.communicate_calls += 1
        if self.timeout_once and self.communicate_calls == 1:
            raise subprocess.TimeoutExpired(["npm"], timeout)
        return self.stdout, self.stderr

    def kill(self) -> None:
        self.killed = True


class RunNpmTests(unittest.TestCase):
    def test_install_args_match_release_start_bat(self):
        self.assertEqual(
            version.NPM_INSTALL_ARGS,
            (
                "install",
                "--no-save",
                "--no-audit",
                "--no-fund",
                "--loglevel=error",
                "--no-progress",
                "--omit=dev",
                "--ignore-scripts",
            ),
        )

    def test_uses_resolved_npm_path(self):
        process = FakeNpmProcess()
        npm = "C:/Program Files/nodejs/npm.CMD"
        with (
            patch.object(version, "_npm_executable", return_value=npm),
            patch.object(version.subprocess, "Popen", return_value=process) as popen,
        ):
            version._run_npm(Path("C:/Luker"))

        command = popen.call_args.args[0]
        self.assertEqual(command[0], npm)
        self.assertEqual(command[1], "install")
        self.assertNotIn("cmd", [part.lower() for part in command])
        self.assertIn("--omit=dev", command)
        self.assertIn("--ignore-scripts", command)
        self.assertEqual(Path(popen.call_args.kwargs["cwd"]), Path("C:/Luker"))

    def test_sets_production_node_env_for_npm_install(self):
        process = FakeNpmProcess()
        with (
            patch.dict(version.os.environ, {"LUKER_TEST_SENTINEL": "1"}),
            patch.object(version, "_npm_executable", return_value="npm.cmd"),
            patch.object(version.subprocess, "Popen", return_value=process) as popen,
        ):
            version._run_npm(Path("C:/Luker"))

        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["NODE_ENV"], "production")
        self.assertEqual(env["LUKER_TEST_SENTINEL"], "1")

    def test_failure_raises(self):
        process = FakeNpmProcess(returncode=1, stderr="boom")
        with (
            patch.object(version, "_npm_executable", return_value="npm.cmd"),
            patch.object(version.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(VersionError, "npm install 失败"),
        ):
            version._run_npm(Path("C:/Luker"))

    def test_timeout_kills_process_tree(self):
        process = FakeNpmProcess(timeout_once=True)
        with (
            patch.object(version, "_npm_executable", return_value="npm.cmd"),
            patch.object(version.subprocess, "Popen", return_value=process),
            patch.object(version, "_terminate_process_tree") as terminate,
            self.assertRaisesRegex(VersionError, "超时"),
        ):
            version._run_npm(Path("C:/Luker"))

        terminate.assert_called_once_with(process.pid)
        self.assertEqual(process.communicate_calls, 2)

    def test_terminate_process_tree_uses_taskkill(self):
        with (
            patch.object(
                version.shutil,
                "which",
                return_value="C:/Windows/System32/taskkill.exe",
            ),
            patch.object(version.subprocess, "run", return_value=completed()) as run,
        ):
            version._terminate_process_tree(1234)

        command = run.call_args.args[0]
        self.assertIn("/T", command)
        self.assertIn("/F", command)
        self.assertIn("1234", command)

    def test_missing_npm_raises(self):
        with (
            patch.object(version, "_npm_executable", return_value=None),
            self.assertRaisesRegex(VersionError, "未找到 npm"),
        ):
            version._run_npm(Path("C:/Luker"))

    def test_popen_missing_raises(self):
        with (
            patch.object(version, "_npm_executable", return_value="npm.cmd"),
            patch.object(
                version.subprocess,
                "Popen",
                side_effect=FileNotFoundError("missing"),
            ),
            self.assertRaisesRegex(VersionError, "未找到 npm"),
        ):
            version._run_npm(Path("C:/Luker"))


class RollbackTests(unittest.TestCase):
    def test_returns_to_branch_and_resets(self):
        calls: list[tuple] = []
        with patch.object(
            version,
            "_git_output",
            side_effect=lambda _repo, *args, **_kwargs: calls.append(args) or "",
        ):
            self.assertTrue(version._rollback(Path("C:/Luker"), "oldsha", "release"))

        self.assertEqual(calls, [("checkout", "release"), ("reset", "--hard", "oldsha")])

    def test_detached_head_rolls_back_to_detached(self):
        calls: list[tuple] = []
        with patch.object(
            version,
            "_git_output",
            side_effect=lambda _repo, *args, **_kwargs: calls.append(args) or "",
        ):
            self.assertTrue(version._rollback(Path("C:/Luker"), "oldsha", None))

        self.assertEqual(calls, [("checkout", "--detach", "oldsha")])

    def test_failure_returns_false(self):
        with patch.object(
            version,
            "_git_output",
            side_effect=VersionError("rollback failed"),
        ):
            self.assertFalse(version._rollback(Path("C:/Luker"), "oldsha", "release"))


class SamePathTests(unittest.TestCase):
    def test_same_path_with_mixed_separators(self):
        self.assertTrue(version.same_path("C:/Luker", "C:\\Luker"))

    def test_different_paths(self):
        self.assertFalse(version.same_path("C:/Luker", "C:/Other"))


if __name__ == "__main__":
    unittest.main()
