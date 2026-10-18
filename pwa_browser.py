"""PWA 浏览器启动模块

使用 Edge 的 PWA 模式启动 Luker，这样标题栏颜色会自动跟随 Luker 主题色变化。

已安装 PWA 的 APPX 包信息通过两种方式获得（按优先级）：
1. 手动配置：launcher_config.json 中的 pwa_appx_family_name
2. 自动发现：扫描已安装的 APPX 包，匹配 DisplayName 为 "Luker" 的 PWA 包

如果 PWA 未安装，回退到 Edge 的 --app 应用窗口模式，最终回退到默认浏览器。
"""

import ctypes
import json
import re
import subprocess
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from config import config

# Windows APPX 包的默认 Application Id（来自 AppxManifest.xml 的 Application Id）
DEFAULT_APPX_APP_ID = "App"

# 自动发现失败后的重试间隔（秒）。成功结果会一直缓存。
DISCOVERY_RETRY_SECONDS = 60

# 自动发现结果的缓存；失败时用 checked_at 做退避，避免反复启动 PowerShell
_discovered_appx: Optional[Tuple[str, str]] = None
_discovery_checked_at = 0.0


def find_edge_path() -> Optional[str]:
    """查找 Edge 浏览器可执行文件路径"""
    possible_paths = [
        # 64位系统上的64位Edge
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        # 64位Edge
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # 用户安装的Edge
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def is_pwa_installed(app_id: str) -> bool:
    """检查指定 App ID 的 PWA 是否已安装

    通过检查 Edge 的 PWA 数据目录来判断
    """
    edge_user_data = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"))

    # 检查 Default 配置文件中的 Web Applications
    web_app_dir = edge_user_data / "Default" / "Web Applications"

    if web_app_dir.exists():
        # 检查是否存在与 Luker 相关的 PWA
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
    """检查指定的 APPX 包是否已安装

    通过 PowerShell 查询已安装的应用包
    """
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
    """自动发现已安装的 Luker PWA APPX 包

    Edge 安装 PWA 时会生成一个 APPX 包，包名形如 "127.0.0.1-XXXXXXXX"，
    其中哈希后缀由源地址（含端口）决定，无法预先得知。
    这里枚举所有候选包并读取其 AppxManifest.xml，
    匹配 DisplayName 为 "Luker" 的包。

    Returns:
        (PackageFamilyName, ApplicationId) 元组，未发现时返回 None
    """
    global _discovered_appx, _discovery_checked_at
    if _discovered_appx:
        return _discovered_appx
    # 上次扫描失败且仍在退避期内，直接返回，避免每次点击都启动 PowerShell
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
            print(f"[PWA] 自动发现 Luker APPX 包: {family_name}")
            return _discovered_appx

    except Exception as e:
        print(f"[PWA] 自动发现 APPX 包失败: {e}")

    return None


def open_as_appx(family_name: str, app_id: str = DEFAULT_APPX_APP_ID) -> bool:
    """通过 Windows Shell 协议启动已安装的 APPX PWA 应用

    这是启动标题栏颜色跟随主题的正确方式
    """
    # 使用 shell:AppsFolder 协议启动
    # 格式: shell:AppsFolder\{PackageFamilyName}!{AppId}
    app_uri = f"shell:AppsFolder\\{family_name}!{app_id}"

    try:
        # ShellExecuteW 返回 > 32 表示启动成功；失败时交给调用方回退到其他方式
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "open", app_uri, None, None, 1
        )
        if result > 32:
            print("[PWA] 通过 APPX 启动成功")
            return True
        print(f"[PWA] APPX 启动失败，ShellExecute 返回 {result}")
    except Exception as e:
        print(f"[PWA] APPX 启动失败: {e}")
    return False


def open_as_pwa(url: Optional[str] = None) -> bool:
    """以 PWA 模式打开 Luker

    优先使用已安装/已配置的 APPX 包启动（标题栏颜色跟随主题）
    如果 APPX 未安装，回退到 Edge --app-id 模式或 --app 模式

    Args:
        url: Luker 的 URL 地址，默认从配置中读取

    Returns:
        bool: 是否成功启动
    """
    if url is None:
        url = config.get_server_url()

    # 1. 优先使用配置文件中手动指定的 APPX 包
    configured_family = config.pwa_appx_family_name
    if configured_family:
        if is_appx_installed(configured_family):
            print("[PWA] 使用配置文件中指定的 APPX 包")
            if open_as_appx(configured_family):
                return True
            print("[PWA] 配置的 APPX 启动失败，尝试其他方式")
        else:
            print(f"[PWA] 配置的 APPX 包未安装: {configured_family}")

    # 2. 自动发现已安装的 Luker APPX 包
    discovered = discover_luker_appx()
    if discovered:
        family_name, app_id = discovered
        if open_as_appx(family_name, app_id):
            return True
        print("[PWA] 自动发现的 APPX 启动失败，尝试其他方式")

    edge_path = find_edge_path()

    if not edge_path:
        print("[PWA] 未找到 Edge 浏览器")
        return False

    # 3. 如果配置了 Edge PWA App ID 且已安装，使用 --app-id 参数启动
    app_id = config.pwa_app_id
    if app_id and is_pwa_installed(app_id):
        args = [
            edge_path,
            f"--app-id={app_id}",
            "--profile-directory=Default",
        ]
        print("[PWA] 使用 --app-id 模式启动")
    else:
        # 4. 如果 PWA 未安装，使用 --app 参数启动（简化的应用窗口模式）
        args = [
            edge_path,
            f"--app={url}",
            "--profile-directory=Default",
        ]
        print("[PWA] 使用 --app 模式启动（PWA 未安装）")

    try:
        subprocess.Popen(
            args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        print(f"[PWA] 启动失败: {e}")
        return False


def open_in_browser(url: Optional[str] = None, prefer_pwa: bool = True) -> bool:
    """打开 Luker 浏览器

    Args:
        url: Luker 的 URL 地址，默认从配置中读取
        prefer_pwa: 是否优先使用 PWA 模式

    Returns:
        bool: 是否成功启动
    """
    if url is None:
        url = config.get_server_url()

    if prefer_pwa:
        if open_as_pwa(url):
            return True
        print("[PWA] 回退到默认浏览器")

    # 回退到默认浏览器
    import webbrowser
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"[浏览器] 启动失败: {e}")
        return False


if __name__ == "__main__":
    # 测试
    print(f"Edge 路径: {find_edge_path()}")
    print(f"Luker 地址: {config.get_server_url()}")
    print(f"APPX 自动发现: {discover_luker_appx()}")
    print("正在启动...")
    open_in_browser()
