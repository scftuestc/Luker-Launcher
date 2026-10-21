"""路径选择对话框；配置模块只负责数据，不直接处理 UI。"""

import tkinter as tk
from tkinter import filedialog, messagebox

from config import config, get_app_dir


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
