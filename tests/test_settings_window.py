import unittest
from dataclasses import replace
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import launcher_app
import settings_window
from core.version import (
    CommitInfo,
    LocalVersion,
    TargetInfo,
    UpdateProgress,
    UpdateTarget,
    VersionCheck,
)
from launcher_app import LukerLauncher
from settings_window import (
    _SCROLL_BINDING_SEQUENCES,
    SettingsWindow,
    bind_click_recursive,
    bind_hover_recursive,
    clear_scroll_bindings,
    theme_card_hover_colors,
    update_button_state_colors,
)


class FakeTkInterpreter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def call(self, *args: str) -> None:
        self.calls.append(args)


class FakeWidget:
    def __init__(self) -> None:
        self.tk = FakeTkInterpreter()


class ClickWidget:
    def __init__(self, children: list["ClickWidget"] | None = None) -> None:
        self.children = children or []
        self.bindings: list[tuple[str, object]] = []

    def bind(self, sequence: str, callback: object) -> None:
        self.bindings.append((sequence, callback))

    def winfo_children(self) -> list["ClickWidget"]:
        return self.children


class FakeSettingsWindow:
    instances: ClassVar[list["FakeSettingsWindow"]] = []

    def __init__(
        self,
        parent: object,
        anchor_point: tuple[int, int] | None = None,
        on_close: object = None,
        on_check_luker_update: object = None,
        on_apply_luker_update: object = None,
        on_luker_path_changed: object = None,
        initial_version_check: object = None,
        initial_version_checking: bool = False,
    ) -> None:
        self.parent = parent
        self.anchor_point = anchor_point
        self.on_close = on_close
        self.on_check_luker_update = on_check_luker_update
        self.on_apply_luker_update = on_apply_luker_update
        self.on_luker_path_changed = on_luker_path_changed
        self.initial_version_check = initial_version_check
        self.initial_version_checking = initial_version_checking
        self.focused = 0
        self.alive = True
        type(self).instances.append(self)

    def focus_force(self) -> None:
        self.focused += 1

    def is_alive(self) -> bool:
        return self.alive


class FakeTrayMenu:
    def __init__(self) -> None:
        self.state: tuple[bool, bool, bool, bool] | None = None
        self.point: tuple[int, int] | None = None

    def update_state(self, *args: bool) -> None:
        self.state = args

    def show_at(self, x: int, y: int) -> None:
        self.point = (x, y)


class FakeLogWindow:
    def is_visible(self) -> bool:
        return False


class ScrollBindingTests(unittest.TestCase):
    def test_clears_all_known_global_sequences(self):
        widget = FakeWidget()

        clear_scroll_bindings(widget)

        self.assertEqual(
            [call[2] for call in widget.tk.calls],
            list(_SCROLL_BINDING_SEQUENCES),
        )
        self.assertTrue(all(call[:2] == ("bind", "all") for call in widget.tk.calls))
        self.assertTrue(all(call[3] == "" for call in widget.tk.calls))


class ClickBindingTests(unittest.TestCase):
    def test_binds_widget_and_all_descendants(self):
        leaf = ClickWidget()
        middle = ClickWidget([leaf])
        root = ClickWidget([middle])

        def on_click(_event: object) -> None:
            pass

        bind_click_recursive(root, on_click)

        for widget in (root, middle, leaf):
            self.assertEqual(widget.bindings, [('<Button-1>', on_click)])


class HoverWidget:
    def __init__(self, children: list["HoverWidget"] | None = None) -> None:
        self.children = children or []
        self.bindings: list[tuple[str, object, str | None]] = []

    def bind(self, sequence: str, callback: object, add: str | None = None) -> None:
        self.bindings.append((sequence, callback, add))

    def winfo_children(self) -> list["HoverWidget"]:
        return self.children


class HoverBindingTests(unittest.TestCase):
    def test_binds_enter_and_leave_on_all_descendants(self):
        leaf = HoverWidget()
        middle = HoverWidget([leaf])
        root = HoverWidget([middle])

        def on_enter(_event: object) -> None:
            pass

        def on_leave(_event: object) -> None:
            pass

        bind_hover_recursive(root, on_enter, on_leave)

        for widget in (root, middle, leaf):
            self.assertEqual(
                widget.bindings,
                [('<Enter>', on_enter, '+'), ('<Leave>', on_leave, '+')],
            )


class ThemeCardHoverColorTests(unittest.TestCase):
    colors: ClassVar[dict[str, str]] = {
        'card': '#101010',
        'card_hover': '#202020',
        'accent': '#303030',
        'border': '#404040',
    }

    def test_unselected_card_animates_fill_and_border(self):
        self.assertEqual(
            theme_card_hover_colors(self.colors, False, 0),
            ('#101010', '#404040'),
        )
        self.assertEqual(
            theme_card_hover_colors(self.colors, False, 1),
            ('#202020', '#303030'),
        )

    def test_selected_card_keeps_accent_border(self):
        self.assertEqual(
            theme_card_hover_colors(self.colors, True, 0),
            ('#101010', '#303030'),
        )
        self.assertEqual(
            theme_card_hover_colors(self.colors, True, 1),
            ('#202020', '#303030'),
        )

    def test_progress_is_clamped(self):
        self.assertEqual(
            theme_card_hover_colors(self.colors, False, -1),
            theme_card_hover_colors(self.colors, False, 0),
        )
        self.assertEqual(
            theme_card_hover_colors(self.colors, False, 2),
            theme_card_hover_colors(self.colors, False, 1),
        )


class UpdateButtonStateColorTests(unittest.TestCase):
    colors: ClassVar[dict[str, str]] = {
        'text_dim': '#606060',
        'accent': '#a0a0a0',
        'border': '#404040',
    }

    def test_disabled_and_enabled_colors(self):
        self.assertEqual(
            update_button_state_colors(self.colors, 0),
            ('#606060', '#404040'),
        )
        self.assertEqual(
            update_button_state_colors(self.colors, 1),
            ('#a0a0a0', '#a0a0a0'),
        )

    def test_progress_is_clamped(self):
        self.assertEqual(
            update_button_state_colors(self.colors, -1),
            update_button_state_colors(self.colors, 0),
        )
        self.assertEqual(
            update_button_state_colors(self.colors, 2),
            update_button_state_colors(self.colors, 1),
        )


class ThemeHoverJobTests(unittest.TestCase):
    def test_cancel_all_hover_jobs(self):
        window = object.__new__(SettingsWindow)
        window._theme_hover_jobs = {'first', 'second'}
        cancelled: list[str] = []
        window.after_cancel = cancelled.append

        window._cancel_theme_hover_jobs()

        self.assertCountEqual(cancelled, ['first', 'second'])
        self.assertEqual(window._theme_hover_jobs, set())

    def test_cancel_update_button_fade(self):
        window = object.__new__(SettingsWindow)
        window._update_button_job = 'fade'
        cancelled: list[str] = []
        window.after_cancel = cancelled.append

        window._cancel_update_button_fade()

        self.assertEqual(cancelled, ['fade'])
        self.assertIsNone(window._update_button_job)


class FakeSwitch:
    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.selected = False

    def get(self) -> int:
        return self.value

    def select(self) -> None:
        self.selected = True

    def deselect(self) -> None:
        self.selected = False


class BlurToggleTests(unittest.TestCase):
    def test_toggle_writes_config_and_repaints(self):
        window = object.__new__(SettingsWindow)
        window.blur_switch = FakeSwitch(1)
        updates = []
        window.update = lambda: updates.append(True)
        fake_config = SimpleNamespace(blur_enabled=False)

        with patch.object(settings_window, 'config', fake_config):
            window._on_blur_toggle()

        self.assertTrue(fake_config.blur_enabled)
        self.assertEqual(updates, [True])

    def test_toggle_off_writes_false(self):
        window = object.__new__(SettingsWindow)
        window.blur_switch = FakeSwitch(0)
        window.update = lambda: None
        fake_config = SimpleNamespace(blur_enabled=True)

        with patch.object(settings_window, 'config', fake_config):
            window._on_blur_toggle()

        self.assertFalse(fake_config.blur_enabled)

    def test_blur_change_applies_when_alive(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window.blur_switch = FakeSwitch()
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(True)

        self.assertTrue(window.blur_switch.selected)
        self.assertEqual(calls, [True])

    def test_blur_change_ignored_after_destroy(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = True
        calls = []
        window._setup_blur = lambda: calls.append(True)

        window._on_blur_change(False)

        self.assertEqual(calls, [])


class FakeVariable:
    def __init__(self) -> None:
        self.value: str | None = None

    def set(self, value: str) -> None:
        self.value = value


class CloseBehaviorTests(unittest.TestCase):
    def test_change_writes_selected_value(self):
        for value in ('ask', 'tray', 'exit'):
            with self.subTest(value=value):
                window = object.__new__(SettingsWindow)
                fake_config = SimpleNamespace(close_behavior='ask')

                with patch.object(settings_window, 'config', fake_config):
                    window._on_close_behavior_change(value)

                self.assertEqual(fake_config.close_behavior, value)

    def test_config_callback_updates_variable_when_alive(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._close_behavior_var = FakeVariable()

        window._on_close_behavior_config_change('tray')

        self.assertEqual(window._close_behavior_var.value, 'tray')

    def test_config_callback_ignored_after_destroy(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = True
        window._close_behavior_var = FakeVariable()

        window._on_close_behavior_config_change('exit')

        self.assertIsNone(window._close_behavior_var.value)

    def test_config_callback_without_variable_is_ignored(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False

        window._on_close_behavior_config_change('ask')


def make_local(**overrides) -> LocalVersion:
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
        dirty=False,
        path_matches=True,
    )
    return replace(base, **overrides)


def make_commit(**overrides) -> CommitInfo:
    base = CommitInfo(
        sha="b" * 40,
        short_sha="bbbbbbb",
        date="2026-10-01",
        subject="remote subject",
    )
    return replace(base, **overrides)


def make_target(
    kind: str,
    relation: str,
    *,
    actionable: bool,
    downgrade: bool = False,
    ahead: int = 0,
    behind: int = 0,
    commit: CommitInfo | None = None,
) -> TargetInfo:
    target_commit = commit or make_commit()
    if kind == "release":
        return TargetInfo(
            kind="release",
            label="v2.8.0",
            tag="v2.8.0",
            branch=None,
            published_at="2026-10-01",
            commit=target_commit,
            relation=relation,
            ahead=ahead,
            behind=behind,
            actionable=actionable,
            downgrade=downgrade,
            status="发行版状态",
        )
    return TargetInfo(
        kind="commit",
        label="最新提交 bbbbbbb",
        tag=None,
        branch="release",
        published_at="",
        commit=target_commit,
        relation=relation,
        ahead=ahead,
        behind=behind,
        actionable=actionable,
        downgrade=False,
        status="提交状态",
    )


def make_check(
    *,
    release: TargetInfo | None = None,
    commit: TargetInfo | None = None,
    local: LocalVersion | None = None,
    error: str | None = None,
) -> VersionCheck:
    return VersionCheck(
        repo_path="C:/Luker",
        local=local or make_local(),
        release=release,
        commit=commit,
        error=error,
    )


class UpdateUiTests(unittest.TestCase):
    def test_selected_target_follows_channel(self):
        window = object.__new__(SettingsWindow)
        release = make_target("release", "behind", actionable=True)
        commit = make_target("commit", "behind", actionable=True)
        window._version_check = make_check(release=release, commit=commit)
        window._update_channel_var = SimpleNamespace(get=lambda: "release")
        self.assertIs(window._selected_target(), release)

        window._update_channel_var = SimpleNamespace(get=lambda: "commit")
        self.assertIs(window._selected_target(), commit)

        window._version_check = None
        self.assertIsNone(window._selected_target())

    def test_update_button_text_for_states(self):
        window = object.__new__(SettingsWindow)
        self.assertEqual(window._update_button_text(None), "更新")
        self.assertEqual(
            window._update_button_text(make_target("release", "behind", actionable=True)),
            "更新到 v2.8.0",
        )
        self.assertEqual(
            window._update_button_text(
                make_target(
                    "release",
                    "ahead",
                    actionable=True,
                    downgrade=True,
                    ahead=75,
                )
            ),
            "回退到 v2.8.0",
        )
        self.assertEqual(
            window._update_button_text(make_target("release", "up_to_date", actionable=False)),
            "已是最新",
        )
        self.assertEqual(
            window._update_button_text(make_target("commit", "behind", actionable=True)),
            "更新到最新提交",
        )
        self.assertEqual(
            window._update_button_text(make_target("commit", "ahead", actionable=False)),
            "当前不可更新",
        )

    def test_status_emphasis_for_newer_or_downgrade_targets(self):
        self.assertTrue(
            SettingsWindow._status_emphasis(make_target("release", "behind", actionable=True))
        )
        self.assertTrue(
            SettingsWindow._status_emphasis(make_target("commit", "behind", actionable=True))
        )
        self.assertTrue(
            SettingsWindow._status_emphasis(
                make_target("release", "ahead", actionable=True, downgrade=True)
            )
        )
        self.assertFalse(
            SettingsWindow._status_emphasis(make_target("release", "up_to_date", actionable=False))
        )
        self.assertFalse(
            SettingsWindow._status_emphasis(make_target("commit", "ahead", actionable=False))
        )
        self.assertFalse(SettingsWindow._status_emphasis(None))

    def test_channel_change_only_rerenders(self):
        window = object.__new__(SettingsWindow)
        calls = []
        window._render_luker_state = lambda: calls.append("render")

        window._on_update_channel_change()

        self.assertEqual(calls, ["render"])

    def test_check_update_sets_loading_and_calls_callback(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_checking = False
        window._update_busy = False
        window._update_progress = UpdateProgress("old", "old", "info", False)
        window._render_luker_state = lambda: None
        called = []
        window._on_check_luker_update = lambda: called.append(True) or True

        window._on_check_update()

        self.assertTrue(window._version_checking)
        self.assertIsNone(window._update_progress)
        self.assertEqual(called, [True])

    def test_check_update_rejection_resets_state(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_checking = False
        window._update_busy = False
        window._update_progress = None
        window._render_luker_state = lambda: None
        window._on_check_luker_update = lambda: False

        window._on_check_update()

        self.assertFalse(window._version_checking)
        self.assertIsNotNone(window._update_progress)
        self.assertEqual(window._update_progress.level, "warning")

    def test_apply_update_confirms_and_passes_target(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_checking = False
        window._update_busy = False
        window._update_progress = None
        window._render_luker_state = lambda: None
        release = make_target("release", "behind", actionable=True)
        window._version_check = make_check(release=release)
        window._update_channel_var = SimpleNamespace(get=lambda: "release")
        targets: list[UpdateTarget] = []
        window._on_apply_luker_update = lambda target: targets.append(target) or True

        with patch.object(settings_window.messagebox, "askyesno", return_value=True):
            window._on_apply_update()

        self.assertEqual(len(targets), 1)
        self.assertEqual(
            targets[0],
            UpdateTarget(
                kind="release",
                label="v2.8.0",
                sha="b" * 40,
                tag="v2.8.0",
                branch=None,
            ),
        )
        self.assertTrue(window._update_busy)
        self.assertEqual(window._update_progress.stage, "preparing")

    def test_apply_update_cancel_does_not_call_backend(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_checking = False
        window._update_busy = False
        window._update_progress = None
        window._render_luker_state = lambda: None
        window._version_check = make_check(
            release=make_target("release", "behind", actionable=True)
        )
        window._update_channel_var = SimpleNamespace(get=lambda: "release")
        called = []
        window._on_apply_luker_update = lambda target: called.append(target) or True

        with patch.object(settings_window.messagebox, "askyesno", return_value=False):
            window._on_apply_update()

        self.assertEqual(called, [])
        self.assertFalse(window._update_busy)

    def test_apply_update_rejection_resets_busy(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_checking = False
        window._update_busy = False
        window._update_progress = None
        window._render_luker_state = lambda: None
        window._version_check = make_check(
            release=make_target("release", "behind", actionable=True)
        )
        window._update_channel_var = SimpleNamespace(get=lambda: "release")
        window._on_apply_luker_update = lambda _target: False

        with patch.object(settings_window.messagebox, "askyesno", return_value=True):
            window._on_apply_update()

        self.assertFalse(window._update_busy)
        self.assertEqual(window._update_progress.level, "warning")

    def test_set_version_check_clears_loading(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_checking = True
        window._update_progress = UpdateProgress("old", "old", "info", True)
        window._render_luker_state = lambda: None
        check = make_check()

        window.set_version_check(check)

        self.assertIs(window._version_check, check)
        self.assertFalse(window._version_checking)
        self.assertIsNone(window._update_progress)

    def test_final_progress_clears_stale_target(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_check = make_check(
            release=make_target("release", "behind", actionable=True)
        )
        window._render_luker_state = lambda: None
        progress = UpdateProgress("done", "更新完成", "success", False)

        window.set_update_progress(progress)

        self.assertIsNone(window._version_check)
        self.assertFalse(window._update_busy)
        self.assertIs(window._update_progress, progress)

    def test_intermediate_progress_keeps_target(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        check = make_check(release=make_target("release", "behind", actionable=True))
        window._version_check = check
        window._render_luker_state = lambda: None

        window.set_update_progress(UpdateProgress("stopping", "停止中", "info", True))

        self.assertIs(window._version_check, check)
        self.assertTrue(window._update_busy)

    def test_select_path_clears_version_state(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._version_check = make_check()
        window._update_progress = UpdateProgress("old", "old", "info", False)
        window._version_checking = True
        window._update_busy = True
        window._render_luker_state = lambda: None
        changed: list[bool] = []
        window._on_luker_path_changed = lambda: changed.append(True)
        window.path_label = SimpleNamespace(
            configure=lambda **kwargs: setattr(window, "configured_path", kwargs["text"])
        )

        with patch.object(settings_window, "select_luker_path", return_value="D:/New"):
            window._select_path()

        self.assertEqual(window.configured_path, "D:/New")
        self.assertEqual(changed, [True])
        self.assertIsNone(window._version_check)
        self.assertIsNone(window._update_progress)
        self.assertFalse(window._version_checking)
        self.assertFalse(window._update_busy)

    def test_current_text_includes_local_version_and_warnings(self):
        window = object.__new__(SettingsWindow)
        window._version_check = make_check(local=make_local(dirty=True, path_matches=False))

        text = window._current_text()

        self.assertIn("当前版本：提交 aaaaaaa · 2026-10-26", text)
        self.assertIn("未提交", text)
        self.assertIn("路径已更改", text)
        self.assertNotIn("local subject", text)

    def test_current_text_shows_current_tag(self):
        window = object.__new__(SettingsWindow)
        window._version_check = make_check(local=make_local(current_tag="v2.8.0"))

        text = window._current_text()

        self.assertIn(
            "当前版本：Tag v2.8.0 · 提交 aaaaaaa · 2026-10-26",
            text,
        )

    def test_summary_text_shows_requested_version_fields(self):
        release = make_target(
            "release",
            "behind",
            actionable=True,
            commit=make_commit(sha="b" * 40, short_sha="bbbbbbb", date="2026-10-01"),
        )
        commit = make_target(
            "commit",
            "behind",
            actionable=True,
            commit=make_commit(sha="c" * 40, short_sha="ccccccc", date="2026-10-26"),
        )

        release_summary = SettingsWindow._summary_text(release)
        commit_summary = SettingsWindow._summary_text(commit)

        self.assertEqual(
            release_summary,
            "v2.8.0 · 发布于 2026-10-01 · 提交 bbbbbbb",
        )
        self.assertEqual(commit_summary, "提交于 2026-10-26 · ccccccc")
        self.assertNotIn("签名", release_summary)
        self.assertNotIn("签名", commit_summary)

    def test_hints_are_short_single_sentences(self):
        for text in (settings_window.PWA_HINT_TEXT, settings_window.GCL_HINT_TEXT):
            self.assertNotIn("\n", text)
            self.assertEqual(text.count("。"), 1)
            self.assertLessEqual(len(text), 30)

    def test_status_text_and_color_use_progress(self):
        window = object.__new__(SettingsWindow)
        window.COLORS = {
            "text_muted": "#111111",
            "success": "#222222",
            "warning": "#333333",
            "error": "#444444",
        }
        window._version_checking = False
        window._update_progress = UpdateProgress("done", "更新完成", "success", False)

        self.assertEqual(window._status_text(None), "更新完成")
        self.assertEqual(window._status_color(None), "#222222")


class SettingsInteractionTests(unittest.TestCase):
    def test_selecting_current_theme_is_a_noop(self):
        window = object.__new__(SettingsWindow)
        fake_config = SimpleNamespace(theme_name='summer')

        with patch.object(settings_window, 'config', fake_config):
            window._select_theme('summer')
            self.assertEqual(fake_config.theme_name, 'summer')

            window._select_theme('mist_gray')
            self.assertEqual(fake_config.theme_name, 'mist_gray')

            window._select_theme('not-a-theme')
            self.assertEqual(fake_config.theme_name, 'mist_gray')

    def test_configure_events_are_coalesced(self):
        window = object.__new__(SettingsWindow)
        window._pending_fit = False
        scheduled: list[object] = []
        window.after_idle = scheduled.append
        fitted: list[bool] = []
        window._fit_to_current_monitor = lambda: fitted.append(True)
        event = SimpleNamespace(widget=window)

        window._on_configure(event)
        window._on_configure(event)

        self.assertEqual(scheduled, [window._run_scheduled_fit])
        scheduled[0]()
        self.assertEqual(fitted, [True])
        self.assertFalse(window._pending_fit)

    def test_theme_change_keeps_only_latest_rebuild(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window._rebuild_job = 'old'
        canceled: list[object] = []
        scheduled: list[tuple[int, object]] = []
        window.after_cancel = canceled.append
        window.after = lambda delay, callback: scheduled.append((delay, callback)) or 'new'

        window._on_theme_change({'bg': '#000000'})

        self.assertEqual(window.COLORS, {'bg': '#000000'})
        self.assertEqual(canceled, ['old'])
        self.assertEqual(scheduled, [(0, window._rebuild_ui)])
        self.assertEqual(window._rebuild_job, 'new')

    def test_setup_blur_is_skipped_after_destroy(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = True
        window._blur_job = 'job'
        calls: list[bool] = []

        with patch.object(
            settings_window,
            'sync_window_blur',
            lambda *args, **kwargs: calls.append(True),
        ):
            window._setup_blur()

        self.assertEqual(calls, [])
        self.assertIsNone(window._blur_job)


class FakeChild:
    def __init__(self, calls: list[tuple[str, ...]]) -> None:
        self.calls = calls

    def destroy(self) -> None:
        self.calls.append(('destroy',))


class RebuildOrderTests(unittest.TestCase):
    def test_root_background_updates_before_rebuilding_children(self):
        window = object.__new__(SettingsWindow)
        window._destroyed = False
        window.COLORS = {'bg': '#123456'}
        window._theme_hover_jobs = set()
        window._update_button_job = None
        calls = []
        window.winfo_exists = lambda: True
        window.winfo_children = lambda: [FakeChild(calls)]
        window.configure = lambda **options: calls.append(('configure', options))
        window._build_ui = lambda: calls.append(('build',))
        window._setup_blur = lambda: calls.append(('blur',))

        with patch.object(
            settings_window,
            'clear_scroll_bindings',
            lambda _widget: calls.append(('clear',)),
        ):
            window._rebuild_ui()

        self.assertEqual(
            calls,
            [
                ('destroy',),
                ('clear',),
                ('configure', {'fg_color': '#123456'}),
                ('build',),
                ('blur',),
            ],
        )


class SettingsWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSettingsWindow.instances.clear()

    @staticmethod
    def _make_launcher() -> LukerLauncher:
        launcher = object.__new__(LukerLauncher)
        launcher._exiting = False
        launcher.log_window = object()
        launcher.settings_window = None
        launcher._tray_anchor = (100, 200)
        launcher._version_checking = False
        launcher._version_check_cache = None
        launcher._version_check_seq = 0
        return launcher

    def test_open_passes_cached_check_to_new_window(self):
        launcher = self._make_launcher()
        cached = make_check()
        launcher._version_check_cache = cached
        launcher._version_checking = True

        with (
            patch.object(launcher_app, "SettingsWindow", FakeSettingsWindow),
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="C:/Luker")),
        ):
            launcher._open_settings_window()

        window = FakeSettingsWindow.instances[0]
        self.assertIs(window.initial_version_check, cached)
        self.assertTrue(window.initial_version_checking)

    def test_open_drops_cached_check_for_other_path(self):
        launcher = self._make_launcher()
        launcher._version_check_cache = make_check()

        with (
            patch.object(launcher_app, "SettingsWindow", FakeSettingsWindow),
            patch.object(launcher_app, "config", SimpleNamespace(luker_path="D:/Other")),
        ):
            launcher._open_settings_window()

        self.assertIsNone(FakeSettingsWindow.instances[0].initial_version_check)
        self.assertIsNone(launcher._version_check_cache)

    def test_open_uses_tray_anchor_and_reuses_alive_window(self):
        launcher = self._make_launcher()

        with patch.object(launcher_app, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()
            launcher._open_settings_window()

        self.assertEqual(len(FakeSettingsWindow.instances), 1)
        window = FakeSettingsWindow.instances[0]
        self.assertIs(window.parent, launcher.log_window)
        self.assertEqual(window.anchor_point, (100, 200))
        self.assertEqual(window.focused, 2)
        self.assertEqual(window.on_close, launcher._on_settings_closed)
        self.assertEqual(
            window.on_check_luker_update.__name__,
            '_request_luker_version_check',
        )
        self.assertEqual(window.on_apply_luker_update.__name__, '_apply_luker_update')
        self.assertEqual(window.on_luker_path_changed.__name__, '_on_luker_path_changed')

    def test_closed_window_is_recreated(self):
        launcher = self._make_launcher()

        with patch.object(launcher_app, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()
            FakeSettingsWindow.instances[0].alive = False
            launcher._tray_anchor = (300, 400)
            launcher._open_settings_window()

        self.assertEqual(len(FakeSettingsWindow.instances), 2)
        self.assertEqual(FakeSettingsWindow.instances[1].anchor_point, (300, 400))

    def test_close_callback_clears_reference(self):
        launcher = self._make_launcher()
        window = object()
        launcher.settings_window = window

        launcher._on_settings_closed()

        self.assertIsNone(launcher.settings_window)

    def test_exiting_does_not_open_window(self):
        launcher = self._make_launcher()
        launcher._exiting = True

        with patch.object(launcher_app, "SettingsWindow", FakeSettingsWindow):
            launcher._open_settings_window()

        self.assertEqual(FakeSettingsWindow.instances, [])

    def test_show_tray_menu_stores_anchor(self):
        launcher = self._make_launcher()
        launcher.tray_menu = FakeTrayMenu()
        launcher.log_window = FakeLogWindow()
        launcher.process_manager = None
        launcher.gcl_process_manager = None

        launcher._show_tray_menu(12, 34)

        self.assertEqual(launcher._tray_anchor, (12, 34))
        self.assertEqual(launcher.tray_menu.point, (12, 34))


if __name__ == "__main__":
    unittest.main()
