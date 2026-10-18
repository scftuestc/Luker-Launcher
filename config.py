import json
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Callable, List
import tkinter as tk
from tkinter import filedialog, messagebox


def get_app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


PRESET_THEMES = {
    'deep_blue': {
        'name': '深蓝夜空',
        'bg': '#0d1117',
        'card': '#161b22',
        'card_hover': '#21262d',
        'border': '#30363d',
        'text': '#f0f6fc',
        'text_dim': '#8b949e',
        'text_muted': '#6e7681',
        'accent': '#22d3ee',
        'accent_blue': '#58a6ff',
        'success': '#3fb950',
        'error': '#f85149',
        'warning': '#d29922',
        'info': '#58a6ff',
    },
    'purple_night': {
        'name': '紫罗兰夜',
        'bg': '#13111c',
        'card': '#1a1625',
        'card_hover': '#252131',
        'border': '#3d3654',
        'text': '#f4f0ff',
        'text_dim': '#a599c9',
        'text_muted': '#7a6c9a',
        'accent': '#c084fc',
        'accent_blue': '#a78bfa',
        'success': '#4ade80',
        'error': '#f87171',
        'warning': '#fbbf24',
        'info': '#a78bfa',
    },
    'forest_green': {
        'name': '森林绿意',
        'bg': '#0f1610',
        'card': '#161f18',
        'card_hover': '#1e2a21',
        'border': '#2d4033',
        'text': '#e8f5e9',
        'text_dim': '#9cbc9e',
        'text_muted': '#6a8a6c',
        'accent': '#4ade80',
        'accent_blue': '#34d399',
        'success': '#22c55e',
        'error': '#ef4444',
        'warning': '#eab308',
        'info': '#34d399',
    },
    'warm_orange': {
        'name': '暖橙黄昏',
        'bg': '#171310',
        'card': '#211c17',
        'card_hover': '#2c251e',
        'border': '#44392d',
        'text': '#fef3e2',
        'text_dim': '#c9a982',
        'text_muted': '#9a7d5a',
        'accent': '#fb923c',
        'accent_blue': '#f59e0b',
        'success': '#84cc16',
        'error': '#ef4444',
        'warning': '#f59e0b',
        'info': '#fb923c',
    },
    'ocean_cyan': {
        'name': '深海青碧',
        'bg': '#0c1415',
        'card': '#121e1f',
        'card_hover': '#1a2a2c',
        'border': '#2a4245',
        'text': '#e0f7fa',
        'text_dim': '#80cbc4',
        'text_muted': '#4db6ac',
        'accent': '#22d3ee',
        'accent_blue': '#06b6d4',
        'success': '#2dd4bf',
        'error': '#f87171',
        'warning': '#fbbf24',
        'info': '#22d3ee',
    },
    'rose_pink': {
        'name': '玫瑰粉黛',
        'bg': '#18101a',
        'card': '#231a25',
        'card_hover': '#2f2432',
        'border': '#4a3850',
        'text': '#fdf2f8',
        'text_dim': '#d8a9c4',
        'text_muted': '#a87d94',
        'accent': '#f472b6',
        'accent_blue': '#ec4899',
        'success': '#4ade80',
        'error': '#fb7185',
        'warning': '#fbbf24',
        'info': '#f472b6',
    },
}

DEFAULT_THEME = 'deep_blue'

# Luker 默认端口（与 server.js 的默认配置一致，实际端口以 Luker config.yaml 为准）
DEFAULT_PORT = 8000
# GCL 默认访问地址
DEFAULT_GCL_URL = "http://127.0.0.1:7861/"


class Config:
    CONFIG_FILE = "launcher_config.json"

    def __init__(self):
        self.config_path = get_app_dir() / self.CONFIG_FILE
        self._config = self._load_config()
        self._theme_change_callbacks: List[Callable[[Dict[str, str]], None]] = []
        self._gcl_change_callbacks: List[Callable[[bool, Optional[str]], None]] = []

    def _load_config(self) -> dict:
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_config(self) -> None:
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def add_theme_change_callback(self, callback: Callable[[Dict[str, str]], None]) -> None:
        self._theme_change_callbacks.append(callback)

    def remove_theme_change_callback(self, callback: Callable[[Dict[str, str]], None]) -> None:
        if callback in self._theme_change_callbacks:
            self._theme_change_callbacks.remove(callback)

    def _notify_theme_change(self) -> None:
        theme = self.get_theme_colors()
        for callback in self._theme_change_callbacks:
            try:
                callback(theme)
            except Exception as e:
                print(f"主题回调错误: {e}")

    def add_gcl_change_callback(self, callback: Callable[[bool, Optional[str]], None]) -> None:
        """添加 GCL 配置变更回调"""
        self._gcl_change_callbacks.append(callback)

    def remove_gcl_change_callback(self, callback: Callable[[bool, Optional[str]], None]) -> None:
        """移除 GCL 配置变更回调"""
        if callback in self._gcl_change_callbacks:
            self._gcl_change_callbacks.remove(callback)

    def _notify_gcl_change(self) -> None:
        """通知 GCL 配置变更"""
        enabled = self.gcl_enabled
        path = self.gcl_bat_path
        for callback in self._gcl_change_callbacks:
            try:
                callback(enabled, path)
            except Exception as e:
                print(f"GCL 配置回调错误: {e}")

    @property
    def theme_name(self) -> str:
        return self._config.get('theme', DEFAULT_THEME)

    @theme_name.setter
    def theme_name(self, name: str) -> None:
        if name in PRESET_THEMES:
            self._config['theme'] = name
            self._save_config()
            self._notify_theme_change()

    def get_theme_colors(self) -> Dict[str, str]:
        theme_name = self.theme_name
        if theme_name in PRESET_THEMES:
            return PRESET_THEMES[theme_name].copy()
        return PRESET_THEMES[DEFAULT_THEME].copy()

    def get_all_themes(self) -> Dict[str, Dict[str, str]]:
        return PRESET_THEMES.copy()

    @property
    def use_pwa_mode(self) -> bool:
        """是否使用 PWA 模式打开浏览器（标题栏颜色跟随 Luker 主题）"""
        return self._config.get('use_pwa_mode', False)  # 默认关闭

    @use_pwa_mode.setter
    def use_pwa_mode(self, value: bool) -> None:
        self._config['use_pwa_mode'] = value
        self._save_config()

    @property
    def pwa_app_id(self) -> Optional[str]:
        """Edge PWA 应用 ID（可选，用于 --app-id 启动模式）

        安装 Luker PWA 后，可在 Edge 的
        %LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\Default\\Web Applications
        目录下找到对应的应用 ID。
        """
        return self._config.get('pwa_app_id')

    @pwa_app_id.setter
    def pwa_app_id(self, value: str) -> None:
        self._config['pwa_app_id'] = value
        self._save_config()

    @property
    def pwa_appx_family_name(self) -> Optional[str]:
        """已安装 Luker PWA 的 APPX PackageFamilyName（可选）

        形如 "127.0.0.1-XXXXXXXX_xxxxxxxxxxxxx"。
        可通过 PowerShell 命令 Get-AppxPackage -Name '127.0.0.1-*' 查询。
        不配置时会自动按 DisplayName 发现已安装的 Luker PWA。
        """
        return self._config.get('pwa_appx_family_name')

    @pwa_appx_family_name.setter
    def pwa_appx_family_name(self, value: str) -> None:
        self._config['pwa_appx_family_name'] = value
        self._save_config()

    @property
    def gcl_enabled(self) -> bool:
        """是否启用 GCL 功能"""
        return self._config.get('gcl_enabled', False)  # 默认关闭

    @gcl_enabled.setter
    def gcl_enabled(self, value: bool) -> None:
        self._config['gcl_enabled'] = value
        self._save_config()
        self._notify_gcl_change()

    @property
    def gcl_bat_path(self) -> Optional[str]:
        """GCL 的 start.bat 路径"""
        return self._config.get('gcl_bat_path')

    @gcl_bat_path.setter
    def gcl_bat_path(self, path: str) -> None:
        self._config['gcl_bat_path'] = path
        self._save_config()
        self._notify_gcl_change()

    @property
    def gcl_url(self) -> str:
        """GCL 的本地访问地址"""
        return self._config.get('gcl_url', DEFAULT_GCL_URL)

    def is_valid_gcl_path(self, path: str) -> bool:
        """验证 GCL bat 路径是否有效"""
        p = Path(path)
        return p.exists() and p.suffix.lower() == '.bat'

    def select_gcl_bat_path(self) -> Optional[str]:
        """选择 GCL 的 start.bat 文件"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        from tkinter import filedialog as fd
        path = fd.askopenfilename(
            title="选择 GCL 的 start.bat 文件",
            filetypes=[("批处理文件", "*.bat"), ("所有文件", "*.*")]
        )

        root.destroy()

        if path:
            if self.is_valid_gcl_path(path):
                self.gcl_bat_path = path
                return path
            else:
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "错误",
                    f"所选文件不是有效的批处理文件！\n\n"
                    f"选择的路径: {path}"
                )
                root.destroy()
                return None
        return None

    @property
    def luker_path(self) -> Optional[str]:
        path = self._config.get('luker_path')
        if path:
            return path
        # 兼容旧版 SillyTavern 启动器遗留下来的配置文件
        return self._config.get('sillytavern_path')

    @luker_path.setter
    def luker_path(self, path: str) -> None:
        self._config['luker_path'] = path
        # 写入新键后清理旧键，避免歧义
        self._config.pop('sillytavern_path', None)
        self._save_config()

    @property
    def start_bat_path(self) -> Optional[Path]:
        if self.luker_path:
            return Path(self.luker_path) / "Start.bat"
        return None

    def get_server_port(self) -> int:
        """从 Luker 的 config.yaml 读取服务端口，读取失败时返回默认端口"""
        if self.luker_path:
            config_yaml = Path(self.luker_path) / "config.yaml"
            try:
                text = config_yaml.read_text(encoding='utf-8')
                # 只匹配顶层的 port 配置（行首无缩进），
                # 忽略 browserLaunch.port 等缩进的嵌套配置项
                match = re.search(r'^port:\s*(\d+)', text, re.MULTILINE)
                if match:
                    return int(match.group(1))
            except Exception:
                pass
        return DEFAULT_PORT

    def get_server_url(self) -> str:
        """获取 Luker 的本地访问地址"""
        return f"http://127.0.0.1:{self.get_server_port()}"

    def is_valid_luker_path(self, path: str) -> bool:
        p = Path(path)
        start_bat = p / "Start.bat"
        server_js = p / "server.js"
        return start_bat.exists() and server_js.exists()

    def select_luker_path(self) -> Optional[str]:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        messagebox.showinfo(
            "Luker 启动器",
            "请选择 Luker 的安装目录\n（包含 Start.bat 的文件夹）"
        )

        path = filedialog.askdirectory(
            title="选择 Luker 安装目录"
        )

        root.destroy()

        if path:
            if self.is_valid_luker_path(path):
                self.luker_path = path
                return path
            else:
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "错误",
                    f"所选目录不是有效的 Luker 安装目录！\n"
                    f"未找到 Start.bat 或 server.js 文件。\n\n"
                    f"选择的路径: {path}"
                )
                root.destroy()
                return None
        return None

    def ensure_path_configured(self) -> bool:
        if self.luker_path and self.is_valid_luker_path(self.luker_path):
            return True

        path = self.select_luker_path()
        return path is not None


config = Config()
