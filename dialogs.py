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
from ui.window_utils import apply_window_rounding, get_ui_font

logger = logging.getLogger(__name__)

DIALOG_WIDTH = 440
DIALOG_HEIGHT = 230


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


def show_exit_confirmation(
    parent: tk.Misc,
    state: LukerState,
    on_confirm: Callable[[], None],
    on_cancel: Callable[[], None],
) -> None:
    """显示退出确认框；确认或取消后调用对应回调。"""
    ExitConfirmationDialog(parent, state, on_confirm, on_cancel)


class ExitConfirmationDialog(ctk.CTkToplevel):
    """退出确认框：退出会停止 Luker 进程并关闭启动器。"""

    def __init__(
        self,
        parent: tk.Misc,
        state: LukerState,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent)

        self._parent = parent
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._closed = False
        self.COLORS = config.get_theme_colors()
        self.UI_FONT = get_ui_font()

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
            text="退出 Luker",
            font=ctk.CTkFont(family=self.UI_FONT, size=17, weight="bold"),
            text_color=self.COLORS['text'],
            anchor="w",
        ).pack(fill="x")

        if state is LukerState.STOPPED:
            message = "Luker 当前未运行。\n确定要关闭 Luker Launcher 吗？"
        else:
            message = "退出会停止 Luker 进程，并关闭 Luker Launcher。\n确定要退出吗？"

        ctk.CTkLabel(
            content,
            text=message,
            font=ctk.CTkFont(family=self.UI_FONT, size=13),
            text_color=self.COLORS['text_dim'],
            justify="left",
            anchor="w",
            wraplength=380,
        ).pack(fill="x", pady=(10, 18))

        buttons = ctk.CTkFrame(content, fg_color="transparent")
        buttons.pack(side="bottom", fill="x")

        self._cancel_btn = make_button(
            buttons,
            'secondary',
            self.COLORS,
            text="取消",
            width=100,
            height=36,
            font_family=self.UI_FONT,
            command=self._cancel,
        )
        self._cancel_btn.pack(side="right")

        self._confirm_btn = make_button(
            buttons,
            'danger',
            self.COLORS,
            text="退出 Luker",
            width=124,
            height=36,
            font_family=self.UI_FONT,
            command=self._confirm,
        )
        self._confirm_btn.pack(side="right", padx=(0, 8))

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
        apply_window_rounding(self, context="退出确认")
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            logger.debug("退出确认框 grab_set 失败", exc_info=True)
        self._cancel_btn.focus_set()

    def _confirm(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._close_window()
        self._on_confirm()

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
    """让用户选择 Luker 安装目录并校验，返回有效路径或 None。"""
    owner, temp_root = _dialog_owner(parent)
    try:
        messagebox.showinfo(
            "Luker 启动器",
            "请选择 Luker 的安装目录\n（包含 Start.bat 的文件夹）",
            parent=owner,
        )

        path = filedialog.askdirectory(
            title="选择 Luker 安装目录",
            parent=owner,
        )
        if not path:
            return None

        if config.is_valid_luker_path(path):
            config.luker_path = path
            return path

        messagebox.showerror(
            "错误",
            f"所选目录不是有效的 Luker 安装目录！\n"
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
