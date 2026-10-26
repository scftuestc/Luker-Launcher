"""主题化确认对话框与路径选择对话框。"""

import contextlib
import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import config, get_app_dir
from core.readiness import LukerState
from ui.buttons import make_button
from ui.dpi import format_geometry
from ui.theme import shade_color
from ui.window_utils import apply_window_rounding, get_ui_font

logger = logging.getLogger(__name__)

DIALOG_WIDTH = 480
DIALOG_HEIGHT = 300


def dialog_position(
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    dialog_width: int,
    dialog_height: int,
) -> tuple[int, int]:
    """按父窗口计算确认框坐标；副屏在左侧或上方时允许负坐标。"""
    return (
        parent_x + (parent_width - dialog_width) // 2,
        parent_y + (parent_height - dialog_height) // 3,
    )


def close_dialog_message(state: LukerState, *, allow_hide: bool) -> str:
    """关闭窗口对话框的正文；托盘不可用时只说明退出。"""
    if not allow_hide:
        return "系统托盘不可用。\n关闭窗口将退出 Luker Launcher。"
    if state is LukerState.STOPPED:
        return "Luker 当前未运行。\n关闭窗口后要隐藏到系统托盘，还是退出 Luker Launcher？"
    return "Luker 正在运行。\n隐藏到托盘会保持 Luker 继续运行；退出程序会停止 Luker 并关闭启动器。"


def show_close_choice(
    parent: tk.Misc,
    state: LukerState,
    *,
    allow_hide: bool,
    on_hide: Callable[[bool], None],
    on_exit: Callable[[bool], None],
    on_cancel: Callable[[], None],
) -> None:
    """显示关闭窗口选择框；隐藏/退出回调携带“记住选择”的勾选状态。"""
    CloseChoiceDialog(
        parent,
        state,
        allow_hide=allow_hide,
        on_hide=on_hide,
        on_exit=on_exit,
        on_cancel=on_cancel,
    )


class CloseChoiceDialog(ctk.CTkToplevel):
    """关闭窗口选择框：隐藏到托盘、退出程序或取消，可记住选择。"""

    def __init__(
        self,
        parent: tk.Misc,
        state: LukerState,
        *,
        allow_hide: bool,
        on_hide: Callable[[bool], None],
        on_exit: Callable[[bool], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent)

        self._parent = parent
        self._allow_hide = allow_hide
        self._on_hide = on_hide
        self._on_exit = on_exit
        self._on_cancel = on_cancel
        self._closed = False
        self.COLORS = config.get_theme_colors()
        self.UI_FONT = get_ui_font()
        self._remember_var = tk.IntVar(master=self, value=0)

        self.withdraw()
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 1.0)
        self.transient(parent)
        self.configure(fg_color=self.COLORS['card'])

        self._build_ui(state)
        self.bind('<Escape>', lambda _event: self._cancel())
        self.bind('<Alt-F4>', lambda _event: self._cancel())
        self.after(0, self._present)

    def _build_ui(self, state: LukerState) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            content,
            text="关闭 Luker Launcher",
            font=ctk.CTkFont(family=self.UI_FONT, size=17, weight="bold"),
            text_color=self.COLORS['text'],
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            content,
            text=close_dialog_message(state, allow_hide=self._allow_hide),
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text_dim'],
            justify="left",
            anchor="w",
            wraplength=420,
        ).pack(fill="x", pady=(10, 12))

        ctk.CTkCheckBox(
            content,
            text="记住我的选择",
            variable=self._remember_var,
            onvalue=1,
            offvalue=0,
            font=ctk.CTkFont(family=self.UI_FONT, size=12),
            text_color=self.COLORS['text_dim'],
            fg_color=self.COLORS['accent'],
            hover_color=shade_color(self.COLORS['accent'], 0.85),
            border_color=self.COLORS['border'],
            checkmark_color=self.COLORS['on_accent'],
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            border_width=2,
        ).pack(anchor="w", pady=(0, 16))

        buttons = ctk.CTkFrame(content, fg_color="transparent")
        buttons.pack(side="bottom", fill="x")

        self._cancel_btn = make_button(
            buttons,
            'secondary',
            self.COLORS,
            text="取消",
            width=96,
            height=36,
            font_family=self.UI_FONT,
            command=self._cancel,
        )
        self._cancel_btn.pack(side="right")

        self._exit_btn = make_button(
            buttons,
            'danger',
            self.COLORS,
            text="退出程序",
            width=112,
            height=36,
            font_family=self.UI_FONT,
            command=self._exit,
        )
        self._exit_btn.pack(side="right", padx=(0, 8))

        if self._allow_hide:
            self._hide_btn = make_button(
                buttons,
                'primary',
                self.COLORS,
                text="隐藏到托盘",
                width=124,
                height=36,
                font_family=self.UI_FONT,
                command=self._hide,
            )
            self._hide_btn.pack(side="right", padx=(0, 8))

    def _present(self) -> None:
        if self._closed or not self.winfo_exists():
            return

        self.update_idletasks()
        try:
            scale = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            scale = 1.0
        width = round(DIALOG_WIDTH * scale)
        height = round(DIALOG_HEIGHT * scale)

        try:
            self._parent.update_idletasks()
            x, y = dialog_position(
                self._parent.winfo_rootx(),
                self._parent.winfo_rooty(),
                self._parent.winfo_width(),
                self._parent.winfo_height(),
                width,
                height,
            )
        except tk.TclError:
            x, y = 0, 0

        # 负坐标交给 format_geometry 编码；不能夹到 0，否则左侧副屏会跑到主屏边缘
        self.geometry(format_geometry(DIALOG_WIDTH, DIALOG_HEIGHT, x, y))
        self.deiconify()
        apply_window_rounding(self, context="关闭窗口")
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            logger.debug("关闭窗口选择框 grab_set 失败", exc_info=True)
        self._cancel_btn.focus_set()

    def _remember_selected(self) -> bool:
        try:
            return self._remember_var.get() == 1
        except tk.TclError:
            return False

    def _hide(self) -> None:
        if self._closed:
            return
        remember = self._remember_selected()
        self._closed = True
        self._close_window()
        self._on_hide(remember)

    def _exit(self) -> None:
        if self._closed:
            return
        remember = self._remember_selected()
        self._closed = True
        self._close_window()
        self._on_exit(remember)

    def _cancel(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._close_window()
        self._on_cancel()

    def _close_window(self) -> None:
        with contextlib.suppress(tk.TclError):
            self.grab_release()
        self.destroy()


def _dialog_owner(
    parent: tk.Tk | tk.Toplevel | None = None,
) -> tuple[tk.Tk | tk.Toplevel, tk.Tk | None]:
    """优先使用现有窗口作为对话框父窗口，否则创建一个临时隐藏根窗口。"""
    if parent is not None:
        try:
            if parent.winfo_exists():
                parent.attributes('-topmost', True)
                return parent, None
        except tk.TclError:
            pass

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    return root, root


def select_luker_path(parent: tk.Tk | tk.Toplevel | None = None) -> str | None:
    """让用户选择 Luker 安装根目录并校验，返回有效路径或 None。"""
    owner, temp_root = _dialog_owner(parent)
    try:
        messagebox.showinfo(
            "Luker 启动器",
            "请选择 Luker 的安装根目录\n该目录应包含 Start.bat 和 server.js。",
            parent=owner,
        )

        path = filedialog.askdirectory(
            title="选择 Luker 安装根目录",
            parent=owner,
        )
        if not path:
            return None

        if config.is_valid_luker_path(path):
            config.luker_path = path
            return path

        messagebox.showerror(
            "错误",
            f"所选目录不是有效的 Luker 安装根目录！\n"
            f"未找到 Start.bat 或 server.js 文件。\n\n"
            f"选择的路径: {path}",
            parent=owner,
        )
        return None
    finally:
        if temp_root is not None:
            temp_root.destroy()


def select_gcl_bat_path(parent: tk.Tk | tk.Toplevel | None = None) -> str | None:
    """选择 GCL 的 start.bat 文件并校验，返回有效路径或 None。"""
    owner, temp_root = _dialog_owner(parent)
    try:
        path = filedialog.askopenfilename(
            title="选择 GCL 的 start.bat 文件",
            filetypes=[("批处理文件", "*.bat"), ("所有文件", "*.*")],
            parent=owner,
        )
        if not path:
            return None

        if config.is_valid_gcl_path(path):
            config.gcl_bat_path = path
            return path

        messagebox.showerror(
            "错误",
            f"所选文件不是有效的批处理文件！\n\n选择的路径: {path}",
            parent=owner,
        )
        return None
    finally:
        if temp_root is not None:
            temp_root.destroy()


def ensure_luker_path_configured() -> bool:
    """确保已配置有效的 Luker 路径，否则引导用户选择。"""
    if config.luker_path and config.is_valid_luker_path(config.luker_path):
        return True

    # 启动器放在 Luker 根目录时直接识别，省去首次选择路径
    app_dir = str(get_app_dir())
    if config.is_valid_luker_path(app_dir):
        config.luker_path = app_dir
        return True

    return select_luker_path() is not None
