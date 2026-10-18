# 🍀 Luker Launcher

一个常驻 Windows 系统托盘的 Luker 启动器：一键启停、查看日志、自动打开页面。

## 📥 下载与安装

1. 打开 [Releases](../../releases) 页面。
2. 下载最新版本中的 `Luker-Launcher.exe`。
3. 双击运行，无需安装。

> 如果 Windows 提示“已保护你的电脑”，点击“更多信息” → “仍要运行”。

## 🚀 首次使用

1. 启动后会要求选择 Luker 安装目录（包含 `Start.bat` 的文件夹）。
2. 选择完成后，启动器会自动启动 Luker，并最小化到系统托盘。
3. 单击托盘图标显示/隐藏日志窗口，右键打开完整菜单。

使用前请确认：

- Windows 10 / 11
- 已安装 Node.js，命令行执行 `node -v` 能正常输出版本
- Luker 目录中包含 `Start.bat` 和 `server.js`

## 🖱️ 常用操作

| 操作 | 方法 |
| --- | --- |
| 显示 / 隐藏日志 | 单击托盘图标 |
| 启动 / 停止 / 重启 Luker | 右键托盘菜单 |
| 打开 Luker 页面 | 右键托盘 → “Luker 页面” |
| 修改主题、路径、PWA / GCL | 右键托盘 → “设置” |
| 退出启动器 | 右键托盘 → “退出” |

- 关闭日志窗口只是隐藏到托盘，程序仍在后台运行。
- Luker 端口会自动读取 `luker_path/config.yaml` 中的 `port`，无需手动填写。
- 配置保存在 exe 同目录的 `launcher_config.json`。

## ❓ 常见问题

**托盘里找不到图标？**
点击任务栏右下角的 `^`，在隐藏图标中查找。

**提示启动失败或找不到 node？**
先在 Luker 目录双击 `Start.bat`，确认 Luker 能正常启动；再检查命令行执行 `node -v` 是否正常。

**想要 PWA 应用窗口？**
在设置中开启 PWA 模式，需要安装 Microsoft Edge。未安装 Luker PWA 时会自动回退到 Edge 应用窗口或默认浏览器。

**GCL 怎么启用？**
在设置中开启 GCL 并选择 GCL 的 `start.bat`，托盘菜单会出现 GCL 的启动/停止项。

## 🛠️ 从源码运行 / 打包

```bash
pip install -r requirements.txt
python main.py
```

```bash
pip install pyinstaller
pyinstaller launcher.spec
```

## 📄 License

MIT
