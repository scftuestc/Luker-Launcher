<div align="center">

# 🍀 Luker Launcher

常驻系统托盘的 Luker 启动器：**一键启停**、**实时日志**、**自动打开页面**。

</div>

---

## 🍀 关于 Luker

[Luker](https://github.com/funnycups/Luker) 是基于 SillyTavern 的 LLM 前端，兼容角色卡、世界书、预设和聊天记录。本仓库只提供 Windows 托盘启动器，不包含 Luker 本体；使用前请先安装 Luker 和 Node.js。项目主页：<https://luker.cups.moe/>。

---

## 📥 下载

从 [Releases](../../releases) 下载最新的 `Luker-Launcher.exe`。

> **建议**：放到 Luker 根目录（与 `Start.bat` 同级）。首次运行会自动识别；已有有效配置时优先使用配置。

- 双击运行，无需安装；配置 `launcher_config.json` 生成在 exe 同目录（模板见 `launcher_config.example.json`）。
- 被 SmartScreen 拦截时，点“更多信息” → “仍要运行”。

**运行要求**：Windows 10 / 11，已安装 Node.js 和 [Luker](https://github.com/funnycups/Luker)。

---

## 🚀 使用

启动后会自动拉起 Luker 并缩到托盘。

| 操作 | 效果 |
| :--- | :--- |
| 单击托盘图标 | 显示 / 隐藏日志窗口 |
| 右键托盘图标 | 启动、停止、重启、打开 Luker 页面、设置、退出 |
| 最小化日志窗口（─） | 收进系统托盘，Luker 继续运行 |
| 关闭日志窗口（×） | 按“关闭窗口行为”设置：每次询问 / 隐藏到托盘 / 退出程序（默认询问） |
| 托盘菜单 / 日志窗口的 Luker logo | 服务就绪后播放呼吸效果；启动中或已停止时显示为灰色 |

托盘菜单支持 `↑` / `↓` 或 `Tab` / `Shift+Tab` 移动高亮，`Home` / `End` 跳首尾，`Enter` 执行，`Esc` 关闭并恢复原窗口焦点。`Ctrl+F` 聚焦日志搜索，`Enter` / `Shift+Enter` 或 `F3` / `Shift+F3` 切换结果；只匹配正文，实时日志到达时保留结果和视口。

托盘创建失败时，最小化按钮会被禁用；关闭窗口会按设置退出，或弹出仅含“退出程序/取消”的选择框。Luker 端口会自动读取 `config.yaml` 中的 `port`。

---

## ⚙️ 设置

右键托盘 → **设置**：

- 🎨 主题切换
- 🪟 毛玻璃效果开关（雾灰主题不提供）
- 🌐 沉浸应用模式
- 🚪 关闭日志窗口时的行为
- 📁 Luker 管理（启动路径与版本）

### Luker 版本管理

设置 → **Luker 管理** 可检查并切换版本：

- 显示当前版本、最新正式 Release 和默认分支最新提交；完整哈希写入日志窗口，检查结果在本次运行期间保留。
- 只有点击“检查更新”才会访问 GitHub 和 `git fetch`；更新要求 Git clone、Git 和 npm。
- 更新会停止 Luker、检出目标提交，按 `Start.bat` 参数安装依赖，完成后按原状态重启；有已跟踪文件的未提交修改时禁止更新。
- 未跟踪的 `data/`、`node_modules/` 不会被删除；失败会尝试回滚，回滚失败时不启动 Luker；当前版本领先最新提交时禁用更新。

### 配置文件

大部分选项可在设置窗口修改；手动调整时编辑 exe 同目录的 `launcher_config.json`，参考 [`launcher_config.example.json`](launcher_config.example.json)。

| 键 | 说明 |
| :--- | :--- |
| `luker_path` | Luker 启动根目录（含 `Start.bat` 和 `server.js`） |
| `use_pwa_mode` | 沉浸应用模式（PWA） |
| `blur_enabled` | 毛玻璃效果（雾灰主题固定关闭） |
| `close_behavior` | `ask` 询问 / `tray` 隐藏到托盘 / `exit` 退出 |
| `theme` | 主题 ID |
| `pwa_app_id` | Edge PWA App ID（可选） |
| `pwa_appx_family_name` | 已安装 PWA 的 PackageFamilyName（可选） |

---

## ❓ 常见问题

### 沉浸应用模式（PWA）是什么？

用 Edge 的 PWA 独立窗口打开 Luker，隐藏地址栏和标签页，标题栏颜色跟随主题；未安装 PWA 时回退到 Edge 应用窗口或默认浏览器。

### 托盘图标不见了？

点任务栏右下角的 `^` 展开隐藏图标。

### 启动失败或提示找不到 node？

先在 Luker 目录运行 `Start.bat` 确认 Luker 能启动，再检查 `node -v`；仍失败时查看 exe 同目录的 `launcher.log`，目录不可写时写到 `%TEMP%\launcher.log`。

---

## 🛠️ 从源码运行 / 打包

### 环境要求

- Windows 10 / 11 x64（依赖 Win32 托盘与窗口接口）
- Python 3.12
- 运行依赖：`pip install -r requirements.txt`；开发检查：`pip install -r requirements-dev.txt`；打包：`pip install pyinstaller==6.22.2`

### 运行

```bash
pip install -r requirements.txt
python main.py
```

### 代码结构

```text
main.py                 薄入口
luker_launcher/         启动入口、Coordinator、服务、进程、日志、UI 与托盘
```

入口/组装根 → Coordinator → 服务/进程/UI/托盘 → 配置/主题/基础设施；`tests/test_architecture.py` 校验依赖方向与导入环。

### 开发文档

长期开发记录、架构决策、可复用组件、开放问题与交接日志见 [`docs/`](docs/README.md)：

- 日常开发/交接：从 [`docs/development-handbook.md`](docs/development-handbook.md) 开始（唯一需要写入的文档）。
- 历史细节：按版本段查 [`docs/archive/`](docs/archive/README.md)。

### 打包

```bash
pyinstaller launcher.spec --noconfirm --distpath .
```

也可直接运行 `build.bat`，两种方式都会在项目根目录生成 exe。

### 测试与检查

```bash
check.bat
```

依次执行格式、lint、类型、测试和覆盖率门禁；也可单独运行 `python -m coverage run -m unittest discover -s tests`、`mypy .`、`ruff check .`。

---

## 📄 License

[MIT](LICENSE)
