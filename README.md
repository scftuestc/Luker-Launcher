# 🍀 Luker Launcher

常驻系统托盘的 Luker 启动器：一键启停、实时日志、自动打开页面。

## 下载

从 [Releases](../../releases) 下载最新的 `Luker-Launcher.exe`。

**建议把 exe 放到 Luker 根目录（与 `Start.bat` 同级）。** 启动器会优先自动识别该目录；如果首次运行仍提示选择路径，选中这个目录即可。配置文件 `launcher_config.json` 会生成在 exe 同目录。

双击运行，无需安装。若被 SmartScreen 拦截，点“更多信息” → “仍要运行”。

要求：Windows 10 / 11，已安装 Node.js 和 Luker。

## 使用

启动后会自动拉起 Luker 并缩到托盘。

- 单击托盘图标：显示 / 隐藏日志窗口
- 右键托盘图标：启动、停止、重启、打开 Luker 页面、设置、退出
- 关闭日志窗口只是隐藏到托盘；退出请用托盘菜单

Luker 端口会自动读取 `config.yaml` 中的 `port`，不需要手动配置。

## 设置

右键托盘 → 设置：

- 主题切换
- PWA 模式
- GCL 联动
- Luker 安装路径

## 常见问题

**PWA 模式是什么？**
用 Edge 的独立应用窗口打开 Luker，更像桌面客户端，标题栏颜色跟随主题。需要 Edge；如果 Luker 没有安装为 PWA，会回退到 Edge 应用窗口或默认浏览器。

**GCL 是什么？**
可选的配套服务，通过它自己的 `start.bat` 启动。开启并选中该 bat 后，托盘菜单可以联动启停 GCL，日志窗口也能切换到 GCL 日志。不使用 GCL 就保持关闭。

**托盘图标不见了？**
点任务栏右下角的 `^` 展开隐藏图标。

**启动失败或提示找不到 node？**
先在 Luker 目录运行 `Start.bat`，确认 Luker 本身能启动；再检查 `node -v` 是否正常。如果仍然失败，查看 exe 同目录的 `launcher.log`，里面有详细错误信息。

## 从源码运行 / 打包

```bash
pip install -r requirements.txt
python main.py
```

```bash
pip install pyinstaller
pyinstaller launcher.spec
```

运行测试：

```bash
python -m unittest discover -s tests
```

## License

MIT
