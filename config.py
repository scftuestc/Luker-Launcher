"""启动器配置读写与路径校验。"""

import contextlib
import json
import logging
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ui.theme import DEFAULT_THEME, LEGACY_THEME_ALIASES, PRESET_THEMES
from ui.theme import get_theme_colors as _get_theme_colors

logger = logging.getLogger(__name__)


def get_app_dir() -> Path:
    """返回程序所在目录，兼容 PyInstaller 打包后的 exe。"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# 修改版本号时同步更新 version_info.txt；tests/test_version.py 会校验一致性
APP_VERSION = "3.3"

# Luker 默认端口（与 server.js 的默认配置一致，实际端口以 Luker config.yaml 为准）
DEFAULT_PORT = 8000
# GCL 默认访问地址
DEFAULT_GCL_URL = "http://127.0.0.1:7861/"
# 点击日志窗口关闭按钮时的行为：每次询问 / 隐藏到托盘 / 退出程序
CLOSE_BEHAVIORS = ('ask', 'tray', 'exit')
DEFAULT_CLOSE_BEHAVIOR = 'ask'

# 配置文件允许的键和类型；读取时统一过滤，避免手改配置导致运行时类型错误
_STRING_KEYS = (
    "luker_path",
    "sillytavern_path",
    "gcl_bat_path",
    "gcl_url",
    "pwa_app_id",
    "pwa_appx_family_name",
)
_BOOL_KEYS = ("use_pwa_mode", "gcl_enabled", "blur_enabled")


def _is_regular_file(path: Path) -> bool:
    """判断路径是否为普通文件；不可访问或非法路径一律视为无效。"""
    try:
        return path.is_file()
    except (OSError, ValueError):
        return False


class Config:
    """launcher_config.json 的读写与主题/GCL/毛玻璃/关闭行为变更通知。"""

    CONFIG_FILE = "launcher_config.json"

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = (
            Path(config_path) if config_path is not None else get_app_dir() / self.CONFIG_FILE
        )
        self._config: dict[str, Any] = self._load_config()
        self._theme_change_callbacks: list[Callable[[dict[str, str]], None]] = []
        self._gcl_change_callbacks: list[Callable[[bool, str | None], None]] = []
        self._blur_change_callbacks: list[Callable[[bool], None]] = []
        self._close_behavior_callbacks: list[Callable[[str], None]] = []

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, UnicodeError, json.JSONDecodeError) as e:
            logger.warning("读取配置失败，使用默认配置: %s", e)
            return {}

        if not isinstance(data, dict):
            logger.warning("配置文件内容不是对象，使用默认配置")
            return {}

        return self._normalize(data)

    @staticmethod
    def _normalize(data: dict[str, Any]) -> dict[str, Any]:
        """只保留已知键，并丢弃类型不正确的值。"""
        normalized: dict[str, Any] = {}

        for key in _STRING_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                normalized[key] = value.strip()

        for key in _BOOL_KEYS:
            value = data.get(key)
            if isinstance(value, bool):
                normalized[key] = value

        theme = data.get('theme')
        if isinstance(theme, str):
            theme = LEGACY_THEME_ALIASES.get(theme, theme)
            if theme in PRESET_THEMES:
                normalized['theme'] = theme

        close_behavior = data.get('close_behavior')
        if isinstance(close_behavior, str) and close_behavior in CLOSE_BEHAVIORS:
            normalized['close_behavior'] = close_behavior

        return normalized

    def _save_config(self) -> bool:
        """原子写入配置，避免写到一半崩溃时留下损坏的 JSON。"""
        temp_path = self.config_path.with_name(self.config_path.name + ".tmp")
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.config_path)
            return True
        except (OSError, UnicodeError) as e:
            logger.error("保存配置失败: %s", e)
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)
            return False

    def add_theme_change_callback(self, callback: Callable[[dict[str, str]], None]) -> None:
        self._theme_change_callbacks.append(callback)

    def remove_theme_change_callback(self, callback: Callable[[dict[str, str]], None]) -> None:
        if callback in self._theme_change_callbacks:
            self._theme_change_callbacks.remove(callback)

    def _notify_theme_change(self) -> None:
        theme = self.get_theme_colors()
        for callback in self._theme_change_callbacks:
            try:
                callback(theme)
            except Exception:
                logger.exception("主题回调执行失败")

    def add_gcl_change_callback(self, callback: Callable[[bool, str | None], None]) -> None:
        """添加 GCL 配置变更回调"""
        self._gcl_change_callbacks.append(callback)

    def remove_gcl_change_callback(self, callback: Callable[[bool, str | None], None]) -> None:
        """移除 GCL 配置变更回调；未注册时忽略。"""
        if callback in self._gcl_change_callbacks:
            self._gcl_change_callbacks.remove(callback)

    def _notify_gcl_change(self) -> None:
        """通知 GCL 配置变更"""
        enabled = self.gcl_enabled
        path = self.gcl_bat_path
        for callback in self._gcl_change_callbacks:
            try:
                callback(enabled, path)
            except Exception:
                logger.exception("GCL 配置回调执行失败")

    def add_blur_change_callback(self, callback: Callable[[bool], None]) -> None:
        """添加毛玻璃开关变更回调。"""
        self._blur_change_callbacks.append(callback)

    def remove_blur_change_callback(self, callback: Callable[[bool], None]) -> None:
        """移除毛玻璃开关变更回调；未注册时忽略。"""
        if callback in self._blur_change_callbacks:
            self._blur_change_callbacks.remove(callback)

    def _notify_blur_change(self) -> None:
        enabled = self.blur_enabled
        for callback in self._blur_change_callbacks:
            try:
                callback(enabled)
            except Exception:
                logger.exception("毛玻璃配置回调执行失败")

    def add_close_behavior_change_callback(self, callback: Callable[[str], None]) -> None:
        """添加关闭窗口行为变更回调。"""
        self._close_behavior_callbacks.append(callback)

    def remove_close_behavior_change_callback(self, callback: Callable[[str], None]) -> None:
        """移除关闭窗口行为变更回调；未注册时忽略。"""
        if callback in self._close_behavior_callbacks:
            self._close_behavior_callbacks.remove(callback)

    def _notify_close_behavior_change(self) -> None:
        behavior = self.close_behavior
        for callback in self._close_behavior_callbacks:
            try:
                callback(behavior)
            except Exception:
                logger.exception("关闭窗口行为回调执行失败")

    @property
    def theme_name(self) -> str:
        name = self._config.get('theme', DEFAULT_THEME)
        return LEGACY_THEME_ALIASES.get(name, name)

    @theme_name.setter
    def theme_name(self, name: str) -> None:
        name = LEGACY_THEME_ALIASES.get(name, name)
        if name in PRESET_THEMES:
            self._config['theme'] = name
            self._save_config()
            self._notify_theme_change()

    def get_theme_colors(self) -> dict[str, str]:
        return _get_theme_colors(self.theme_name)

    @property
    def use_pwa_mode(self) -> bool:
        """是否使用 PWA 模式打开浏览器（标题栏颜色跟随 Luker 主题）"""
        return bool(self._config.get('use_pwa_mode', False))

    @use_pwa_mode.setter
    def use_pwa_mode(self, value: bool) -> None:
        self._config['use_pwa_mode'] = bool(value)
        self._save_config()

    @property
    def blur_enabled(self) -> bool:
        """是否启用窗口毛玻璃与半透明效果。"""
        return bool(self._config.get('blur_enabled', True))

    @blur_enabled.setter
    def blur_enabled(self, value: bool) -> None:
        self._config['blur_enabled'] = bool(value)
        self._save_config()
        self._notify_blur_change()

    @property
    def close_behavior(self) -> str:
        """点击日志窗口关闭按钮时的行为：ask / tray / exit。"""
        value = self._config.get('close_behavior', DEFAULT_CLOSE_BEHAVIOR)
        return value if value in CLOSE_BEHAVIORS else DEFAULT_CLOSE_BEHAVIOR

    @close_behavior.setter
    def close_behavior(self, value: str) -> None:
        if value not in CLOSE_BEHAVIORS:
            return
        self._config['close_behavior'] = value
        self._save_config()
        self._notify_close_behavior_change()

    @property
    def pwa_app_id(self) -> str | None:
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
    def pwa_appx_family_name(self) -> str | None:
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
        return bool(self._config.get('gcl_enabled', False))

    @gcl_enabled.setter
    def gcl_enabled(self, value: bool) -> None:
        self._config['gcl_enabled'] = bool(value)
        self._save_config()
        self._notify_gcl_change()

    @property
    def gcl_bat_path(self) -> str | None:
        """GCL 的 start.bat 路径"""
        return self._config.get('gcl_bat_path')

    @gcl_bat_path.setter
    def gcl_bat_path(self, path: str | None) -> None:
        self._config['gcl_bat_path'] = path
        self._save_config()
        self._notify_gcl_change()

    @property
    def gcl_url(self) -> str:
        """GCL 的本地访问地址"""
        return self._config.get('gcl_url', DEFAULT_GCL_URL)

    def is_valid_gcl_path(self, path: str | None) -> bool:
        """验证 GCL bat 路径是否有效"""
        if not path:
            return False
        p = Path(path)
        return p.suffix.lower() == '.bat' and _is_regular_file(p)

    @property
    def luker_path(self) -> str | None:
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

    def get_server_port(self) -> int:
        """从 Luker 的 config.yaml 读取服务端口，读取失败时返回默认端口"""
        if not self.luker_path:
            return DEFAULT_PORT

        config_yaml = Path(self.luker_path) / "config.yaml"
        try:
            text = config_yaml.read_text(encoding='utf-8')
        except (OSError, UnicodeError, ValueError) as e:
            logger.warning("读取 Luker config.yaml 失败，使用默认端口: %s", e)
            return DEFAULT_PORT

        # 只匹配顶层的 port 配置（行首无缩进），
        # 忽略 browserLaunch.port 等缩进的嵌套配置项
        match = re.search(r'^port:\s*["\']?(\d+)["\']?\s*(?:#.*)?$', text, re.MULTILINE)
        if match:
            port = int(match.group(1))
            if 1 <= port <= 65535:
                return port
        return DEFAULT_PORT

    def get_server_url(self) -> str:
        """获取 Luker 的本地访问地址"""
        return f"http://127.0.0.1:{self.get_server_port()}"

    def is_valid_luker_path(self, path: str | None) -> bool:
        if not path:
            return False
        p = Path(path)
        start_bat = p / "Start.bat"
        server_js = p / "server.js"
        return _is_regular_file(start_bat) and _is_regular_file(server_js)


config = Config()
