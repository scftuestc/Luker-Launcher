# 当前架构

> **文档类型**：架构手册（稳定知识，低频更新）
> **文档编号**：`HB-02`
> **对应旧章节**：§2（2026-11-14 拆分前）
> **内容**：分层依赖、模块地图、启动顺序、运行流程、线程与状态
> **更新时机**：架构/启动/线程/流程变化时
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md`；高于历史归档。
> **导航**：[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)

---

<a id="sec-2"></a>
## 2. 当前架构

### 2.1 分层与依赖方向

```text
main.py
  └─ luker_launcher.bootstrap.entrypoint
       ├─ luker_launcher.application.launcher（组装根）
       │    ├─ BrowserCoordinator
       │    ├─ ProcessCoordinator
       │    ├─ StatusCoordinator
       │    ├─ UpdateCoordinator
       │    └─ LifecycleCoordinator
       ├─ services（browser / readiness / version）
       ├─ process（managers / job / single_instance）
       ├─ log（classify / store / pipeline）
       ├─ tray（icon / menu）
       ├─ ui（窗口、对话框、控件、DPI、日志视图）
       ├─ infrastructure（logging_setup / win32）
       ├─ config / theme / paths
       └─ ui.tokens（纯数据）
```

强制规则（`tests/test_architecture.py`）：

- `services/`、`log/`、`infrastructure/`、`process/` 不得导入 `application/`、`ui/`、`tray/` 或 Tk/CTk。
- `config` 不得导入 `application/`、`ui/`、`tray/`；可依赖标准库、`paths`、纯数据 `theme`。
- `ui/` 不得导入 `application/`。
- `theme.py`、`paths.py` 只允许标准库。
- 根 `main.py` 和 `luker_launcher.__main__` 是仅有的两个允许导入 `bootstrap` 的入口；包内其他模块不得导入。
- 根目录只能有 `main.py` 一个 Python 文件；`main.py` 只导入 `bootstrap.entrypoint`；`python -m luker_launcher` 走同一入口。
- 不允许 import cycle。

### 2.2 模块地图

> 下表包内路径省略 `luker_launcher/`；根文件写 `main.py`。

| 路径 | 职责 | 关键入口 |
|---|---|---|
| `main.py` | 根目录薄入口（`python main.py`） | `main()` |
| `luker_launcher/__main__.py` | 包入口（`python -m luker_launcher`） | `main()` |
| `bootstrap/entrypoint.py` | 日志、配置错误补报、DPI、单实例、主循环 | `main()`、`setup_dpi_awareness()` |
| `application/launcher.py` | 组装根：UI/托盘/Coordinator、首次运行、主循环 | `LukerLauncher.run()` |
| `application/task_runner.py` | 启动守护线程；线程创建失败返回 `False`；worker 异常不捕获 | `TaskRunner.run()` |
| `application/lifecycle_state.py` | 共享 `exiting` 标志 | `LifecycleState` |
| `application/protocols.py` | `LogSink`、`UiPoster`、`SettingsView` | 协议 |
| `application/process_coordinator.py` | 启停/重启/路径切换/忙碌/`stop_all()` | `ProcessCoordinator` |
| `application/status_coordinator.py` | 就绪探测、三态、2 秒轮询 | `StatusCoordinator` |
| `application/browser_coordinator.py` | 手动/自动打开、去重、等待 | `BrowserCoordinator` |
| `application/update_coordinator.py` | 检查缓存、序号、更新、进度 | `UpdateCoordinator` |
| `application/lifecycle_coordinator.py` | 关闭行为、退出、幂等 shutdown | `LifecycleCoordinator` |
| `config.py` | 配置读写/归一化/通知/端口缓存/路径校验 | `config`、`Config` |
| `theme.py` | 6 套主题元数据/颜色、旧 ID 迁移、颜色数学 | `PRESET_THEMES`、`get_theme_colors()` |
| `paths.py` | exe 目录 vs `_MEIPASS` | `get_app_dir()`、`resource_path()` |
| `infrastructure/win32.py` | 集中声明 Win32 `argtypes/restype` | `user32`、`kernel32`、`dwmapi`、`shell32` |
| `infrastructure/logging_setup.py` | 文件日志、异常钩子、UI sink | `setup_logging()`、`add_ui_log_sink()` |
| `services/readiness.py` | 进程存活 + HTTP 探测 | `LukerState`、`LukerReadinessMonitor` |
| `services/browser.py` | APPX → Edge `--app-id` → Edge `--app` → 默认浏览器 | `open_in_browser()`、`open_as_pwa()` |
| `services/version.py` | Git/GitHub/npm，不碰 Tk、不启停 Luker | `read_local_version()`、`check_luker_versions()`、`apply_luker_update()` |
| `process/managers.py` | `node server.js`、日志读取、进程树停止 | `LukerProcessManager` |
| `process/job.py` | Job Object `KILL_ON_JOB_CLOSE` | `assign_to_job()` |
| `process/single_instance.py` | 单实例互斥体 | `acquire()`、`release()` |
| `log/classify.py` | 日志级别 | `get_tag_for_line()` |
| `log/store.py` | 有界历史、最近错误 | `LogStore`、`LogEntry` |
| `log/pipeline.py` | 有界队列、分块重放、控制器 | `BoundedLogQueue`、`LogReplay`、`LogController` |
| `ui/log_window.py` | 主窗口、日志、搜索、主题、立绘、动效 | `LogWindow` |
| `ui/settings_window.py` | 主题卡片、PWA、关闭行为、版本管理 | `SettingsWindow` |
| `ui/dialogs.py` | 关闭选择、路径选择、首启引导 | `show_close_choice()`、`ensure_luker_path_configured()` |
| `ui/dpi.py` | 显示器、窗口放置、缩放 | `plan_window_placement()`、`sync_window_scaling()` |
| `ui/resizing.py` | 根窗口定尺、拖拽、跨屏 | `WindowResizer` |
| `ui/motion.py` | 缓动、`StepTicker`、`WindowFade` | `StepTicker`、`WindowFade` |
| `ui/window_utils.py` | DWM 模糊/圆角、拖动、字体 | `sync_window_blur()`、`bind_window_drag()` |
| `ui/buttons.py` | 按钮角色/配色/创建 | `make_button()`、`button_colors()` |
| `ui/icons.py` | 运行时绘制图标 | `transport_icon()`、`menu_icon()`、`toolbar_icon()` |
| `ui/switch.py` | 平滑开关 | `AnimatedSwitch` |
| `ui/ctk_adapter.py` | CTk 私有绘制接口适配 | `CtkSwitchAdapter` |
| `ui/theme_assets.py` | 主题图片加载/回退 | `load_theme_image()` |
| `ui/character_art.py` | 立绘缩放、左侧渐隐 | `render_character()` |
| `ui/tokens.py` | 尺寸/字号/圆角/动效令牌 | 纯常量 |
| `ui/log_view/display.py` | Text 渲染/裁剪/错误位置 | `LogDisplay` |
| `ui/log_view/search.py` | 搜索结果/高亮/搜索框 | `LogSearch`、`SearchBar` |
| `tray/icon.py` | 托盘图标/消息循环/Explorer 恢复 | `TrayIcon` |
| `tray/menu.py` | 无激活菜单、键盘、焦点 | `TrayMenu` |

### 2.3 启动顺序

0. `python main.py` 或 `python -m luker_launcher` → `bootstrap.entrypoint.main()`。
1. `logging_setup.setup_logging()`：写 `launcher.log`（不可写则 `%TEMP%`），安装全局异常钩子。
2. `config.report_load_error()`：配置在 import 阶段读取，日志就绪后补报。
3. `setup_dpi_awareness()`：Per-Monitor V2 → Per-Monitor → System。
4. CTk dark 主题；`single_instance.acquire()`（失败弹框退出）。
5. `LukerLauncher()` 构造 `UiDispatcher`、`LifecycleState`、`TaskRunner` 和 5 个 Coordinator。
6. `run()`：路径引导 → 日志窗口 → UI 泵 → 进程管理器 → 状态探测 → 托盘 → 首次启动 → PWA 自动打开 → `mainloop()`。
7. 主循环返回后 `LifecycleCoordinator.shutdown()` 幂等清理。

### 2.4 关键运行流程

**进程启停**

- `ProcessCoordinator.ensure_manager()` 按路径创建/复用管理器；运行中不热切换。
- `start/stop/restart` 全在后台线程；重启路径变化时先停旧、再建新、再启动。
- `LukerProcessManager` 用 `["node","server.js"]`；PWA 模式加 `--browserLaunchEnabled false`。
- 启动前查 `server.js`、端口占用；`Popen` 隐藏窗口、合并 stdout/stderr；加入 Job Object。
- 停止用 `psutil` 递归终止子进程树，超时 kill，关闭管道唤醒读线程。
- `stop_all()` 最多检查 3 个管理器实例，覆盖退出期间新接管的实例。

**三态就绪**

- `STOPPED/STARTING/READY`；连续 2 次 HTTP 成功才 READY；4xx/5xx 也算服务已监听。
- READY 后保持到进程退出，避免网络抖动导致呼吸灯闪烁。
- 就绪线程只投递 `refresh`，主线程重新计算，避免旧 STARTING 覆盖新 READY。
- `StatusCoordinator` 每 2 秒轮询；启动/重启前 `reset()`。

**浏览器/PWA**

- 自动打开仅 PWA 模式，后台最多等 30 秒，每秒探测；手动打开取消待执行自动请求。
- 顺序：配置 APPX → 自动发现 APPX → Edge `--app-id` → Edge `--app` → 默认浏览器。
- APPX 包族名先校验格式；自动发现失败 60 秒退避，成功永久缓存。

**关闭/退出**

- `close_behavior`：`ask`/`tray`/`exit`；更新中阻止；托盘不可用不能隐藏。
- `exit()`：设 `exiting`，后台 `status.stop()` → `process.stop_all()` → 经 `post_control` 投递 `finish_exit`。
- 线程创建失败：主线程同步 `stop_all()`，`finally` 退出（`707dd44`）。
- `finish_exit()` → 幂等 `shutdown()` → `window.quit()`；`shutdown()` 只停 status/UI/tray，不停 Luker；进程清理由 `exit()` 负责。

**版本检查/更新**

- 只有点击“检查更新”才访问 GitHub/`git fetch`；本地 dirty/缺 npm/路径不匹配/Git 失败都是 blocker。
- 更新目标必须是完整 40 位 SHA；`checkout --detach` 后 npm 安装；失败回滚代码并尝试恢复依赖。
- npm 参数与 `Start.bat` 一致，额外 `NODE_ENV=production`；只作用于 npm，不改 `node server.js`。
- `Start.bat` 还会在 `better_sqlite3.node` 缺失时执行 `npm run storage:install-sqlite`；启动器在 `_run_npm` 安装成功后执行同一条件步骤（`services/version.py`）。
- `UpdateCoordinator` 用 `version_check_seq` 丢弃过期结果；更新阶段走 `post_control`。

**日志管线**

- `LogStore`：单一日志源 3000 条 / 8 MB；`BoundedLogQueue`：5000 条 / 8 MB；时间戳在队列取出时生成。
- 每轮最多 10 行；可见 100ms、隐藏 500ms、积压 10ms。
- 重放 200 条/批、让出 1ms；重放期间新日志进 tail。
- 搜索最多 5000 结果，250ms 防抖；实时日志保留当前结果和视口。

**主题切换**

- `PRESET_THEMES` 存颜色 + 元数据；`get_theme_colors()` 只返回颜色键。
- 日志窗口 128ms 调色板渐变；设置窗口淡出 64ms → 重建 → 淡入 64ms；托盘菜单重建并保留选中/焦点。
- 当前 6 套：`summer`、`purple_night`、`forest_green`、`mist_gray`、`deepseek`、`crimson`。
- `mist_gray` 固定关闭毛玻璃；`deepseek` 唯一带卡片/立绘图片。
- 旧 ID 迁移：`ocean_cyan→deepseek`、`deep_blue→summer`、`rose_pink→crimson`、`cloud_gray/warm_orange/bright_white→mist_gray`。

**DPI/窗口**

- Per-Monitor V2；`winfo_*`/Win32 坐标是物理像素，CTk `geometry` 宽高/`CTkImage(size)` 是逻辑像素。
- `ui/dpi.py`：`plan_window_placement()`、`format_geometry()`（负坐标 `+-100`）、`sync_window_scaling()`。
- 日志窗口固定 960×640（按工作区适配）；设置窗口 600×720，内部滚动。
- 立绘：`winfo_*` ÷ `_get_widget_scaling()` → 逻辑尺寸；`render_character()` 按物理像素渲染；`CTkImage(size=逻辑)` 再缩放一次；CTk 私有访问清单见 ADR-13。
- 角色面板 320 逻辑像素，左侧 16% alpha 渐隐；无座右铭。

### 2.5 线程模型

| 执行体 | 谁创建 | 主要工作 | 与主线程通信 |
|---|---|---|---|
| Tk 主线程 | entrypoint/LogWindow | 控件、mainloop、所有 UI | 直接执行 |
| UI 泵 | `UiDispatcher.start()` | 执行投递回调 | queue + coalesce + control |
| Luker 日志读取 | `LukerProcessManager.start()` | 读 stdout | 放入 `BoundedLogQueue` |
| 就绪探测 | `LukerReadinessMonitor.start()` | 1 秒 HTTP | 只 `post(refresh)` |
| 托盘消息循环 | `TrayIcon.run_detached()` | Win32 消息/图标/菜单 | 回调只投递 UI；进程操作由主线程菜单触发 |
| 进程/更新/浏览器/退出 worker | `TaskRunner.run()` | 启停/Git/npm/打开/清理 | `post_ui`/`post_control` |
| 窗口动画 | Tk `after`/`StepTicker` | 淡入、渐变、呼吸灯 | 主线程 |

**调度器限额**：普通队列 256 条、每 tick 最多 32 条、空闲 50ms；合并键 `visibility`/`tray_menu`/`settings`/`luker_state`；`post_control` 是独立无界队列。

**不变量**：后台线程不直接碰 Tk；进程/浏览器/更新/退出完成回调都走 `post_control`，不会被普通队列丢弃。

### 2.6 状态归属

| 状态 | 所有者 | 主要读者 |
|---|---|---|
| `config` | `config.py` 全局单例 | UI 通过公开 setter 写入；其他层只读 |
| `LifecycleState.exiting` | `LifecycleCoordinator` | 所有 Coordinator |
| `ProcessCoordinator.manager/busy` | `ProcessCoordinator` | Status/Update/Lifecycle |
| `StatusCoordinator.last_state` | `StatusCoordinator` | LogWindow/TrayMenu |
| `UpdateCoordinator` 缓存/序号 | `UpdateCoordinator` | SettingsWindow |
| 日志 store/queue/replay | `LogController` | LogWindow |
| 窗口视觉状态 | LogWindow/SettingsWindow | 自身 |
| 托盘状态 | TrayIcon/TrayMenu | Launcher/Status |

---

[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)
