# 🍀 Luker 启动器 Luker Launcher

一个简洁的 [Luker](https://github.com/) 启动器，让你优雅地管理 Luker 进程。
（由 SillyTavern-Launcher 改造而来）

## ✨ 功能

- **系统托盘运行** - 最小化到托盘，不占用任务栏
- **一键启停** - 启动、停止、重启 Luker
- **实时日志** - 毛玻璃效果的日志窗口，支持自动滚动与搜索
- **日志分隔线** - 超过 1 分钟的日志自动插入分隔线，复制时不会被选中
- **多彩主题** - 内置 6 款主题配色，点击即可切换
- **进程管理** - 自动管理 Luker 进程树，干净退出
- **PWA 模式** - 以 PWA 应用窗口打开 Luker，标题栏颜色跟随主题
- **GCL 联动** - 可选的 GCL 进程管理与日志切换
- **端口自适应** - 自动读取 Luker `config.yaml` 中的 `port` 配置

## 📦 安装

### 直接使用

运行 `打包.bat` 生成 `Luker-Launcher.exe`，双击运行即可。

### 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 打包为 exe

```bash
pip install pyinstaller
pyinstaller launcher.spec
```

或者直接运行 `打包.bat`。

## 🎨 主题

| 主题   | 预览               |
| ------ | ------------------ |
| 🌊 深蓝 | 默认主题，深蓝夜空 |
| 🔮 紫夜 | 紫罗兰之夜         |
| 🌲 森林 | 森林绿意           |
| 🌅 暖橙 | 暖橙黄昏           |
| 🌴 海洋 | 深海青碧           |
| 🌸 玫瑰 | 玫瑰粉黛           |

## 🖱️ 使用

1. 首次运行会要求选择 Luker 安装目录（包含 `Start.bat` 的文件夹）
2. 启动后自动最小化到系统托盘
3. 单击托盘图标：显示/隐藏日志窗口
4. 右键托盘图标：打开菜单（启停 Luker、打开页面、设置、退出）

## ⚙️ 配置

配置文件 `launcher_config.json` 保存在程序同目录下：

```json
{
  "luker_path": "D:/AI/Luker",
  "use_pwa_mode": true,
  "theme": "ocean_cyan",
  "gcl_enabled": false
}
```

| 键 | 说明 |
| --- | --- |
| `luker_path` | Luker 安装目录 |
| `use_pwa_mode` | 是否使用 PWA 模式打开浏览器 |
| `theme` | 主题名称 |
| `gcl_enabled` | 是否启用 GCL 功能 |
| `gcl_bat_path` | GCL 的 start.bat 路径（启用 GCL 时设置） |
| `pwa_appx_family_name` | （可选）已安装 Luker PWA 的 APPX PackageFamilyName |
| `pwa_app_id` | （可选）Edge PWA 应用 ID，用于 `--app-id` 启动模式 |

启动器会自动读取 `luker_path/config.yaml` 中的顶层 `port` 配置作为访问端口
（例如 `port: 59733`），修改端口后无需改动启动器配置。

## 🌐 PWA 模式说明

开启 PWA 模式后，启动器会禁止 Luker 自动打开浏览器
（通过 `--browserLaunchEnabled false` 参数），改为由启动器以 PWA 方式打开：

1. **已安装 PWA（推荐）**：在 Edge 中打开 Luker 页面，菜单 → 应用 →
   「将 Luker 安装为应用」。安装后启动器会通过 APPX 自动发现并以
   标题栏颜色跟随主题的方式启动，无需额外配置。
2. **未安装 PWA**：回退到 Edge `--app` 应用窗口模式。
3. **无 Edge**：回退到系统默认浏览器。

自动发现失败时，可手动配置 `pwa_appx_family_name`：
PowerShell 执行 `Get-AppxPackage -Name '127.0.0.1-*'` 找到 DisplayName 为
Luker 的包，把其 `PackageFamilyName` 填入配置即可。

## 📋 依赖

- customtkinter - 现代化 UI
- Pillow - 图标处理
- psutil - 进程管理
- pywin32 - Windows API

## 📄 License

MIT
