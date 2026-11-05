"""应用目录与打包资源路径。"""

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """返回程序所在目录，兼容 PyInstaller 打包后的 exe。"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    # luker_launcher/paths.py 的上一级是仓库根目录
    return Path(__file__).resolve().parent.parent


def get_bundle_dir() -> Path:
    """返回只读资源目录：打包后为 _MEIPASS，源码运行为仓库根目录。"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def resource_path(name: str) -> Path:
    """返回随程序打包的只读资源路径。"""
    return get_bundle_dir() / name
