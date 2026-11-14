# 测试与验证手册

> **文档类型**：架构手册（稳定知识，低频更新）
> **文档编号**：`HB-06`
> **对应旧章节**：§8（2026-11-14 拆分前）
> **内容**：测试布局、门禁、覆盖盲区、冒烟与测试数据规则
> **更新时机**：测试命令/覆盖/门禁变化时
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md`；高于历史归档。
> **导航**：[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)

---

<a id="sec-8"></a>
## 8. 测试与验证手册

### 8.1 测试布局（重点）

| 文件 | 数量 | 覆盖 |
|---|---:|---|
| `test_core_version.py` | 60 | Git/GitHub/npm/回滚 |
| `test_settings_window.py` | 54 | 设置窗口/主题/版本/更新 |
| `test_application_update_coordinator.py` | 36 | 检查/缓存/更新/重启 |
| `test_config.py` | 35 | 归一化/BOM/路径/端口 |
| `test_browser.py` | 33 | APPX/Edge/PWA/回退 |
| `test_log_pipeline.py` | 30 | 队列/重放/控制器 |
| `test_dpi.py` | 26 | 监视器/放置/缩放 |
| `test_log_search.py` | 26 | 搜索/高亮/调整 |
| `test_log_window_theme.py` | 24 | 立绘/主题/DPI/动画 |
| `test_ui_window_utils.py` | 22 | 模糊/圆角/拖动/字体 |
| `test_application_process_coordinator.py` | 20 | 启停/路径/忙碌/线程失败 |
| `test_ui_resizing.py` | 19 | 定尺/跨屏/拖拽 |
| `test_application_lifecycle_coordinator.py` | 18 | ask/tray/exit/幂等 |
| `test_ui_dispatch.py` | 18 | 合并/上限/control |
| `test_ui_icons.py` | 18 | 图标渲染 |
| `test_tray_menu.py` | 16 | 菜单/键盘/焦点 |
| `test_application_browser_coordinator.py` | 14 | 自动/手动/去重/超时 |
| `test_application_status_coordinator.py` | 14 | 三态/轮询/过期回调 |
| `test_tray_icon.py` | 14 | 句柄/图标/消息循环 |
| `test_dialogs.py` | 14 | 关闭框/路径/定位 |
| `test_architecture.py` | 14 | 依赖方向/根目录/import cycle/CTk 私有访问 |
| `test_ctk_adapter.py` | 8 | CTk 适配层 |
| `test_docs.py` | 1 | 文档结构校验器 |
| 其余 | — | 日志存储/显示、进程、托盘键盘、主题、Win32 API |

> 总计 **772**。`test_architecture.py` 不是可选检查。

### 8.2 门禁命令

```bat
check.bat
```

五道：`ruff format --check` → `ruff check` → `mypy` → `coverage run -m unittest discover -s tests -q` → `coverage report`（门槛 65%）。每道都用 `call python ...`；失败 `goto fail`，输出 `Check failed.`，返回非零。

`build.bat`：`call pyinstaller launcher.spec --noconfirm --distpath .`；失败不清理 `build/`、不打印 `Done!`、返回非零。

> `check.bat` / `build.bat` 末尾会 `pause`；自动化调用需提供输入或直接调用底层命令。`check.bat` 会写 `.coverage`（已忽略）。
>
> 文档结构由 `tests/test_docs.py` 调用 `docs/tools/check_docs.py` 校验，已纳入 `check.bat`；也可单独运行 `python docs/tools/check_docs.py`。

### 8.3 覆盖不足/需要人工

- 真实 PyInstaller 构建后的 `_MEIPASS` 资源读取。
- 真实 125%/150%/200% Windows 设备观感。
- 真实 npm 更新（单测是 fake Popen）。
- 真实托盘菜单/Explorer 重启/多显示器热插拔。
- 真实进程强杀后的 Job Object 行为。
- 托盘线程 `PostMessage` 失败等极端退出路径。

### 8.4 手工冒烟清单

用**临时目录 + 假 Luker**，不要改用户配置：

1. `python main.py`：窗口/托盘/日志/按钮/主题/设置。
2. 假 Luker：启动/停止/重启/端口占用提示。
3. 关闭行为：ask/tray/exit；记住选择。
4. 版本检查：无网络/非 Git/dirty/缺 npm/ahead/behind/diverged。
5. 100/125/150%：日志窗口、立绘、设置、托盘菜单。
6. 双屏不同 DPI：窗口/设置/托盘菜单位置尺寸。
7. 托盘：左键切换/双击/右键键盘导航/Explorer 重启恢复。
8. 退出：正常/托盘不可用降级/更新中阻止。

### 8.5 测试数据规则

- 不修改用户的 `launcher_config.json`；用 `tempfile.TemporaryDirectory()` 或临时配置。
- 假 Luker：临时目录写空 `server.js`；需要配置时写 `Start.bat`、`server.js`、`config.yaml`（参考 `tests/test_process_managers.py:15-17`、`tests/test_config.py:253-255`）。
- UI 测试用 fake 控件，不创建真实 Tk 窗口。
- 批处理测试在临时目录放假 `python.bat`/`pyinstaller.bat`，不运行真实打包。
- 不断言易漂移的精确像素/截图；优先断言行为/尺寸关系。

---

[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)
