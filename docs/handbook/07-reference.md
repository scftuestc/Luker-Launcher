# 术语与附录

> **文档类型**：架构手册（稳定知识，低频更新）
> **文档编号**：`HB-07`
> **对应旧章节**：§9（2026-11-14 拆分前）
> **内容**：术语、配置 schema、关键提交、事实来源
> **更新时机**：术语/配置/事实来源变化时
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md`；高于历史归档。
> **导航**：[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)

---

<a id="sec-9"></a>
## 9. 术语与附录

### 9.1 术语

- **Coordinator**：只负责一类业务流程、通过构造函数注入依赖的对象。
- **组装根**：只创建对象、接线、启动主循环，不写业务细节。
- **UiDispatcher**：后台线程 → Tk 主线程的安全队列；完成回调走 control 队列。
- **READY**：进程存活且 HTTP 连续成功，不是“进程一启动就算”。
- **Job Object**：Windows 内核对象；`KILL_ON_JOB_CLOSE` 随句柄关闭终止子进程。
- **GPG `G`**：`git log --format='%G?'` 输出 `G` 表示签名有效。
- **onefile/`_MEIPASS`**：PyInstaller 单文件运行时资源解压目录。
- **物理/逻辑像素**：150% 下 1 逻辑 = 1.5 物理；Tk `winfo_*` 物理，CTk `geometry`/`CTkImage(size)` 逻辑。
- **P2/P3**：P2 发布前应修；P3 维护性/可延后。
- **DEV/ADR/LSN/OPEN/TODO**：文档 ID 前缀；分配规则见 [`devlog/README.md`](../devlog/README.md) 的 ID registry。
- **GCL**：v3.4 前的旧 `.bat` 启动方式，无端口探测/健康检查/多实例；`b840bf1` 移除。`tests/test_config.py` 仍验证 `gcl_*` 键被忽略，不是重新引入。
- **方案 A**：`DEV-20261110-01` 的立绘布局（固定 960×640、320 面板、左 16% 渐隐、无座右铭、滚动条最右）。

### 9.2 配置 schema

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `luker_path` | string | `""` | Luker 根目录，需含 `Start.bat` + `server.js` |
| `sillytavern_path` | string | 无 | 旧版兼容，写入新键后清理 |
| `use_pwa_mode` | bool | `false` | 沉浸应用模式 |
| `blur_enabled` | bool | `true` | 毛玻璃；雾灰固定关闭 |
| `close_behavior` | string | `"ask"` | `ask`/`tray`/`exit` |
| `theme` | string | `"summer"` | 主题 ID；旧 ID 自动迁移 |
| `pwa_app_id` | string | `""` | Edge PWA App ID（可选） |
| `pwa_appx_family_name` | string | `""` | APPX PackageFamilyName（可选） |

未知键/错误类型丢弃；`luker_path` 等 `_STRING_KEYS` 去空白；`theme`/`close_behavior` 走白名单，带空白会回退默认值。

### 9.3 关键提交速查

| 提交 | 主题 |
|---|---|
| `cb75d8b` | 初始导入（v1.0） |
| `4c91e77` | 日志时间戳/清除/GCL 饥饿 |
| `6d2e987` | 进程启停后台化 |
| `4c32010` | 合并 Luker/GCL 进程管理器 |
| `0755a14` | 拆分日志/主题/配置 |
| `c7ff0b6` | UI 队列 + 托盘生命周期 |
| `6f2258d` | 单实例/Job Object/外部 Luker |
| `34f95d2` | 高 DPI 适配 |
| `555f658` | APPX 包族名校验（命令注入） |
| `a8f9b5e` | 日志队列/搜索上限 |
| `f93b14f` | 日志分块重放 |
| `6f1f6ec` | 主题切换构建时绑定 |
| `42b1e13` | 应用主体移入独立模块 |
| `2f96c3e` | Luker 版本检查/更新 |
| `3260c48` | 托盘句柄/消息循环加固 |
| `69dc96f` | 配置读取/路径边界 |
| `cc6f815` | 构建失败返回非零 |
| `79e2a78` | npm `NODE_ENV=production` |
| `b840bf1` | **移除 GCL** |
| `ce3bc04` | 托盘键盘导航 |
| `5a41744` | CTk 私有开关适配层 |
| `547160a` | Coordinator 基础 |
| `a66f873` | v4.0 |
| `64f1a06` | DeepSeek 主题 |
| `00dec31` | 固定日志窗口/立绘 |
| `707dd44` | 退出失败同步停止 |
| `16dbd3f` | 高 DPI 立绘修复 |
| `3966429` | 打包/门禁测试补强 |
| `e9bc44f` | 回滚主题卡片悬停放大 |
| `a7a1c68` | 最终立绘布局 |
| `8f3f84b` | 搜索实时日志保留结果/视口 |
| `994ce62` | 设置窗口滚动绑定清理 |
| `b6ce9f5` | 主题卡片悬停回滚（配合 `e9bc44f`） |
| `3ad154f` | 组合根构造期回调保护 |
| `a512226` | 方案 A 立绘布局（dev） |
| `157f22a` | 合并方案 A |

### 9.4 事实来源

- `README.md`、`pyproject.toml`、`check.bat`、`build.bat`、`launcher.spec`、`version_info.txt`。
- `docs/handbook/`：本目录，稳定架构知识与决策。
- `docs/devlog/`：当前状态、风险/TODO、当前日志与历史归档；`INDEX.md` 为条目/提交/决策索引。
- 本地工作记录（`.zcode/reports/`，不随仓库分发，可能不存在）：`review-2026-11-09.md`、`review-fixes-2026-11-09.md`、`implementation-2026-11-05.md`、`launcher-refactor-and-package-plan-2026-11-05.md`、`ai-gijika-deepseek-2026-11-08.md`、`ai-gijika-polish-2026-11-09.md` 等；其结论已并入本手册/归档。
- Git：193 个产品提交 + 文档维护提交、17 标签、`git log --stat`、`git diff`、`git show`。

---

[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)
