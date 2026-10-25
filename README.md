<div align="center">

# 🍀 Luker Launcher

常驻系统托盘的 Luker 启动器：**一键启停**、**实时日志**、**自动打开页面**。

</div>

---

## 🍀 关于 Luker

[Luker](https://github.com/funnycups/Luker) 是一个面向进阶用户的 LLM 前端，基于 SillyTavern 并保持数据兼容，角色卡、世界书、预设和聊天记录可以直接沿用。项目主页：<https://luker.cups.moe/>。

本仓库只提供 Windows 托盘启动器，不包含 Luker 本体。使用前请先安装 [Luker](https://github.com/funnycups/Luker) 和 Node.js。

---

## 📥 下载

从 [Releases](../../releases) 下载最新的 `Luker-Launcher.exe`。

> **建议**：把 exe 放到 Luker 根目录（与 `Start.bat` 同级）。首次运行会自动识别该目录；已有有效配置时优先使用配置。如果仍提示选择路径，选中这个目录即可。

- 双击运行，无需安装
- 配置文件 `launcher_config.json` 会生成在 exe 同目录（模板见 `launcher_config.example.json`）
- 若被 SmartScreen 拦截，点“更多信息” → “仍要运行”

**运行要求**：Windows 10 / 11，已安装 Node.js 和 [Luker](https://github.com/funnycups/Luker)。

---

## 🚀 使用

启动后会自动拉起 Luker 并缩到托盘。

| 操作 | 效果 |
| :--- | :--- |
| 单击托盘图标 | 显示 / 隐藏日志窗口 |
| 右键托盘图标 | 启动、停止、重启、打开 Luker 页面、设置、退出 |
| 最小化日志窗口（─） | 收进系统托盘，Luker 继续运行 |
| 关闭日志窗口（×） | 弹窗确认后停止 Luker 并退出启动器 |
| 托盘菜单 / 日志窗口的 Luker logo | Luker 服务就绪后播放呼吸效果；启动中或已停止时显示为灰色 |

如果托盘创建失败，最小化按钮会被禁用，关闭日志窗口仍会弹窗确认后退出。

Luker 端口会自动读取 `config.yaml` 中的 `port`，不需要手动配置。

---

## ⚙️ 设置

右键托盘 → **设置**：

- 🎨 主题切换
- 🪟 毛玻璃效果开关
- 🌐 PWA 模式
- 🚀 GCL 联动
- 📁 Luker 安装路径

### 配置文件

大部分选项可以在设置窗口修改；需要手动调整时，编辑 exe 同目录的 `launcher_config.json`。可参考仓库中的 [`launcher_config.example.json`](launcher_config.example.json)；空字符串表示未设置，首次运行会提示选择 Luker 目录。

| 键 | 说明 |
| :--- | :--- |
| `luker_path` | Luker 安装目录 |
| `use_pwa_mode` | 是否使用 PWA 模式 |
| `blur_enabled` | 是否启用毛玻璃效果 |
| `theme` | 主题 ID |
| `gcl_enabled` | 是否启用 GCL |
| `gcl_bat_path` | GCL 的 `start.bat` 路径 |
| `gcl_url` | GCL 访问地址 |
| `pwa_app_id` | Edge PWA App ID（可选） |
| `pwa_appx_family_name` | 已安装 PWA 的 APPX PackageFamilyName（可选） |

---

## ❓ 常见问题

### PWA 模式是什么？

用 Edge 的独立应用窗口打开 Luker，更像桌面客户端，标题栏颜色跟随主题。需要 Edge；如果 Luker 没有安装为 PWA，会回退到 Edge 应用窗口或默认浏览器。

### GCL 是什么？

可选的配套服务，通过它自己的 `start.bat` 启动。开启并选中该 bat 后，托盘菜单可以联动启停 GCL，日志窗口也能切换到 GCL 日志。不使用 GCL 就保持关闭。

### 托盘图标不见了？

点任务栏右下角的 `^` 展开隐藏图标。

### 启动失败或提示找不到 node？

先在 Luker 目录运行 `Start.bat`，确认 Luker 本身能启动；再检查 `node -v` 是否正常。如果仍然失败，查看 exe 同目录的 `launcher.log`，里面有详细错误信息；如果该目录不可写，日志会写到 `%TEMP%\launcher.log`。

---

## 🛠️ 从源码运行 / 打包

### 环境要求

- Windows 10 / 11 x64（依赖 Win32 托盘与窗口接口，不支持其他平台）
- Python 3.12（本项目以此版本开发和验证）
- 运行依赖：`pip install -r requirements.txt`
- 开发与检查：`pip install -r requirements-dev.txt`
- 打包：`pip install pyinstaller==6.22.2`（与本地发布构建一致）

### 运行

```bash
pip install -r requirements.txt
python main.py
```

### 代码结构

```text
main.py / launcher_app.py           入口与应用协调
config.py / logging_setup.py        配置读写与文件日志
log_window.py / settings_window.py  主窗口与设置窗口
dialogs.py                          退出确认与路径选择

log/                                日志存储、管线、渲染与搜索
tray/                               托盘图标与右键菜单
ui/                                 主题、按钮、图标、窗口效果、DPI 与 UI 调度
process/                            子进程管理、Job Object 与单实例保护
core/                               Luker 就绪探测与浏览器启动
tests/                              单元测试
```

依赖方向是“根窗口/协调器 → 功能包 → `ui`/`config`”。`ui.theme` 只包含主题数据与颜色数学，不反向依赖 `config`、窗口或协调器；各包的 `__init__.py` 不做 re-export，避免导入副作用和循环依赖。

### 打包

```bash
pip install pyinstaller==6.22.2
pyinstaller launcher.spec --noconfirm --distpath .
```

也可以直接运行 `打包.bat`，两种方式生成的 exe 都会放在项目根目录。

### 测试与检查

```bash
python -m coverage run -m unittest discover -s tests
python -m coverage report
mypy .
ruff check .
ruff format --check .
```

---

## 📄 License

[MIT](LICENSE)
