# 可复用组件目录

> **文档类型**：架构手册（稳定知识，低频更新）
> **文档编号**：`HB-04`
> **对应旧章节**：§4（2026-11-14 拆分前）
> **内容**：已有实现、位置与复用注意事项
> **更新时机**：新增/删除/迁移组件时
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md`；高于历史归档。
> **导航**：[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)

---

<a id="sec-4"></a>
## 4. 可复用组件目录（不要重复造轮子）

> 写新代码前先在这里找；新增组件更新本表；删除组件标记“已废弃”，不要删历史。

### 4.1 应用层

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 后台一次性任务 | `TaskRunner.run()` | `application/task_runner.py` | 线程创建失败返回 `False`；worker 异常需自行捕获 |
| 跨线程投递 UI | `UiDispatcher.post()`/`post_control()` | `ui/dispatch.py` | 状态/幂等界面用 `post`；进程/浏览器/更新/退出完成用 `post_control` |
| 共享退出标志 | `LifecycleState.exiting` | `application/lifecycle_state.py` | Lifecycle 写，其他只读 |
| 进程启停/路径切换 | `ProcessCoordinator` | `application/process_coordinator.py` | 已处理 busy/退出/stop_all |
| 三态就绪 | `StatusCoordinator` + `LukerReadinessMonitor` | `application/status_coordinator.py` / `services/readiness.py` | 不要自己写 HTTP 轮询 |
| 手动/自动打开 | `BrowserCoordinator` | `application/browser_coordinator.py` | 已处理去重/等待/退出 |
| 版本检查/更新 | `UpdateCoordinator` | `application/update_coordinator.py` | 已处理缓存/序号/回滚 |
| 关闭/退出 | `LifecycleCoordinator` | `application/lifecycle_coordinator.py` | ask/tray/exit + 幂等 shutdown |
| 跨协调器协议 | `LogSink`/`UiPoster`/`SettingsView` | `application/protocols.py` | 不要传整个 Launcher |

### 4.2 配置、主题、路径

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 配置读写 | `config`/`Config` | `config.py` | 键白名单在 `_normalize` |
| 端口读取 | `config.get_server_port()` | `config.py` | 已缓存，只匹配顶层 `port:` |
| 路径校验 | `config.is_valid_luker_path()` | `config.py` | 要求两个普通文件 |
| 主题颜色 | `get_theme_colors()` | `theme.py` | 渐变只用颜色副本 |
| 颜色运算 | `shade_color()`/`mix_color()`/`is_light_color()` | `theme.py` | 不要自己写 hex 解析 |
| 主题色块 | `theme_swatch_colors()` | `theme.py` | 设置页卡片 |
| 模糊能力 | `theme_supports_blur()` | `theme.py` | 雾灰固定关闭 |
| 旧主题迁移 | `LEGACY_THEME_ALIASES` | `theme.py` | 配置读取自动迁移 |
| 程序/资源路径 | `get_app_dir()`/`resource_path()` | `paths.py` | 打包后在 `_MEIPASS` |
| 尺寸/字号 | `ui/tokens.py` | `ui/tokens.py` | 优先用令牌 |

**新增主题检查**：`PRESET_THEMES`（颜色 + name/short_name/icon）→ 需要时 `THEME_SWATCH_KEYS`、`LEGACY_THEME_ALIASES`、`BLUR_DISABLED_THEMES` → 图片资源 → `launcher.spec` datas → `tests/test_packaging.py` 期望值 → 设置页/日志窗口视觉验证。

**版本 bump 检查**：`config.APP_VERSION` 与 `version_info.txt` 必须同步；`tests/test_version.py` 校验；发布前按 [当前状态](../devlog/STATUS.md) 的发布检查。

### 4.3 日志

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 日志级别 | `get_tag_for_line()` | `log/classify.py` | 错误/警告/信息/默认 |
| 有界历史（单源） | `LogStore` | `log/store.py` | 3000 条/8 MB |
| 有界队列 | `BoundedLogQueue` | `log/pipeline.py` | 条数 + UTF-8 字节 |
| 分块重放 | `LogReplay` | `log/pipeline.py` | 200 条/批；tail |
| 日志控制器 | `LogController` | `log/pipeline.py` | 泵/重放/清空/隐藏 |
| Text 渲染 | `LogDisplay` | `ui/log_view/display.py` | 裁剪/分隔线/错误位置 |
| 搜索 | `LogSearch`/`SearchBar` | `ui/log_view/search.py` | 5000 结果/250ms |
| 颜色标签 | `configure_log_tags()` | `ui/log_view/display.py` | 主题切换重配 |

### 4.4 进程与服务

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| Luker 子进程 | `LukerProcessManager` | `process/managers.py` | 不要自己 Popen node |
| 子进程兜底 | `assign_to_job()` | `process/job.py` | `KILL_ON_JOB_CLOSE` |
| 单实例 | `single_instance.acquire/release` | `process/single_instance.py` | 创建失败放行 |
| 就绪探测 | `LukerReadinessMonitor` | `services/readiness.py` | 2 次成功才 READY |
| PWA/APPX | `open_in_browser()`/`open_as_pwa()` | `services/browser.py` | 已有校验/回退 |
| 版本读取 | `read_local_version()` | `services/version.py` | 不访问网络 |
| 版本检查 | `check_luker_versions()` | `services/version.py` | 显式调用 |
| 更新 | `apply_luker_update()` | `services/version.py` | 固定 SHA/回滚 |
| 路径比较 | `same_path()` | `services/version.py` | 大小写/分隔符归一 |

### 4.5 UI 组件

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 显示器/缩放 | `get_monitor_info()`/`sync_window_scaling()` | `ui/dpi.py` | 不要自己调 GetDpiForWindow |
| 窗口放置 | `plan_window_placement()` | `ui/dpi.py` | center/clamp/min size |
| 几何字符串 | `format_geometry()` | `ui/dpi.py` | 负坐标 `+-100` |
| 定尺/跨屏 | `WindowResizer` | `ui/resizing.py` | 日志窗口 `resizable=False` |
| 动画步进 | `StepTicker` | `ui/motion.py` | generation 取消 |
| 淡入淡出 | `WindowFade` | `ui/motion.py` | 只改 `-alpha` |
| 调色板渐变 | `fade_palette()`/`ease_in_out_cubic()` | `ui/motion.py` | 主题切换 |
| 毛玻璃/圆角 | `sync_window_blur()`/`apply_window_rounding()` | `ui/window_utils.py` | 失败只日志 |
| 无边框拖动 | `bind_window_drag()` | `ui/window_utils.py` | 子控件都要绑 |
| 字体 | `get_ui_font()` | `ui/window_utils.py` | 雅黑 UI → 雅黑 → Segoe UI |
| 按钮 | `make_button()`/`button_colors()` | `ui/buttons.py` | 8 种角色 |
| 图标 | `transport_icon()`/`menu_icon()`/`theme_icon()`/`toolbar_icon()` | `ui/icons.py` | 运行时绘制 |
| 平滑开关 | `AnimatedSwitch` | `ui/switch.py` | 复用 CTk 引擎 |
| CTk 私有接口 | `CtkSwitchAdapter` + textbox/scaling 辅助函数 | `ui/ctk_adapter.py` | switch/textbox/ScalingTracker 私有访问都集中在这里 |
| 主题图片 | `load_theme_image()`/`theme_card_image()`/`theme_log_image()` | `ui/theme_assets.py` | 缺失返回 None |
| 立绘 | `render_character()`/`left_fade_mask()` | `ui/character_art.py` | 不改源图 |
| 关闭确认 | `CloseChoiceDialog`/`show_close_choice()` | `ui/dialogs.py` | 记住选择/托盘降级 |
| 路径选择 | `select_luker_path()`/`ensure_luker_path_configured()` | `ui/dialogs.py` | 自动识别 |

### 4.6 托盘与基础设施

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 托盘图标/消息循环 | `TrayIcon.run_detached()`/`stop()` | `tray/icon.py` | 消息循环必须在托盘线程 |
| 托盘状态 | `update_status()`/`set_window_visible()` | `tray/icon.py` | `update_status` 通过消息；`set_window_visible` 直接赋值布尔 |
| 托盘菜单 | `TrayMenu` | `tray/menu.py` | 键盘/焦点/无激活 |
| Win32 声明 | `infrastructure/win32.py` | 集中声明主要 API | 局部 ctypes 仍在 `tray/icon.py`、`ui/dpi.py`、`process/job.py`、`process/single_instance.py` |
| 文件日志 | `setup_logging()`/`add_ui_log_sink()` | `infrastructure/logging_setup.py` | 不可写回退 `%TEMP%` |
| 全局异常 | `sys.excepthook`/`threading.excepthook` | `infrastructure/logging_setup.py` | 已安装，不要覆盖 |

### 4.7 测试工具

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 架构边界 | `tests/test_architecture.py` | `tests/test_architecture.py` | 新增包/导入后跑 |
| 批处理行为 | `BuildScriptBehaviorTests`/`CheckScriptBehaviorTests` | `tests/test_packaging.py` | Windows-only/临时目录 |
| 应用组合 | `tests/test_application_launcher_composition.py` | `tests/test_application_launcher_composition.py` | 构造期回调/接线 |
| UI 特征 | `tests/test_log_window_*.py`/`test_settings_window.py` | `tests/` | fake 控件 |
| 本地冒烟 | `.zcode/smoke_*.py` | `.zcode/` | 可能不存在；不要当生产代码 |
| 假 Luker | 临时目录 + `server.js`/`Start.bat`/`config.yaml` | `tests/test_process_managers.py:15-17`、`tests/test_config.py:253-255` | 不要用 `.zcode/build/dummy-luker/`（不存在） |

---

[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)
