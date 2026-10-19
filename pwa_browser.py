"""PWA 浏览器启动：优先 APPX，其次 Edge --app-id/--app，最后默认浏览器。"""

import ctypes
import json
import logging
import re
import subprocess
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from config import config

logger = logging.getLogger(__name__)

# AppxManifest.xml 未声明 Application Id 时的默认值
DEFAULT_APPX_APP_ID = "App"

# 自动发现失败后的重试间隔；成功结果永久缓存，失败按此间隔退避
DISCOVERY_RETRY_SECONDS = 60

_discovered_appx: Optional[Tuple[str, str]] = None
_discovery_checked_at = 0.0


def find_edge_path() -> Optional[str]:
    """查找 Edge 浏览器可执行文件路径"""
    possible_paths = [
        # Edge 的系统级和用户级安装位置
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def is_pwa_installed(app_id: str) -> bool:
    """通过 Edge 的 PWA 数据目录判断指定 App ID 是否已安装。"""
    edge_user_data = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"))

    # 检查 Default 配置文件中的 Web Applications
    web_app_dir = edge_user_data / "Default" / "Web Applications"

    if web_app_dir.exists():
        for item in web_app_dir.iterdir():
            if item.is_dir() and app_id in item.name:
                return True

    # 也检查其他可能的配置文件
    if edge_user_data.exists():
        for profile_dir in edge_user_data.iterdir():
            if profile_dir.is_dir() and profile_dir.name.startswith("Profile"):
                web_app_dir = profile_dir / "Web Applications"
                if web_app_dir.exists():
                    for item in web_app_dir.iterdir():
                        if item.is_dir() and app_id in item.name:
                            return True

    return False


def is_appx_installed(family_name: str) -> bool:
    """通过 PowerShell 查询指定 APPX 包是否已安装。"""
    package_name = family_name.split('_')[0]
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f"Get-AppxPackage -Name '{package_name}' | Select-Object -ExpandProperty PackageFullName"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def discover_luker_appx() -> Optional[Tuple[str, str]]:
    """扫描 127.0.0.1-* APPX 包，按 DisplayName 找到 Luker PWA。

    包名的哈希后缀由安装地址决定，无法直接拼出，所以枚举后读取 manifest。
    返回 (PackageFamilyName, ApplicationId)，未发现时返回 None。
    """
    global _discovered_appx, _discovery_checked_at
    if _discovered_appx:
        return _discovered_appx
    # 退避期内直接返回，避免反复启动 PowerShell
    if time.monotonic() - _discovery_checked_at < DISCOVERY_RETRY_SECONDS:
        return None
    _discovery_checked_at = time.monotonic()

    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-AppxPackage -Name '127.0.0.1-*' | "
             "Select-Object Name, PackageFamilyName, InstallLocation | ConvertTo-Json -Compress"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.strip()
        if not output:
            return None

        packages = json.loads(output)
        # 只有一个结果时 ConvertTo-Json 返回对象而非数组
        if isinstance(packages, dict):
            packages = [packages]

        for pkg in packages:
            install_location = pkg.get('InstallLocation')
            family_name = pkg.get('PackageFamilyName')
            if not install_location or not family_name:
                continue

            manifest_path = Path(install_location) / "AppxManifest.xml"
            try:
                manifest = manifest_path.read_text(encoding='utf-8')
            except Exception:
                continue

            # 匹配 <DisplayName>Luker</DisplayName> 或 DisplayName="Luker"
            if not re.search(r'DisplayName[">]\s*Luker\s*[<"]', manifest, re.IGNORECASE):
                continue

            app_id_match = re.search(r'<Application[^>]*\sId="([^"]+)"', manifest)
            app_id = app_id_match.group(1) if app_id_match else DEFAULT_APPX_APP_ID

            _discovered_appx = (family_name, app_id)
            logger.info("自动发现 Luker APPX 包: %s", family_name)
            return _discovered_appx

    except Exception as e:
        logger.warning("自动发现 APPX 包失败: %s", e)

    return None


def open_as_appx(family_name: str, app_id: str = DEFAULT_APPX_APP_ID) -> bool:
    """通过 shell:AppsFolder 启动已安装的 APPX PWA。"""
    # 格式: shell:AppsFolder\{PackageFamilyName}!{AppId}
    app_uri = f"shell:AppsFolder\\{family_name}!{app_id}"

    try:
        # ShellExecuteW 返回 > 32 表示启动成功；失败时交给调用方回退到其他方式
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "open", app_uri, None, None, 1
        )
        if result > 32:
            logger.info("通过 APPX 启动成功")
            return True
        logger.warning("APPX 启动失败，ShellExecute 返回 %s", result)
    except Exception as e:
        logger.warning("APPX 启动失败: %s", e)
    return False


def open_as_pwa(url: Optional[str] = None) -> bool:
    """按 APPX → Edge --app-id → Edge --app 的顺序打开 Luker。"""
    if url is None:
        url = config.get_server_url()

    # 优先使用配置文件中手动指定的 APPX 包
    configured_family = config.pwa_appx_family_name
    if configured_family:
        if is_appx_installed(configured_family):
            logger.info("使用配置文件中指定的 APPX 包")
            if open_as_appx(configured_family):
                return True
            logger.warning("配置的 APPX 启动失败，尝试其他方式")
        else:
            logger.warning("配置的 APPX 包未安装: %s", configured_family)

    # 其次自动发现已安装的 Luker APPX 包
    discovered = discover_luker_appx()
    if discovered:
        family_name, app_id = discovered
        if open_as_appx(family_name, app_id):
            return True
        logger.warning("自动发现的 APPX 启动失败，尝试其他方式")

    edge_path = find_edge_path()

    if not edge_path:
        logger.warning("未找到 Edge 浏览器")
        return False

    # 再尝试 Edge 的 --app-id 模式
    app_id = config.pwa_app_id
    if app_id and is_pwa_installed(app_id):
        args = [
            edge_path,
            f"--app-id={app_id}",
            "--profile-directory=Default",
        ]
        logger.info("使用 --app-id 模式启动")
    else:
        # PWA 未安装时使用普通应用窗口
        args = [
            edge_path,
            f"--app={url}",
            "--profile-directory=Default",
        ]
        logger.info("使用 --app 模式启动（PWA 未安装）")

    try:
        subprocess.Popen(
            args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        logger.warning("启动失败: %s", e)
        return False


def open_in_browser(url: Optional[str] = None, prefer_pwa: bool = True) -> bool:
    """打开 Luker；优先 PWA，失败时回退默认浏览器。"""
    if url is None:
        url = config.get_server_url()

    if prefer_pwa:
        if open_as_pwa(url):
            return True
        logger.info("回退到默认浏览器")

    import webbrowser
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        logger.warning("浏览器启动失败: %s", e)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Edge 路径: %s", find_edge_path())
    logger.info("Luker 地址: %s", config.get_server_url())
    logger.info("APPX 自动发现: %s", discover_luker_appx())
    logger.info("正在启动...")
    open_in_browser()
