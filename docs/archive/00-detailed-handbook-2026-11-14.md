# Luker Launcher 详细开发手册（2026-11-14 快照）

> **文档类型**：历史归档 · 详细手册快照（只读）
> **文档编号**：`LH-LUKER-ARCH-00`
> **结构版本**：`2.0`（2026-11-14 快照；当前主手册为 `4.0`）
> **来源**：原 `development-history-full-2026-11-14.md` §0–§9
> **事实截止**：2026-11-14
> **权威性**：低于 [`../development-handbook.md`](../development-handbook.md)；冲突时以主手册、代码、测试为准。
>
> **快照说明**：本文件保留 2026-11-14 当时的详细正文，包括当时“本文件在 `.zcode/` 下、不进入版本库”等规则。那些规则已被主手册 §0 取代；本文件只读，不再更新。

---

## 交接摘要（每次交接更新）

- **当前状态**：`ai-gijika` / `a7a1c68`；工作区 clean；758 tests / 74% / `check.bat` pass。
- **最近完成**：DeepSeek 主题、角色立绘、固定日志窗口、两个 P2 修复、审查整改、最终移除座右铭并把滚动条移到最右。
- **当前阻塞**：`APP_VERSION` 仍为 4.0；HEAD 未 bump、未构建 exe、未在真实 125%/150% 设备验收；是否发布需用户确认。
- **建议下一步**：先确认是否发布；若发布，按 `TODO-01` 做版本 bump + 构建 + 100%/125%/150% 验收。不要先做大重构。
- **不要重复**：不要重新引入 GCL；不要恢复主题卡片悬停放大；不要加回座右铭；不要恢复日志窗口拖拽缩放；不要改 npm 参数。
- **文档使用**：任务完成后在 §10 末尾追加 `DEV-YYYYMMDD-NN`，并更新 §0.2、§6、§7。

**常见问题速查**：

| 你可能问 | 看这里 |
|---|---|
| 某个能力是不是已经实现过？ | §4 可复用组件目录 |
| 为什么代码要这样设计？ | §3 ADR |
| 这个坑以前踩过吗？ | §5 历史经验库（LSN） |
| 现在还有什么没做？ | §6 开放问题 + §7 待办 |
| 最近一次改了什么？ | §10 末尾的 `DEV` 条目 |
| 发布前要做什么？ | §7 `TODO-01` + §8.4 手工冒烟 |
| 怎么追加记录？ | §0.5 流程 + §0.6 模板 |

---

## 0. 文档使用规范（先读）

### 0.1 文档目的

这个文件解决三个问题：

1. **项目记忆**：193 个提交、17 个标签之后，新 Agent 不需要从零猜“为什么代码长这样”。
2. **避免重复造轮子**：已有组件、工具、设计决策集中登记；写新代码前先查 §4。
3. **可持续交接**：每个任务结束后按统一格式追加日志；下一个 Agent 可以接着写，而不是重写整份文档。

**边界**：本文件记录“事实、决策、验证、遗留”，不替代 README、代码注释和测试。产品行为以 README + 代码 + 测试为准；本文件用于解释原因和历史。

**最小必读（约 20 分钟）**：§0（规范）、§1（基线）、§2（架构）、§3（ADR）、§4（可复用组件）、§6（开放问题）、§7（待办）。§5/§10 是历史细节，按需查阅；不要一开始从头读到尾。

### 0.2 文档控制表

| 字段 | 当前值 | 更新时机 |
|---|---|---|
| 文档编号 | `LH-LUKER-001` | 结构变更时 |
| 结构版本 | `2.0` | 结构调整时 |
| 最后更新 | `2026-11-14` | 每次追加日志 |
| 最新日志条目 | `DEV-20261114-01` | 每次追加日志 |
| 下一条日志 ID | `DEV-20261114-02` | 每次追加日志 |
| 当前分支 / HEAD | `ai-gijika` / `a7a1c68` | 每次任务开始/结束 |
| 当前版本 | `APP_VERSION = 4.0` | 版本 bump 时 |
| 工作区状态 | clean（本文件在 `.zcode/` 下，被忽略） | 每次任务结束 |
| 质量基线 | 758 tests / 74% / check.bat pass | 每次任务结束 |
| 事实截止 | `2026-11-14` | 每次追加日志 |

### 0.3 事实等级与写作规则

每条记录尽量使用以下标签，避免把猜测写成事实：

| 标签 | 含义 | 例子 |
|---|---|---|
| `[已验证]` | 代码、测试、命令或 Git 历史可直接证明 | `git rev-list --count v1.0..v1.1` = 10 |
| `[推断]` | 根据提交信息/代码结构推断，未单独实验 | “可能是为了避免重复开浏览器” |
| `[待确认]` | 需要用户/产品/实机确认 | “真实 150% 设备观感” |

写作规则：

- 日期统一 `YYYY-MM-DD`；提交用 7 位短哈希；文件引用用 `path:line`。
- 不粘贴大段命令输出；只写“命令 + 关键结果”。
- 不写“优化了代码”“修复了问题”这种空话；必须写**改了什么行为、哪个文件、哪个测试**。
- 未验证的内容必须标 `[待验证]` 或 `[待确认]`，不要写成已完成。
- 旧日志不修改；如果 later 发现错误，在 §0.9 修订记录里加“勘误”，并引用旧条目。
- 决策被推翻时，不删除旧 ADR；新增 ADR 并标注“取代 ADR-xx”。

### 0.4 状态、类型、优先级词表

**状态**：

| 状态 | 含义 |
|---|---|
| `待开始` | 已登记，未动工 |
| `进行中` | 正在做，可能有未提交改动 |
| `待验证` | 代码/测试完成，等待实机或用户验收 |
| `已完成` | 代码、测试、必要验证完成；未发布 |
| `已发布` | 已进入 tag/release |
| `已回滚` | 做过但被撤回；保留原因 |
| `已废弃` | 不再维护；保留历史 |
| `阻塞` | 等用户/外部条件 |

**类型**：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`perf`、`release`、`revert`。

**优先级**：`P0`（立即）、`P1`（发布前必须）、`P2`（发布前应修）、`P3`（维护性/可延后）。

### 0.5 每次任务后的追加流程（必须执行）

1. **确定 ID**：`DEV-YYYYMMDD-NN`。当天下第一条为 `01`；下一条见 §0.2 控制表。跨天重新从 `01` 开始。
2. **在 §10 末尾追加**：复制 §0.6 模板；不要插入旧条目中间，不要重排历史。
3. **填完整**：目标、改动、验证、决策/风险、遗留/下一步。验证必须写命令和结果。
4. **更新 §0.2**：最后更新、最新条目、下一条 ID、HEAD、质量基线。
5. **更新 §6/§7**：关闭/新增开放问题；更新 TODO 状态（`待开始`/`进行中`/`已完成`）。
6. **如果改变架构/决策/组件**：更新 §2/§3/§4，并在 §0.9 加一行文档修订记录。
7. **不要 `git add` 本文件**：`.zcode/` 已被 `.gitignore` 第 15 行忽略；本文件不进入版本库。
8. **更新交接摘要**：如果状态/阻塞/下一步变了，同步更新顶部“交接摘要”。
9. **交接时**：填写 §0.8 交接检查表；在 §10 最后一条写“交接点”。

### 0.6 开发日志条目模板（可直接复制）

```markdown
### DEV-YYYYMMDD-NN | 一句话标题

| 字段 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| 分支 | ai-gijika |
| 提交 | abc1234（未提交则写“未提交”） |
| 类型 | feat / fix / refactor / test / docs / chore / release |
| 状态 | 已完成 / 待验证 / 已发布 / 已回滚 / 进行中 |
| 关联 | ADR-xx / OPEN-xx / TODO-xx |
| 证据等级 | [已验证] / [推断] / [待确认] |

**目标/背景**

- 为什么做；对应哪个用户问题或审查项。

**改动**

- `path:line`：改了什么行为。
- 新增/删除的组件、配置、测试。

**验证**

- 命令：`...`
- 结果：`... tests passed` / `coverage ...` / 手动验证了什么。
- 未验证：明确写“未验证”。

**决策/风险**

- 做了什么取舍；有什么已知风险。

**遗留/下一步**

- 未完成事项；下一个 Agent 应该接着做什么。
```

> 小改动可以压缩为 6~10 行，但“日期 / 提交 / 类型 / 状态 / 改动 / 验证 / 遗留”不能缺。

### 0.7 文档地图

| 章节 | 内容 | 更新频率 |
|---|---|---|
| §0 | 使用规范、控制表、模板 | 结构变更时 |
| §1 | 项目基线、分支/版本、质量基线 | 每次发布/交接 |
| §2 | 当前架构、启动顺序、运行流程 | 架构变更时 |
| §3 | 关键设计决策（ADR） | 决策变更时 |
| §4 | 可复用组件目录（不要重复造轮子） | 新增/删除组件时 |
| §5 | 历史经验库（踩坑/回归） | 新增教训时 |
| §6 | 开放问题与技术债 | 状态变化时 |
| §7 | 待办与下一步（可领取） | 领取/完成时 |
| §8 | 测试与验证手册 | 命令/覆盖变化时 |
| §9 | 术语、配置 schema、关键提交、来源 | 按需 |
| §10 | **开发日志（只追加）** | 每个任务结束 |

### 0.8 交接检查表

接手时：

- [ ] 已读 §1、§2、§3、§4。
- [ ] `git status` 干净；当前分支/HEAD 已写入 §0.2。
- [ ] 已跑 `check.bat`；测试数/覆盖率已记录。
- [ ] 已看 §6 开放问题、§7 待办。
- [ ] 已确认硬约束：不推送、不改用户配置、GPG 签名、作者只有 Yaoyao、无 AI 署名。
- [ ] 已确认本文件在 `.zcode/` 下，不会被提交。

交班时：

- [ ] 最后一条 §10 日志写清“已完成/未完成/下一步”。
- [ ] §0.2 的 HEAD/质量基线是最新的。
- [ ] §6/§7 状态已更新。
- [ ] 未验证项已明确标 `[待验证]`。
- [ ] 工作区没有未说明的改动。

### 0.9 文档修订记录

| 日期 | 版本 | 修改人 | 说明 |
|---|---|---|---|
| 2026-11-14 | 1.0 | 上一轮审查 | 初版开发历史文档（994 行，叙述式） |
| 2026-11-14 | 2.0 | ZCode | 重构为“稳定知识 + 只追加日志”结构；修正 v1.2/v2.0 提交区间；增加模板、ID、待办、交接检查表 |

> 勘误也记录在这里：`日期 | 影响条目 | 原内容 | 更正`。

---

## 1. 项目基线

### 1.1 产品是什么

Luker Launcher 是 Windows 10/11 x64 上的**常驻托盘启动器**，不包含 Luker 本体。它负责：

- 一键启动、停止、重启 Luker（`node server.js`）；
- 实时读取并显示 Luker 输出日志；
- 服务就绪后自动打开 PWA/浏览器；
- 托盘图标、托盘右键菜单、关闭窗口行为；
- 主题、毛玻璃、窗口圆角、动效；
- Luker 版本检查与 Git 更新；
- 单实例、子进程兜底清理、文件日志。

Luker 是基于 SillyTavern 的 LLM 前端；启动器只要求其目录包含 `Start.bat`、`server.js`，并从 `config.yaml` 读取端口。

### 1.2 运行环境与依赖

| 项目 | 当前值 |
|---|---|
| 操作系统 | Windows 10/11 x64；依赖 Win32 托盘、Job Object、DWM |
| Python | 3.12 |
| GUI | Tkinter + CustomTkinter `>=5.2,<6.1`（6.0 已实测，暂不放开 6.1） |
| 图像 | Pillow `>=10` |
| 进程 | psutil `>=5.9` |
| 打包 | PyInstaller `6.22.2`（onefile，`console=False`） |
| 质量工具 | ruff `0.16.10`、mypy `2.4.0`、coverage `7.16.2` |
| 许可证 | MIT，Copyright (c) 2026 Yaoyao |

### 1.3 硬约束（来自用户，不是建议）

- **不要推送到远程**；不要打标签、不要发布 Release，除非用户明确确认。
- **作者/提交者只能是** `Yaoyao <jiayinyao24@outlook.com>`；不要添加 `Co-authored-by`、`Signed-off-by` 或任何 AI/GPT/生成器署名。
- **提交必须 GPG 签名**；提交后用 `git log --format='%G?'` 确认是 `G`。
- **不要修改用户的 `launcher_config.json`**；所有测试/冒烟使用临时目录或临时配置。
- **不要改变 UI 行为、npm 参数、配置格式、窗口尺寸策略**，除非当前任务明确要求。
- **不要把架构抽取和包文件搬家混在一个大提交里**；历史已证明分阶段更安全。
- 远程仓库：`https://github.com/scftuestc/Luker-Launcher.git`。

### 1.4 分支与发布

| 分支/标签 | 指向 | 说明 |
|---|---|---|
| `main` | `fc06d38` | 已发布主线；`v4.0` 之后只有 README 精简 |
| `dev` | `a512226` | 主题分支的中间点（含座右铭浮层版本） |
| `ai-gijika` | `a7a1c68` | 当前工作分支；比 `main` 多 19 个提交，比 `dev` 多 3 个 |
| `origin/ai-gijika` | `a7a1c68` | 远程已有同名分支，本地与之同步；**不要据此推送** |
| `v4.0` | `a66f873` | 最新正式标签；GitHub 已发布 `Luker-Launcher.exe` |
| `v3.5` / `v3.5.0` | `ec0b561` | 两个标签指向同一提交，历史遗留，不必处理 |

> `ai-gijika` 的 19 个提交**没有** bump 版本，也**没有**重新发布。根目录现有 exe 是 4.0 时期构建，不代表 HEAD。`main`/`dev` 不包含这 19 个提交；不要自行 merge/rebase/推送，先问用户。

### 1.5 版本坐标（提交范围含端点）

| 版本 | 日期 | 提交范围 | 提交数 | 一句话 |
|---|---|---|---:|---|
| `v1.0` | 2026-10-02 | `cb75d8b` | 1 | 导入现有启动器原型（14 文件 / 3,733 行） |
| `v1.1` | 2026-10-18 | `206c1d1..38be292` | 10 | 日志/GCL/进程/PWA/托盘第一轮修复 + 注释/README |
| `v1.2` | 2026-10-18 | `6343f3e..5cfb3b3` | 6 | 日志与界面资源占用优化、自动识别路径、清空队列 |
| `v2.0` | 2026-10-19 | `4c32010..4e98b09` | 10 | 合并进程管理器、拆日志/主题/配置、UI 队列、单实例/Job Object、文件日志、首批测试 |
| `v2.1` | 2026-10-19 | `71a73e3..c224c69` | 7 | ruff/CI/LICENSE、托盘菜单/设置窗口拆分、类型注解 |
| `v2.2` | 2026-10-19 | `34f95d2..34d01e3` | 6 | 高 DPI 跨屏、托盘/进程生命周期、发布元数据 |
| `v2.3` | 2026-10-20~21 | `b5993f0..aad0cad` | 10 | GCL/PWA 竞态、APPX 校验、日志窗口最小尺寸、队列/重放上限 |
| `v2.4` | 2026-10-21 | `b69d47d..3729554` | 17 | 日志队列/搜索/显示/重放拆分、窗口缩放、UI 调度器、覆盖率门禁 |
| `v3.0` | 2026-10-22~23 | `24f9db0..b480684` | 20 | 主题/毛玻璃/圆角/按钮/呼吸 logo/关闭确认/托盘菜单图标 |
| `v3.1` | 2026-10-24~25 | `fe149c4..c778e3b` | 20 | 应用主体拆分、日志窗口/搜索栏拆分、目录分包、生命周期完成回调 |
| `v3.2` | 2026-10-25~27 | `43476f0..523764c` | 14 | 关闭行为记忆、版本检查/更新、设置页接入、更新加固、本地门禁 |
| `v3.3` | 2026-10-30 | `3260c48..5f9e402` | 9 | 托盘句柄、配置边界、构建失败、npm 生产环境、窗口几何抽取、测试补齐 |
| `v3.4` | 2026-11-02 | `2b9ebdb..16e97be` | 8 | 设计令牌、窗口淡入、日志空/加载/错误态、托盘键盘、**移除 GCL** |
| `v3.4.1` | 2026-11-03 | `ca08bb9` | 1 | 版本号补丁 |
| `v3.5` | 2026-11-03~04 | `5f95490..ec0b561` | 16 | 雾灰关闭毛玻璃、图标/字体统一、配置 BOM、Win32 声明、CTk 适配层、边界加固 |
| `v4.0` | 2026-11-05 | `547160a..a66f873` | 18 | **Coordinator 架构 + 单一 `luker_launcher/` 包 + 架构测试** |
| `v4.0+` | 2026-11-05~10 | `fc06d38` + `64f1a06..a7a1c68` | 20 | DeepSeek 主题、立绘、DPI/退出修复、审查整改、布局迭代 |

> `v3.5.0` 与 `v3.5` 是同一提交的重复标签，统计只算一次。总计：1+10+6+10+7+6+10+17+20+20+14+9+8+1+16+18+20 = **193**。

### 1.6 质量基线（2026-11-14 实测）

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests -q` | **758 项通过**，约 2 秒 |
| 覆盖率 | **74%**（门槛 65%） |
| `ruff format --check .` | 106 个文件已格式化 |
| `ruff check .` | 通过 |
| `mypy .` | 55 个源文件无问题 |
| 工作区 | 干净；只有被忽略的 `.coverage`、`.zcode/`、根目录 exe/log 等 |
| 提交签名 | 193 个提交中 187 个 `G`；6 个 v1.1 时期提交为 `N`（历史事实，当前不要效仿） |
| 作者/提交者 | 全部为 `Yaoyao <jiayinyao24@outlook.com>`；无 AI 署名 |

> 6 个未签名提交：`38be292`、`6343f3e`、`9ab1fa9`、`fab4cb8`、`60b7690`、`224c7ba`，集中在 v1.1/v1.2 前后。之后的提交全部 GPG 签名。

### 1.7 审查结论

- 本轮审查与上一轮全仓库审查均未发现 P0/P1。
- 上一轮已确认并修复 2 个 P2：
  - 退出线程创建失败时可能残留 Luker/Node 进程（`707dd44`）；
  - 高 DPI 下立绘物理/逻辑尺寸混用导致放大两次、裁切（`16dbd3f`）。
- 仍有若干 P3 维护性问题，见 §6。它们不影响当前基本功能，但下一个 Agent 应知道边界。

---

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
       ├─ luker_launcher.services（browser / readiness / version）
       ├─ luker_launcher.process（managers / job / single_instance）
       ├─ luker_launcher.log（classify / store / pipeline）
       ├─ luker_launcher.tray（icon / menu）
       ├─ luker_launcher.ui（窗口、对话框、控件、DPI、日志视图）
       ├─ luker_launcher.infrastructure（logging_setup / win32）
       ├─ luker_launcher.config / theme / paths
       └─ luker_launcher.ui.tokens（纯数据）
```

强制规则（`tests/test_architecture.py`）：

- `services/`、`log/`、`infrastructure/`、`process/` **不得**导入 `application/`、`ui/`、`tray/` 或 Tk/CTk。
- `config` **不得**导入 `application/`、`ui/`、`tray/`；当前实现只依赖标准库与纯数据 `theme`。
- `ui/` **不得**导入 `application/`。
- `theme.py`、`paths.py` 只允许标准库。
- 只有 `luker_launcher.__main__` 可以导入 `bootstrap`。
- 根目录只能有 `main.py` 一个 Python 文件；`main.py` 只导入 `luker_launcher.bootstrap.entrypoint`。
- 不允许 import cycle。

### 2.2 模块地图

| 路径 | 职责 | 关键入口 |
|---|---|---|
| `main.py` | 薄入口 | `main()` |
| `luker_launcher/bootstrap/entrypoint.py` | 日志初始化、配置错误补报、DPI 感知、单实例、Tk 主循环 | `main()`、`setup_dpi_awareness()` |
| `luker_launcher/application/launcher.py` | 组装根：创建 UI/托盘/Coordinator，首次运行，主循环 | `LukerLauncher.run()` |
| `application/task_runner.py` | 后台守护线程创建，失败返回 `False` | `TaskRunner.run()` |
| `application/lifecycle_state.py` | 共享 `exiting` 标志 | `LifecycleState` |
| `application/protocols.py` | `LogSink`、`UiPoster`、`SettingsView` | 协议 |
| `application/process_coordinator.py` | 启停/重启/路径切换/忙碌标志/`stop_all()` | `ProcessCoordinator` |
| `application/status_coordinator.py` | 就绪探测、三态、2 秒轮询 | `StatusCoordinator` |
| `application/browser_coordinator.py` | 手动/自动打开、去重、等待就绪 | `BrowserCoordinator` |
| `application/update_coordinator.py` | 版本检查缓存、请求序号、更新流程、进度 | `UpdateCoordinator` |
| `application/lifecycle_coordinator.py` | 关闭行为、退出对话框、幂等 shutdown | `LifecycleCoordinator` |
| `config.py` | 配置读写、归一化、主题/毛玻璃/关闭行为通知、端口缓存、路径校验 | 全局 `config`、`Config` |
| `theme.py` | 6 套主题元数据/颜色、旧 ID 迁移、颜色数学 | `PRESET_THEMES`、`get_theme_colors()` |
| `paths.py` | exe 目录 vs `_MEIPASS` 资源目录 | `get_app_dir()`、`resource_path()` |
| `infrastructure/win32.py` | 集中声明 Win32 `argtypes/restype` | `user32`、`kernel32`、`dwmapi`、`shell32` |
| `infrastructure/logging_setup.py` | 文件日志、全局异常钩子、UI 日志 sink | `setup_logging()`、`add_ui_log_sink()` |
| `services/readiness.py` | 进程存活 + 本地 HTTP 探测，三态 | `LukerState`、`LukerReadinessMonitor` |
| `services/browser.py` | APPX → Edge `--app-id` → Edge `--app` → 默认浏览器 | `open_in_browser()`、`open_as_pwa()` |
| `services/version.py` | Git/GitHub/npm，不碰 Tk、不启停 Luker | `read_local_version()`、`check_luker_versions()`、`apply_luker_update()` |
| `process/managers.py` | `node server.js` 子进程、日志读取、进程树停止 | `LukerProcessManager` |
| `process/job.py` | Job Object `KILL_ON_JOB_CLOSE` | `assign_to_job()` |
| `process/single_instance.py` | 本地会话互斥体 | `acquire()`、`release()` |
| `log/classify.py` | 日志级别分类 | `get_tag_for_line()` |
| `log/store.py` | 有上限的历史日志、最近错误 | `LogStore`、`LogEntry` |
| `log/pipeline.py` | 有界队列、分块重放、日志控制器 | `BoundedLogQueue`、`LogReplay`、`LogController` |
| `ui/log_window.py` | 主窗口、日志显示、搜索、主题、立绘、动效 | `LogWindow` |
| `ui/settings_window.py` | 设置窗口、主题卡片、PWA、关闭行为、Luker 版本管理 | `SettingsWindow` |
| `ui/dialogs.py` | 关闭选择框、路径选择、首次路径引导 | `show_close_choice()`、`ensure_luker_path_configured()` |
| `ui/dpi.py` | 显示器信息、窗口放置、缩放同步 | `plan_window_placement()`、`sync_window_scaling()` |
| `ui/resizing.py` | 根窗口初始尺寸、边缘拖拽、跨屏适配 | `WindowResizer` |
| `ui/motion.py` | 缓动、`StepTicker`、`WindowFade`、调色板渐变 | `StepTicker`、`WindowFade` |
| `ui/window_utils.py` | DWM 模糊/圆角、窗口拖动、字体探测 | `sync_window_blur()`、`bind_window_drag()` |
| `ui/buttons.py` | 按钮角色、配色、统一创建 | `make_button()`、`button_colors()` |
| `ui/icons.py` | 运行时绘制图标（不依赖字体） | `transport_icon()`、`menu_icon()`、`toolbar_icon()` |
| `ui/switch.py` | 平滑开关 | `AnimatedSwitch` |
| `ui/ctk_adapter.py` | CTk 私有绘制接口的唯一适配层 | `CtkSwitchAdapter` |
| `ui/theme_assets.py` | 主题图片加载与回退 | `load_theme_image()` |
| `ui/character_art.py` | 立绘缩放、左侧 alpha 渐隐 | `render_character()` |
| `ui/tokens.py` | 尺寸/字号/圆角/动效令牌 | 纯常量 |
| `ui/log_view/display.py` | Text 渲染、行数/字节裁剪、错误位置 | `LogDisplay` |
| `ui/log_view/search.py` | 搜索结果、高亮、搜索框、防抖 | `LogSearch`、`SearchBar` |
| `tray/icon.py` | Shell_NotifyIcon 托盘图标、消息循环、Explorer 恢复 | `TrayIcon` |
| `tray/menu.py` | 无激活右键菜单、键盘导航、焦点恢复 | `TrayMenu` |

### 2.3 启动顺序

`bootstrap.entrypoint.main()`：

1. `logging_setup.setup_logging()`：写 `launcher.log`（不可写则 `%TEMP%`），安装 `sys.excepthook` / `threading.excepthook`。
2. `config.report_load_error()`：配置在 import 阶段读取，错误等日志系统就绪后补报。
3. `setup_dpi_awareness()`：优先 Per-Monitor V2，其次 Per-Monitor，最后 System。
4. `ctk.set_appearance_mode("dark")`、`set_default_color_theme("dark-blue")`。
5. `single_instance.acquire()`：失败弹 MessageBox 并退出。
6. `LukerLauncher()` 构造：创建 `UiDispatcher`、`LifecycleState`、`TaskRunner` 和 5 个 Coordinator。
7. `LukerLauncher.run()`：
   - 首次路径引导；
   - 创建 `LogWindow`，启动 UI 队列泵；
   - `process.ensure_manager()`、`status.start()`；
   - 创建托盘菜单/图标，`tray_icon.run_detached()`；
   - 首次启动 Luker（有托盘则隐藏窗口，无托盘保持窗口）；
   - PWA 模式安排自动打开；
   - 进入 Tk `mainloop()`；
   - 返回后 `LifecycleCoordinator.shutdown()` 幂等清理。

<a id="a00-flows"></a>
### 2.4 关键运行流程

#### 进程启动/停止/重启

- `ProcessCoordinator.ensure_manager()`：按 `config.luker_path` 创建/复用 `LukerProcessManager`；运行中不热切换路径。
- `start()`：先 `on_status_reset()`，再后台 `manager.start()`。
- `stop()`：后台 `manager.stop()`。
- `restart()`：同路径直接 `manager.restart()`；路径变化则先停旧管理器，再创建新管理器并 `adopt_manager()`，最后启动。
- `LukerProcessManager`：
  - 启动命令 `["node", "server.js"]`；PWA 模式下追加 `--browserLaunchEnabled false`，避免 Luker 自己再开浏览器。
  - 启动前检查 `server.js` 是否存在、端口是否被占用。
  - `Popen` 使用 `CREATE_NO_WINDOW`、隐藏窗口、stdout/stderr 合并、stdin 管道、UTF-8 `errors='replace'`。
  - 子进程加入 Job Object；失败只警告，不阻止启动。
  - 日志读取线程逐行读 stdout，回调给日志窗口。
  - 停止时用 `psutil` 递归终止子进程树，再终止父进程；超时 kill；关闭管道唤醒读线程。
  - `RLock` 串行化 start/stop/restart。
- `ProcessCoordinator.stop_all()`：最多检查 3 个管理器实例，覆盖退出期间新接管的实例。

#### 三态就绪

- `LukerState`：`STOPPED`、`STARTING`、`READY`。
- `LukerReadinessMonitor`：1 秒间隔、1 秒超时、连续 2 次 HTTP 成功才 READY；4xx/5xx 也算“服务已在监听”；READY 后保持到进程退出，避免网络抖动导致呼吸灯闪烁。
- `StatusCoordinator`：
  - 无管理器/进程未运行 → STOPPED；
  - 进程存活但 readiness 不是 READY → STARTING；
  - readiness READY → READY。
  - 每 2 秒在 Tk 主线程轮询；`reset()` 用于启动/重启前清空旧 READY。
  - 就绪线程回调只投递 `refresh`，不直接应用过期状态。

#### 浏览器/PWA

- `BrowserCoordinator.open()`：
  - 自动打开只执行一次；手动打开取消待执行的自动请求；
  - `busy` 防止并发；退出中拒绝；
  - 后台线程执行 `open_in_browser(url, prefer_pwa=config.use_pwa_mode)`。
- `BrowserCoordinator.schedule_auto_open_if_needed()`：仅 PWA 模式，后台最多等 30 秒，每秒探测；超时写日志提示手动打开。
- `services.browser.open_as_pwa()` 顺序：
  1. 配置的 `pwa_appx_family_name`（先校验格式，再 PowerShell 查安装）；
  2. 自动发现 `127.0.0.1-*` APPX 包，读 `AppxManifest.xml` 找 DisplayName=Luker；
  3. Edge `--app-id`（配置了且已安装 PWA）；
  4. Edge `--app=<url>`；
  5. 默认浏览器。
- 自动发现失败有 60 秒退避；成功永久缓存。

#### 关闭/退出

- `LifecycleCoordinator.request_exit()`：
  - 更新中阻止退出并提示；
  - `close_behavior`：`ask` / `tray` / `exit`；
  - 托盘不可用时不允许隐藏，只能退出或取消；
  - 关闭对话框异常时回退到系统 `messagebox`。
- `exit()`：
  - 设置 `exiting=True`、`set_running(False)`；
  - 后台 worker：`status.stop()` → `process.stop_all()` → 投递 `finish_exit`；
  - 线程创建失败：主线程同步 `process.stop_all()`，`finally` 中 `finish_exit()`（`707dd44`）。
- `finish_exit()` → `shutdown()`（幂等：停状态、停 UI 队列、停托盘）→ `window.quit()`。
- `mainloop` 返回后再次 `shutdown()` 兜底。

#### 版本检查/更新

- 只有用户点击“检查更新”才访问 GitHub / `git fetch`，没有后台轮询。
- `check_luker_versions()`：
  - `read_local_version()`：读 HEAD、短哈希、分支、日期、subject、tag、dirty、path 是否匹配；
  - `git fetch --tags --prune origin`（网络失败仍继续查 GitHub API）；
  - GitHub API 读默认分支、最新 release、release 指向的 commit、默认分支最新 commit；
  - 计算 `up_to_date / ahead / behind / diverged / unknown`；
  - 本地 dirty、缺 npm、路径不匹配、Git 失败都会成为 blocker。
- 更新目标固定到完整 40 位 SHA；`apply_luker_update()`：
  - 校验 SHA；
  - 检查 Git 仓库、Git/npm、dirty；
  - `git fetch`、`cat-file` 确认目标存在；
  - `git checkout --detach <sha>`；
  - npm 安装（参数与 `Start.bat` 一致，额外 `NODE_ENV=production`）；
  - 失败时 `checkout`/`reset --hard` 回滚代码，并尝试重装依赖；
  - 回滚失败不自动启动 Luker。
- `UpdateCoordinator` 用 `version_check_seq` 丢弃过期结果；检查缓存按路径失效；更新阶段通过 `post_control` 投递，避免普通队列的合并/丢弃覆盖最终状态。

#### 日志管线

- `LogStore`：每个源最多 3000 条、8 MB；超出丢最旧；记录最近一条 error。
- `BoundedLogQueue`：最多 5000 条、8 MB（UTF-8 字节），按条数和字节双重限制。
- `LogController`：
  - 每轮最多取 10 行；
  - 可见时 100ms 轮询，隐藏时 500ms，有积压时 10ms；
  - 重放每批 200 条、让出 1ms；
  - 重放期间新日志进入 tail，快照结束后再插入；
  - 隐藏时只存不渲染，显示时整段重建；
  - 实时日志触发搜索刷新合并为 250ms。
- `LogDisplay`：Text 控件中按行数/字节裁剪；每 60 秒插入分隔线；时间戳和正文共用悬挂缩进；记录 `last_error_index` 供“定位”。
- `LogSearch`：最多 5000 个结果；跳过时间戳和分隔线；实时日志刷新时保留当前结果和视口。
- `SearchBar`：250ms 防抖、`Ctrl+F`、`Enter/Shift+Enter`、`F3/Shift+F3`、`Esc`。

#### 主题切换

- `PRESET_THEMES` 同时存颜色和元数据（name/short_name/icon/card_image/log_image）；`get_theme_colors()` 只返回 `THEME_COLOR_KEYS` 的颜色，避免把元数据当颜色。
- 主题切换由 `config.theme_name` setter 触发：
  - 日志窗口：`StepTicker` 做 128ms 调色板渐变；期间只改颜色，不触发 DWM/图标重建；完成后 `_apply_theme()` 做完整刷新。
  - 设置窗口：淡出（64ms）→ 销毁全部子控件 → 按新主题重建 → 淡入（64ms）。
  - 托盘菜单：销毁子控件并重建，保留选中项/焦点/动画状态。
- 当前 6 套主题：`summer`、`purple_night`、`forest_green`、`mist_gray`、`deepseek`、`crimson`。
- `mist_gray` 是唯一浅色主题，**固定关闭毛玻璃**；`deepseek` 是唯一带 `card_image`/`log_image` 的主题。
- 旧 ID 通过 `LEGACY_THEME_ALIASES` 迁移：`ocean_cyan→deepseek`、`deep_blue→summer`、`rose_pink→crimson`、`cloud_gray→mist_gray`、`warm_orange→mist_gray`、`bright_white→mist_gray`。
- 设置页当前主题只用 accent 边框表示，**没有**“✓ 当前主题”文字；这是有意的产品取舍。

#### DPI 与窗口

- 进程 Per-Monitor V2；Win32 坐标、Tk `geometry` 位置、`winfo_width/height` 都是**物理像素**；CTk 的 `geometry` 宽/高和 `CTkImage(size=...)` 是**逻辑像素**。
- `ui/dpi.py` 提供：
  - `MonitorInfo`、`get_monitor_info()`（窗口/屏幕点）；
  - `fit_logical_window_size()`、`fit_window_with_minimum()`；
  - `centered_position()`、`clamp_popup_position()`、`clamp_window_position()`；
  - `format_geometry()`（负坐标写成 `+-100`，不能写 `-100`）；
  - `plan_window_placement()`（`center`/`clamp`）；
  - `sync_window_scaling()`（立即应用缩放，不等 CTk 100ms 轮询）；
  - `discard_window_scaling()`（销毁 Toplevel 时清缓存）。
- `WindowResizer`：初始尺寸/最小尺寸/跨屏重排/边缘拖拽。生产路径只有日志窗口 `resizable=False`；设置窗口用自己的 `_fit_to_current_monitor()`。
- 立绘：`winfo_*` 先除以 `_get_widget_scaling()` 得到逻辑尺寸；`render_character()` 按逻辑尺寸 × scale 生成物理像素图；`CTkImage(size=逻辑尺寸)` 再缩放一次，最终物理像素吻合。

### 2.5 线程模型

| 执行体 | 谁创建 | 主要工作 | 与主线程通信 |
|---|---|---|---|
| Tk 主线程 | `bootstrap.entrypoint` / `LogWindow` | 创建控件、`mainloop`、所有 UI 操作 | 直接执行 |
| UI 泵 | `UiDispatcher.start()`（Tk `after`） | 执行投递的回调 | `queue` + coalesce + control 队列 |
| Luker 日志读取线程 | `LukerProcessManager.start()` | 逐行读 stdout | 回调把行放入 `BoundedLogQueue`（线程安全） |
| 就绪探测线程 | `LukerReadinessMonitor.start()` | 1 秒 HTTP 探测 | 状态回调只 `post(refresh)` |
| 托盘消息循环 | `TrayIcon.run_detached()` | Win32 消息、图标、右键菜单 | 回调只投递 UI；进程操作由主线程菜单触发 |
| 进程/更新/浏览器/退出 worker | `TaskRunner.run()` | 启停、Git/npm、打开浏览器、退出清理 | `post_ui` / `post_control` |
| 设置窗口/日志窗口动画 | Tk `after` / `StepTicker` | 淡入、主题渐变、呼吸灯 | 主线程 |

**关键不变量**：后台线程不直接调用 Tk 控件；生命周期完成回调走 `post_control`，不会被普通 UI 队列的容量限制丢弃。

### 2.6 状态归属

| 状态 | 所有者 | 主要读者 |
|---|---|---|
| `config` | `config.py` 全局单例 | 所有层（只读属性） |
| `LifecycleState.exiting` | `LifecycleCoordinator` 写 | 所有 Coordinator 只读 |
| `ProcessCoordinator.manager/busy` | `ProcessCoordinator` | Status/Update/Lifecycle |
| `StatusCoordinator.last_state` | `StatusCoordinator` | LogWindow/TrayMenu |
| `UpdateCoordinator.version_check_cache/seq` | `UpdateCoordinator` | SettingsWindow |
| `LogStore`/`BoundedLogQueue`/`LogReplay` | `LogController` | LogWindow |
| 日志窗口视觉状态 | `LogWindow` | 自身 |
| 设置窗口视觉状态 | `SettingsWindow` | 自身 |
| 托盘图标/菜单状态 | `TrayIcon`/`TrayMenu` | Launcher/Status |

---

## 3. 关键设计决策（ADR）

> 这些决定不是“随便选的”。下一个 Agent 若想推翻，先读原因，并征得用户同意。新决策追加 ADR；旧 ADR 不删除，标注“被 ADR-xx 取代”。

### ADR 索引

| ADR | 决策 | 状态 | 证据 |
|---|---|---|---|
| ADR-01 | 用 `node server.js`，不通过 `Start.bat` | 有效 | `process/managers.py:339-345` |
| ADR-02 | Job Object + 单实例 | 有效 | `process/job.py`、`process/single_instance.py` |
| ADR-03 | 后台线程统一经 `UiDispatcher` 回主线程 | 有效 | `ui/dispatch.py` |
| ADR-04 | 就绪 = 连续成功 + READY 粘滞 | 有效 | `services/readiness.py` |
| ADR-05 | 配置归一化/原子写入/BOM/端口缓存 | 有效 | `config.py` |
| ADR-06 | 路径切换只在停止时进行 | 有效 | `application/process_coordinator.py:56-75` |
| ADR-07 | 更新固定完整 SHA、dirty 检查、可回滚 | 有效 | `services/version.py:734-808` |
| ADR-08 | 移除 GCL 联动 | 有效 | `b840bf1` |
| ADR-09 | 日志窗口固定尺寸 | 有效 | `ui/log_window.py:242` |
| ADR-10 | 主题卡片悬停放大已回滚 | 有效 | `e9bc44f` |
| ADR-11 | 座右铭已移除 | 有效 | `a7a1c68` |
| ADR-12 | 门禁只在本地，不恢复远程 CI | 有效 | `43476f0` |
| ADR-13 | CTk 私有接口隔离 + 版本锁 | 有效 | `ui/ctk_adapter.py`、`requirements.txt` |
| ADR-14 | 主题颜色与元数据分离 | 有效 | `theme.py:256-262` |
| ADR-15 | 版本/打包一起验证，发布需确认 | 有效 | `config.py:25`、`launcher.spec` |

<a id="adr-01"></a>
### ADR-01 用 `node server.js`，不通过 `Start.bat`

- **决策**：启动器直接 `node server.js`；PWA 模式追加 `--browserLaunchEnabled false`。
- **背景**：需要控制 Luker 是否自己打开浏览器，避免 PWA 模式弹两个窗口。
- **后果**：启动器依赖 `node` 在 PATH；`Start.bat` 里的其他环境准备不会自动执行。
- **不要**：为了“更贴近 Start.bat”改成 `Start.bat`；会失去参数控制，历史 GCL 也因此出过重复启动问题。

<a id="adr-02"></a>
### ADR-02 Job Object + 单实例

- **决策**：子进程加入 `KILL_ON_JOB_CLOSE` 的 Job Object；同一 Windows 会话只允许一个启动器。
- **背景**：启动器被任务管理器结束/异常退出时，node 可能继续占端口；两个启动器会抢端口。
- **后果**：Job 句柄随启动器进程关闭；单实例互斥体创建失败时放行，不能阻止用户使用。
- **不要**：移除 Job Object 或只 `terminate()` 父进程；node 子进程树会残留。

<a id="adr-03"></a>
### ADR-03 后台线程统一经 `UiDispatcher` 回主线程

- **决策**：托盘/进程/就绪/版本线程都不直接碰 Tk；普通 UI 请求可合并/丢弃，生命周期完成走 `post_control`。
- **背景**：Tk 非线程安全，跨线程操作会随机崩溃。
- **后果**：`post()` 返回 `False` 表示 UI 泵已停止，调用方必须复位 busy。
- **不要**：从后台线程直接 `root.after()`；不要用普通队列投递“必须执行”的完成回调。

<a id="adr-04"></a>
### ADR-04 就绪 = 连续成功 + READY 粘滞

- **决策**：进程存活 + 连续 2 次 HTTP 成功才 READY；READY 后保持到进程退出。
- **背景**：进程刚启动不代表服务可用；网络抖动会让呼吸灯闪烁。
- **后果**：就绪回调只投递 `refresh`，由主线程重新计算；避免旧 STARTING 覆盖新 READY。
- **不要**：每次探测都直接 apply 状态；会状态回退。

<a id="adr-05"></a>
### ADR-05 配置归一化/原子写入/BOM/端口缓存

- **决策**：只保留已知键；字符串去空白；bool 只接受真 bool；theme/close_behavior 白名单；`utf-8-sig`；临时文件 + `fsync` + `os.replace`；端口按 stat 缓存。
- **背景**：手改配置、BOM、半截写入、每秒读盘都会造成启动失败或卡顿。
- **后果**：未知键/错误类型被丢弃；端口读取失败回退 8000。
- **不要**：用 `yaml` 整体解析 `config.yaml`（只需顶层 `port:`）；不要把嵌套 `browserLaunch.port` 当端口。

<a id="adr-06"></a>
### ADR-06 路径切换只在停止时进行

- **决策**：`ensure_manager()` 发现路径变化且旧管理器仍在运行 → 保留旧管理器；`restart()` 才停旧换新；退出中拒绝接管。
- **背景**：运行中热切换会中断正在工作的 Luker，且容易端口冲突。
- **后果**：用户改路径后需要重启（或 restart）才生效。
- **不要**：运行中直接替换 manager。

<a id="adr-07"></a>
### ADR-07 更新固定完整 SHA、dirty 检查、可回滚

- **决策**：目标必须是完整 40 位 SHA；有已跟踪修改（dirty）禁止更新；失败回滚代码并尝试恢复依赖；回滚失败不自动启动。
- **背景**：防止 git 参数注入、更新到意外提交、半更新状态。
- **后果**：更新流程较慢但可恢复；未跟踪的 `data/`、`node_modules/` 不动。
- **不要**：改 npm 参数；不要用短 SHA/分支名 checkout；不要给 `node server.js` 加 `NODE_ENV`。

<a id="adr-08"></a>
### ADR-08 移除 GCL 联动

- **决策**：v3.4 删除 GCL 的设置页、托盘菜单、日志源、配置项和实现。
- **背景**（`b840bf1`）：GCL 仅按 `.bat` 启动外部进程，没有端口探测、健康检查、多实例支持；而且会接受 Luker 自己的 `Start.bat`，导致重复启动和端口占用。
- **后果**：配置里的 `gcl_*` 键会被归一化丢弃；README 不再提 GCL。
- **不要**：重新引入 GCL 联动；如果未来要做，先设计独立健康检查/端口/实例模型。

<a id="adr-09"></a>
### ADR-09 日志窗口固定尺寸

- **决策**：`WindowResizer(resizable=False)`；名义 960×640 逻辑像素，按工作区适配；跨屏重新锁定。
- **背景**：主题/立绘布局对尺寸敏感；固定尺寸保证视觉稳定。
- **后果**：不能拖拽缩放；`resizing.py` 仍保留 `resizable=True` 分支（P3 死代码）。
- **不要**：未经产品确认恢复拖拽缩放。

<a id="adr-10"></a>
### ADR-10 主题卡片悬停放大已回滚

- **决策**：当前只做 6 帧/18ms 的颜色过渡，不改几何/图片。
- **背景**：曾实现 0.94→1.0 放大和图片 100→106；快速进出、滚轮、窗口 Leave 容易留下残影，最终整体回滚（`b6ce9f5` → `e9bc44f`）。“修复成本高于收益”是根据回滚结果推断 `[推断]`。
- **后果**：卡片视觉更稳定；`_ThemeCardHighlight` 仍自建动画状态机（P3）。
- **不要**：重新加回 `relwidth`/图片放大；如果要做，先解决指针校准和残影测试。

<a id="adr-11"></a>
### ADR-11 座右铭已移除

- **决策**：当前无座右铭；`theme.py` 的 DeepSeek 元数据没有 `motto`；`character_art.py` 只做缩放和左侧渐隐。
- **背景**：座右铭经历加入 → 浮层 → 一行 → 移除（`00dec31` → `a512226` → `7af004a` → `a7a1c68`）。
- **后果**：日志窗口高度全部给文本/立绘；字体探测 helper 已删除。
- **不要**：重新加回座右铭，除非用户明确要求。

<a id="adr-12"></a>
### ADR-12 门禁只在本地，不恢复远程 CI

- **决策**：`check.bat` 五道门禁；删除 `.github/workflows/ci.yml`。
- **背景**：`43476f0` 的提交信息只记录“门禁改为只在本地执行”，未展开原因；从项目是 Windows 桌面应用、托盘/Win32 测试需要 Windows 环境推断，本地门禁更实际 `[推断]`。
- **后果**：没有远程绿灯；合并前必须本地跑 `check.bat`。
- **不要**：重新加 GitHub Actions 并声称覆盖托盘；除非配置 Windows runner。

<a id="adr-13"></a>
### ADR-13 CTk 私有接口隔离 + 版本锁

- **决策**：`customtkinter>=5.2,<6.1`；`_textbox`/`_get_widget_scaling`/`_canvas`/`_draw_engine` 访问集中/隔离。
- **背景**：6.0 已实测；6.1 的 Text 控件内部接口可能变化。
- **后果**：升级 CTk 需要回归日志窗口、DPI、开关动画、主题渐变。
- **不要**：在业务代码里到处新增直接私有属性访问。

<a id="adr-14"></a>
### ADR-14 主题颜色与元数据分离

- **决策**：`PRESET_THEMES` 存颜色 + 元数据；`get_theme_colors()` 只返回 `THEME_COLOR_KEYS`。
- **背景**：主题渐变/动画只能处理颜色，不能把 `name`/`icon` 当颜色传给 Tk。
- **后果**：新增主题必须同时更新 `THEME_SWATCH_KEYS` 和 `LEGACY_THEME_ALIASES`（如适用）。
- **不要**：把整个 `PRESET_THEMES[theme]` 直接传给渐变/控件。

<a id="adr-15"></a>
### ADR-15 版本/打包一起验证，发布需确认

- **决策**：`APP_VERSION` 与 `version_info.txt` 同步；发布前构建 exe、验证资源与 DPI；发布动作必须用户确认。
- **背景**：v4.0 后 19 个提交未 bump；直接发布会让 exe 版本与上一版相同，且新资源未验证。
- **后果**：当前 `APP_VERSION=4.0`，HEAD 未构建；发布任务列入 §7。
- **不要**：未经确认 bump/构建/打标签/上传。

---

## 4. 可复用组件目录（不要重复造轮子）

> 写新代码前先在这里找；找不到再考虑新增。新增组件时更新本表；删除组件时标记“已废弃”，不要直接删历史。

### 4.1 应用层

| 需要什么 | 现成实现 | 位置 | 用法/注意 |
|---|---|---|---|
| 后台跑一次性任务 | `TaskRunner.run(func, name=None) -> bool` | `application/task_runner.py` | 守护线程；创建失败返回 `False`，调用方负责复位状态 |
| 跨线程投递 UI | `UiDispatcher.post()` / `post_control()` | `ui/dispatch.py` | 普通请求可合并；生命周期完成必须用 `post_control` |
| 共享退出标志 | `LifecycleState.exiting` | `application/lifecycle_state.py` | Lifecycle 写，其他 Coordinator 只读 |
| 进程启停/路径切换 | `ProcessCoordinator` | `application/process_coordinator.py` | 已处理 busy、退出、路径切换、`stop_all()` |
| 三态就绪 | `StatusCoordinator` + `LukerReadinessMonitor` | `application/status_coordinator.py` / `services/readiness.py` | 不要自己写 HTTP 轮询 |
| 手动/自动打开浏览器 | `BrowserCoordinator` | `application/browser_coordinator.py` | 已处理去重、等待、退出 |
| 版本检查/更新 | `UpdateCoordinator` | `application/update_coordinator.py` | 已处理缓存、序号、进度、回滚 |
| 关闭/退出 | `LifecycleCoordinator` | `application/lifecycle_coordinator.py` | 已处理 ask/tray/exit、幂等 shutdown |
| 跨协调器协议 | `LogSink`、`UiPoster`、`SettingsView` | `application/protocols.py` | 不要传整个 Launcher 给 Coordinator |

### 4.2 配置、主题、路径

| 需要什么 | 现成实现 | 位置 | 用法/注意 |
|---|---|---|---|
| 配置读写 | 全局 `config` / `Config` | `config.py` | 不要另建配置单例；键白名单在 `_normalize` |
| 端口读取 | `config.get_server_port()` | `config.py` | 已缓存 + 只匹配顶层 `port:` |
| 路径校验 | `config.is_valid_luker_path()` | `config.py` | 要求 `Start.bat` + `server.js` 都是普通文件 |
| 主题颜色 | `get_theme_colors()`、`PRESET_THEMES` | `theme.py` | 渐变/控件只用颜色副本 |
| 颜色运算 | `shade_color()`、`mix_color()`、`is_light_color()` | `theme.py` | 不要自己写 hex 解析 |
| 主题色块 | `theme_swatch_colors()` | `theme.py` | 设置页卡片色块 |
| 主题模糊能力 | `theme_supports_blur()` | `theme.py` | 雾灰固定关闭 |
| 旧主题迁移 | `LEGACY_THEME_ALIASES` | `theme.py` | 配置读取时自动迁移 |
| 程序目录/资源 | `get_app_dir()`、`get_bundle_dir()`、`resource_path()` | `paths.py` | 打包后资源在 `_MEIPASS` |
| 界面尺寸/字号 | `ui/tokens.py` | `ui/tokens.py` | 新增控件优先用令牌，不要散落魔法数字 |

### 4.3 日志

| 需要什么 | 现成实现 | 位置 | 用法/注意 |
|---|---|---|---|
| 日志级别 | `get_tag_for_line()` | `log/classify.py` | 错误/警告/信息/默认 |
| 有界历史 | `LogStore` | `log/store.py` | 3000 条 / 8 MB；最近 error |
| 有界队列 | `BoundedLogQueue` | `log/pipeline.py` | 同时限制条数和 UTF-8 字节 |
| 分块重放 | `LogReplay` | `log/pipeline.py` | 200 条/批；新日志进 tail |
| 日志控制器 | `LogController` | `log/pipeline.py` | 泵、重放、清空、隐藏/显示 |
| Text 渲染/裁剪 | `LogDisplay` | `ui/log_view/display.py` | 行数/字节裁剪、分隔线、错误位置 |
| 搜索 | `LogSearch` / `SearchBar` | `ui/log_view/search.py` | 最多 5000 结果；防抖；保留视口 |
| 日志颜色标签 | `configure_log_tags()` | `ui/log_view/display.py` | 主题切换时重配 |

### 4.4 进程与服务

| 需要什么 | 现成实现 | 位置 | 用法/注意 |
|---|---|---|---|
| Luker 子进程 | `LukerProcessManager` | `process/managers.py` | 不要自己 `Popen` node |
| 子进程兜底 | `assign_to_job()` | `process/job.py` | `KILL_ON_JOB_CLOSE` |
| 单实例 | `single_instance.acquire/release` | `process/single_instance.py` | 创建失败放行 |
| 就绪探测 | `LukerReadinessMonitor` | `services/readiness.py` | 2 次成功才 READY |
| PWA/APPX | `open_in_browser()`、`open_as_pwa()` | `services/browser.py` | 已有 APPX 校验/回退 |
| 版本读取 | `read_local_version()` | `services/version.py` | 不访问网络 |
| 版本检查 | `check_luker_versions()` | `services/version.py` | 显式调用；做 git fetch + GitHub API |
| 更新 | `apply_luker_update()` | `services/version.py` | 固定 SHA、dirty 检查、回滚 |
| 路径比较 | `same_path()` | `services/version.py` | 大小写/分隔符归一 |

### 4.5 UI 组件

| 需要什么 | 现成实现 | 位置 | 用法/注意 |
|---|---|---|---|
| 显示器/缩放 | `get_monitor_info()`、`sync_window_scaling()` | `ui/dpi.py` | 不要自己调 `GetDpiForWindow` |
| 窗口放置 | `plan_window_placement()` | `ui/dpi.py` | 支持 center/clamp、min size、物理坐标 |
| 几何字符串 | `format_geometry()` | `ui/dpi.py` | 负坐标必须 `+-100` |
| 根窗口定尺/跨屏 | `WindowResizer` | `ui/resizing.py` | 日志窗口 `resizable=False` |
| 动画步进 | `StepTicker` | `ui/motion.py` | 固定帧数 + generation 取消 |
| 窗口淡入淡出 | `WindowFade` | `ui/motion.py` | 只改 `-alpha`，不碰 DWM |
| 调色板渐变 | `fade_palette()`、`ease_in_out_cubic()` | `ui/motion.py` | 主题切换 |
| 毛玻璃/圆角 | `sync_window_blur()`、`apply_window_rounding()` | `ui/window_utils.py` | 失败只日志，不影响显示 |
| 无边框拖动 | `bind_window_drag()` | `ui/window_utils.py` | Tk 事件不冒泡，标题栏子控件都要绑 |
| 字体 | `get_ui_font()` | `ui/window_utils.py` | 微软雅黑 UI → 雅黑 → Segoe UI |
| 按钮 | `make_button()` / `button_colors()` | `ui/buttons.py` | 8 种角色，统一配色/尺寸 |
| 图标 | `transport_icon()` / `menu_icon()` / `theme_icon()` / `toolbar_icon()` | `ui/icons.py` | 运行时绘制，不依赖字体/emoji |
| 平滑开关 | `AnimatedSwitch` | `ui/switch.py` | 复用 CTk 绘制引擎 |
| CTk 私有接口 | `CtkSwitchAdapter` | `ui/ctk_adapter.py` | 升级 CTk 只回归这里 |
| 主题图片 | `load_theme_image()`、`theme_card_image()`、`theme_log_image()` | `ui/theme_assets.py` | 缺失/损坏返回 None，调用方回退 |
| 立绘合成 | `render_character()`、`left_fade_mask()` | `ui/character_art.py` | 按物理像素生成，不修改源图 |
| 关闭确认框 | `CloseChoiceDialog` / `show_close_choice()` | `ui/dialogs.py` | 支持记住选择、托盘不可用降级 |
| 路径选择/首启 | `select_luker_path()`、`ensure_luker_path_configured()` | `ui/dialogs.py` | 自动识别启动器所在目录 |

### 4.6 托盘与基础设施

| 需要什么 | 现成实现 | 位置 | 用法/注意 |
|---|---|---|---|
| 托盘图标/消息循环 | `TrayIcon.run_detached()` / `stop()` | `tray/icon.py` | 消息循环必须在托盘线程 |
| 托盘状态 | `update_status()`、`set_window_visible()` | `tray/icon.py` | 通过 `WM_TRAY_STATUS` 转交托盘线程 |
| 托盘菜单 | `TrayMenu` | `tray/menu.py` | 键盘导航、焦点恢复、无激活样式 |
| Win32 声明 | `infrastructure/win32.py` | 集中 `argtypes/restype` | 新增调用先在这里声明 |
| 文件日志 | `setup_logging()` / `add_ui_log_sink()` | `infrastructure/logging_setup.py` | exe 目录不可写回退 `%TEMP%` |
| 全局异常 | `sys.excepthook` / `threading.excepthook` | `infrastructure/logging_setup.py` | 已安装，不要重复覆盖 |

### 4.7 测试与本地工具

| 需要什么 | 现成实现 | 位置 | 用法/注意 |
|---|---|---|---|
| 架构边界 | `tests/test_architecture.py` | 测试 | 新增包/导入后跑一次 |
| 批处理行为 | `BuildScriptBehaviorTests`、`CheckScriptBehaviorTests` | `tests/test_packaging.py` | Windows-only；临时目录 + 假可执行文件 |
| 应用组合 | `tests/test_application_launcher_composition.py` | 测试 | 构造期回调、共享对象、回调接线 |
| UI 特征测试 | `tests/test_log_window_*.py`、`tests/test_settings_window.py` | 测试 | 使用 fake 控件，不启动真实窗口 |
| 本地冒烟脚本 | `.zcode/smoke_*.py` | 本地未跟踪 | 只用于开发，不要当生产代码 |
| 假 Luker | `.zcode/build/dummy-luker/` | 本地未跟踪 | 临时 E2E；不要提交 |

---

## 5. 历史经验库（踩坑与回归）

> 新教训追加为 `LSN-24` 及以后；不要删除旧条目。每条尽量写“现象 → 根因 → 修复 → 现在怎么做”。

| ID | 现象 | 根因 | 修复/现状 | 关键提交 |
|---|---|---|---|---|
| LSN-01 | 日志时间戳错乱、清空后旧日志又出现、GCL 日志饥饿 | 日志读取/队列/清空没有统一所有权 | 统一 `LogStore` + `BoundedLogQueue` + `LogController`；清空同时丢队列 | `4c91e77`、`60b7690` |
| LSN-02 | 启停 Luker 时界面卡住 | 在主线程同步 `Popen/stop` | 进程操作全部后台线程 + `TaskRunner` | `6d2e987` |
| LSN-03 | 主题切换后旧回调仍操作已销毁控件 | 配置回调注册/注销不完整 | `add/remove_*_callback` + 窗口销毁时移除 | `b412050` |
| LSN-04 | 托盘/进程线程直接操作 Tk 导致随机崩溃 | Tk 非线程安全 | `UiDispatcher` 统一投递主线程 | `c7ff0b6` |
| LSN-05 | 托盘图标消失/重复/退出后残影 | HICON 生命周期、Explorer 重启、消息循环退出不干净 | 新图标生效后再释放旧图标；`TaskbarCreated` 重新添加；`stop()` 消息/线程兜底 | `c7ff0b6`、`3260c48` |
| LSN-06 | 64 位 Windows 下托盘/窗口句柄偶发异常 | ctypes 未声明 `restype`，句柄按 C int 截断 | `infrastructure/win32.py` 集中声明；托盘文件内也声明 | `b3a7066`、`77b9a75` |
| LSN-07 | 启动器被强杀后 node 仍占端口 | 没有 Job Object 兜底 | `KILL_ON_JOB_CLOSE` | `6f2258d` |
| LSN-08 | 150% 缩放下立绘过大、被裁切 | `winfo_*` 物理像素直接传给 `CTkImage(size=逻辑像素)` | 先除以 `_get_widget_scaling()`；缓存键含 scale | `16dbd3f` |
| LSN-09 | 长时间运行内存上涨 | 日志队列/存储无上限 | 条数 + UTF-8 字节双上限；搜索结果上限 | `a8f9b5e` |
| LSN-10 | 打开日志窗口时卡顿 | 一次性插入全部历史日志 | 200 条/批、1ms 让出；隐藏时只存不渲染 | `f93b14f` |
| LSN-11 | 实时日志到达时搜索跳回第一条 | 每次日志都全量重跑搜索并重置当前项 | 250ms 合并刷新；保留当前结果和视口 | `8f3f84b` |
| LSN-12 | 关闭设置窗口后其他滚动区域滚轮失效 | CTkScrollableFrame 用 `bind_all`，销毁不解绑 | `clear_scroll_bindings()` + “同时只有一个设置窗口”不变量 | `994ce62` |
| LSN-13 | CTk 升级后开关动画/文本控件失效 | 依赖 `_canvas`、`_draw_engine`、`_textbox` 私有接口 | `CtkSwitchAdapter` 隔离；版本锁 `<6.1` | `5a41744` |
| LSN-14 | 副屏在左侧/上方时窗口跑到屏幕另一端 | Tk 把 `-100` 解释为距右/下边缘偏移 | `format_geometry()` 输出 `+-100` | `fe149c4` |
| LSN-15 | 标题栏空白处不能拖动窗口 | Tk 鼠标事件只发给指针下控件，不冒泡 | `bind_window_drag()` 绑定标题栏和所有子控件 | 早期版本 |
| LSN-16 | `check.bat` 某道门禁失败却继续/静默中断 | `python` 解析到 `.bat` 包装器时批处理不返回 | 五道门禁全部 `call python ...`；新增失败传播测试 | `3966429` |
| LSN-17 | 更新目标提交号可能被 git 当成选项 | 短 SHA/任意字符串直接拼命令 | 只接受完整 40 位十六进制 SHA | `7e50e68` |
| LSN-18 | npm 安装环境与 `Start.bat` 不一致 | 少了 `NODE_ENV=production` | 只给 npm 安装补环境变量，不改 node 运行环境 | `79e2a78` |
| LSN-19 | 主题卡片悬停后残留边框/图片 | 快速进出、滚轮、窗口 Leave 的指针校准复杂 | 先修残影，后整体回滚放大；现在只做颜色过渡 | `b6ce9f5`、`e9bc44f` |
| LSN-20 | 退出线程创建失败时 Luker 残留 | 失败分支只 `finish_exit()`，没 `stop_all()` | 主线程同步 `stop_all()`，`finally` 退出 | `707dd44` |
| LSN-21 | 组合根构造期间回调访问未初始化的 `_status` | lambda 延迟绑定，构造顺序耦合 | `getattr(self, '_status', None)` 空值保护 + 测试 | `3ad154f` |
| LSN-22 | 打包后主题图片缺失但测试仍通过 | 只检查 spec 文本/源文件，不检查 `datas` 目标目录 | 解析 `datas` 元组，断言源路径和目标目录 | `3966429` |
| LSN-23 | 座右铭/字体/立绘布局反复 | 产品视觉迭代 | 最终移除座右铭；保留左侧渐隐和 320 面板 | `a512226`…`a7a1c68` |

---

## 6. 开放问题与技术债

> 新问题追加为 `OPEN-xx`；关闭时把状态改为 `已关闭`，并在 §10 对应日志里写修复提交。不要在旧条目上涂改原因。

### 6.1 仍然开放

| ID | 优先级 | 事项 | 证据 | 影响 | 建议 | 状态 |
|---|---|---|---|---|---|---|
| OPEN-01 | P3/发布 | `APP_VERSION` 仍是 4.0，HEAD 未构建 | `config.py:25`、`version_info.txt` | 若现在发布，exe 版本与 v4.0 相同；主题/DPI 修复未进发布物 | 发布前 bump 4.1；构建并验证 exe；先问用户 | 未开始 |
| OPEN-02 | P3/验证 | 真实 125%/150% 设备未验收 | 之前只有模拟缩放截图 | 立绘/窗口在真实高 DPI 下可能有观感差异 | 在真实设备跑 §8.4 | 未开始 |
| OPEN-03 | P3/打包 | 完整 PyInstaller 构建不在门禁 | `tests/test_packaging.py` 只做静态/批处理测试 | 资源可能漏进 exe；构建失败可能晚发现 | 发布前手动 `build.bat` + 启动检查 | 未开始 |
| OPEN-04 | P3/更新 | 真实 npm 更新未实机验证 | 单测 fake `Popen`；`_run_npm_process` 真实路径 | `npm.cmd`/代理/超时在真实环境可能有差异 | 在一次性 Luker 副本上验证，不要动主安装 | 未开始 |
| OPEN-05 | P3 | `resizing.py` 可缩放分支是死代码 | 生产唯一调用 `log_window.py:242` `resizable=False` | 约百行不可达代码和测试仍在维护 | 若固定尺寸是最终决策，删除 `resizable=True` 分支；否则加注释 | 待产品确认 |
| OPEN-06 | P3 | 设置窗口与 `WindowResizer` 重复跨屏逻辑 | `settings_window.py:329-350` / `resizing.py:119-159` | 两套规则，未来改一处容易漏另一处 | 抽 `refit_window_to_monitor()` 到 `ui/dpi.py`；行为不变 | 未开始 |
| OPEN-07 | P3 | `clear_scroll_bindings` 清全局绑定 | `settings_window.py:110-119` | 将来新增滚动区域时，关闭设置窗口可能误删绑定 | 保留“同时一个设置窗口”不变量；升级 CTk 后改实例级解绑 | 已知风险 |
| OPEN-08 | P3 | `_ThemeCardHighlight` 自建动画状态机 | `settings_window.py:153-215`；`ui/motion.py` 已有 `StepTicker` | 两套取消语义，维护成本高 | 下次改动画时复用 `StepTicker`；不要现在大改 | 未开始 |
| OPEN-09 | P3 | `settings_window.py` 1369 行、`log_window.py` 1294 行 | 文件规模 | 评审/合并/定位成本高 | 只在下一次必然修改时小步提取；不要现在大拆 | 未开始 |
| OPEN-10 | P3 | `LogWindow._get_textbox()` 访问 CTk 私有 `_textbox` | `log_window.py:1126-1128` | CTk 升级可能破坏 | 保持版本锁；新增私有访问放适配层 | 已接受 |
| OPEN-11 | P3 | 托盘 `stop()` 极端失败路径 | `tray/icon.py:604-624` | `PostMessage`/`PostThreadMessage` 都失败时线程可能不退出 | 记录日志；实机极端场景验证 | 已接受 |
| OPEN-12 | 产品 | 当前主题只用 accent 边框标识 | `settings_window.py:742-748` | 低对比度/色觉差异用户可能难确认 | 若用户要求，加小徽标；不是 bug | 产品取舍 |
| OPEN-13 | 合规 | DeepSeek 素材/名称授权 | `assets/deepseek/*` | 发布前需确认 | 由用户确认，不是代码问题 | 待确认 |

### 6.2 已关闭，不要重复做

| 事项 | 修复提交 | 现状 |
|---|---|---|
| 退出线程失败残留 Luker | `707dd44` | 主线程同步 `stop_all()` + 测试断言 |
| 高 DPI 立绘裁切 | `16dbd3f` | 物理/逻辑换算 + 1.25/1.5 测试 |
| 打包 `datas` 目标目录/`check.bat` 失败传播 | `3966429` | 测试已覆盖；`call python` 已修 |
| 立绘适配任务销毁后仍执行 | `d484c4a` | `_cancel_animation_jobs()` 取消 `_character_fit_job` |
| 未使用的 `_theme_cards` | `6a1f2fb` | 已删除 |
| 主题图片异常过宽 | `0e6f34a` | 收窄为 `(OSError, ValueError)` |
| 组合根构造期回调 | `3ad154f` | 空值保护 + 组合测试 |
| 主题卡片悬停放大残影 | `b6ce9f5` → `e9bc44f` | 已回滚为颜色过渡 |
| GCL 重复启动/端口占用 | `b840bf1` | 已整体移除 |
| 主题卡片选中文字 | `2d6acda` / `00dec31` | 已移除，只保留 accent 边框 |
| 座右铭 | `a7a1c68` | 已移除；不要再加 |

---

## 7. 待办与下一步（可领取）

> 领取时把状态改为 `进行中`，在 §0.2 记录 HEAD；完成后改为 `已完成` 并追加 §10 日志。优先级是建议，不是用户命令。

| ID | 优先级 | 任务 | 验收标准 | 依赖 | 状态 |
|---|---|---|---|---|---|
| TODO-01 | P1/发布 | 发布验证 4.1 | `APP_VERSION`/`version_info.txt` bump；`build.bat` 成功；exe 在 100%/125%/150% 下主题/立绘/日志/设置正常；资源可读 | 用户确认是否发布 | 待确认 |
| TODO-02 | P2/验证 | 真实高 DPI 验收 | 真实 125%/150% 设备跑 §8.4；记录截图/窗口尺寸 | 设备条件 | 待开始 |
| TODO-03 | P2/打包 | 完整 exe 构建冒烟 | `build.bat` 返回 0；`_MEIPASS` 资源存在；隔离启动无「加载主题图片失败」 | PyInstaller 环境 | 待开始 |
| TODO-04 | P2/更新 | 真实 npm 更新验证 | 一次性 Luker 副本；更新成功/失败回滚/依赖恢复；不改主安装 | 用户授权副本 | 待开始 |
| TODO-05 | P3/决策 | 固定日志窗口最终决策 | 用户确认是否保留拖拽；若否，删除 `resizable=True` 分支及测试 | 产品确认 | 待确认 |
| TODO-06 | P3/重构 | 抽 `refit_window_to_monitor()` | 设置窗口与日志窗口共用；行为不变；补测试 | 无 | 待开始 |
| TODO-07 | P3/加固 | 滚动绑定实例级解绑 | 关闭设置窗口不影响其他滚动区域；补测试 | CTk 升级/方案确认 | 待开始 |
| TODO-08 | P3/重构 | 复用 `StepTicker` 统一悬停动画 | 主题卡片悬停颜色过渡不变；减少一套状态机 | 无 | 待开始 |
| TODO-09 | P3/拆分 | 大 UI 文件按需小步提取 | 只在下一次必然修改时做；行为不变；先补特征测试 | 有实际需求 | 待开始 |

---

## 8. 测试与验证手册

### 8.1 测试布局

| 文件 | 测试数 | 覆盖重点 |
|---|---:|---|
| `tests/test_core_version.py` | 60 | Git/GitHub/npm、版本关系、回滚、npm 参数/环境 |
| `tests/test_settings_window.py` | 54 | 设置窗口构建、主题、版本、更新、生命周期 |
| `tests/test_application_update_coordinator.py` | 36 | 检查缓存、序号、更新阶段、失败/重启 |
| `tests/test_config.py` | 35 | 配置归一化、BOM、路径、端口、保存 |
| `tests/test_browser.py` | 33 | APPX/Edge/PWA/默认浏览器回退 |
| `tests/test_log_pipeline.py` | 30 | 队列、重放、控制器、搜索刷新 |
| `tests/test_dpi.py` | 26 | 监视器、放置、缩放、几何 |
| `tests/test_log_search.py` | 26 | 搜索、跳过装饰、高亮、调整 |
| `tests/test_log_window_theme.py` | 24 | 立绘、主题、DPI、绑定、动画 |
| `tests/test_ui_window_utils.py` | 22 | 模糊、圆角、拖动、字体 |
| `tests/test_application_process_coordinator.py` | 20 | 启停/路径/忙碌/线程失败 |
| `tests/test_ui_resizing.py` | 19 | 初始尺寸、跨屏、拖拽 |
| `tests/test_application_lifecycle_coordinator.py` | 18 | ask/tray/exit、线程失败、幂等 |
| `tests/test_ui_dispatch.py` | 18 | 合并、上限、control 队列、停止 |
| `tests/test_ui_icons.py` | 18 | 图标渲染 |
| `tests/test_tray_menu.py` | 16 | 菜单状态、键盘、焦点 |
| `tests/test_application_browser_coordinator.py` | 14 | 自动/手动、去重、超时 |
| `tests/test_application_status_coordinator.py` | 14 | 三态、轮询、过期回调 |
| `tests/test_tray_icon.py` | 14 | 句柄、图标更新、消息循环 |
| `tests/test_dialogs.py` | 14 | 关闭框、路径选择、定位 |
| `tests/test_architecture.py` | 13 | 依赖方向、根目录、import cycle |
| 其余 | — | 日志存储/显示、进程、托盘键盘、主题、Windows API 等 |

> 总计 758 项。`tests/test_architecture.py` 不是“可选检查”，它会在新增错误导入时直接失败。

### 8.2 门禁命令

```bat
check.bat
```

依次执行：

1. `python -m ruff format --check .`
2. `python -m ruff check .`
3. `python -m mypy .`
4. `python -m coverage run -m unittest discover -s tests -q`
5. `python -m coverage report`（`fail_under = 65`）

`check.bat` 的每道门禁都用 `call python ...`；失败会 `goto fail`，输出 `Check failed.`，返回非零。

`build.bat`：

```bat
call pyinstaller launcher.spec --noconfirm --distpath .
```

失败时不清理 `build/`、不打印 `Done!`、返回非零；成功才清理 `build/`。

<a id="a00-test-gaps"></a>
### 8.3 覆盖到/没覆盖到什么

**覆盖较好：**

- 配置边界、BOM、路径、端口缓存；
- 进程启停/路径切换/线程失败/stop_all；
- 三态就绪、轮询、过期回调；
- 退出 ask/tray/exit、对话框降级、线程失败；
- 版本检查/更新/回滚/npm 参数；
- 日志队列/重放/搜索/显示裁剪；
- DPI 放置、窗口缩放；
- 托盘句柄、菜单键盘；
- 架构依赖方向、批处理失败传播、打包 `datas`。

**覆盖不足/需要人工：**

- 真实 PyInstaller 构建后的 `_MEIPASS` 资源读取（测试只检查 spec/datas）；
- 真实 125%/150%/200% Windows 设备观感（只有模拟缩放测试）；
- 真实 npm 更新（单元测试用 fake Popen；真实 `npm.cmd` 路径未实机验证）；
- 真实托盘菜单点击/Explorer 重启/多显示器热插拔；
- 真实 Luker 进程被强杀后的 Job Object 行为；
- 托盘线程 `PostMessage` 失败等极端退出路径。

### 8.4 手工冒烟清单

使用**临时目录 + 假 Luker**，不要改用户配置：

1. `python main.py`：窗口、托盘、日志、按钮、主题切换、设置窗口。
2. 假 Luker 的 `Start.bat`/`server.js`：启动/停止/重启/端口占用提示。
3. 关闭窗口三种行为：ask / tray / exit；记住选择。
4. 版本检查：无网络、Git 非仓库、dirty、缺 npm、ahead/behind/diverged。
5. 100%/125%/150% 缩放：日志窗口、立绘、设置窗口、托盘菜单。
6. 双屏（不同 DPI）：拖动窗口/设置窗口/托盘菜单，检查位置和尺寸。
7. 托盘：左键切换、双击显示、右键菜单键盘导航、Explorer 重启后恢复。
8. 退出：正常退出、托盘不可用降级、更新中阻止退出。

<a id="a00-test-data"></a>
### 8.5 测试数据规则

- 不修改根目录 `launcher_config.json`。
- 使用临时目录 + 临时配置；测试结束清理。
- 托盘/窗口测试用 fake 控件或 `object.__new__(...)`，不要启动真实 GUI。
- Windows-only 批处理测试用临时目录 + 假 `python.bat`/`pyinstaller.bat`，不要执行真实构建/安装。

---

## 9. 术语与附录

### 9.1 术语表

- **Coordinator**：只负责一类业务流程的对象；通过构造函数注入依赖，便于单测。
- **组装根（composition root）**：只负责创建对象、接线、启动主循环的地方，不写业务细节。
- **UiDispatcher**：后台线程 → Tk 主线程的安全投递队列；普通事件可合并/丢弃，生命周期完成回调走独立 control 队列。
- **就绪（READY）**：进程存活且本地 HTTP 连续成功；不是“进程一启动就算就绪”。
- **Job Object**：Windows 内核对象；设置 `KILL_ON_JOB_CLOSE` 后，句柄关闭会终止其中所有进程。
- **GPG `G`**：`git log --format='%G?'` 输出 `G` 表示签名有效。
- **onefile / `_MEIPASS`**：PyInstaller 单文件 exe 运行时把资源解压到临时目录；`resource_path()` 必须指向那里。
- **物理像素/逻辑像素**：Windows 150% 缩放下，1 逻辑像素 = 1.5 物理像素；Tk `winfo_*` 是物理，CTk `geometry` 宽高/`CTkImage(size)` 是逻辑。
- **P2/P3**：P2 是中高优先级（用户可见/残留进程，发布前应修）；P3 是维护性/低风险改进。
- **回归测试**：先写一个能复现问题的测试，修复后必须通过，防止再次出现。

### 9.2 配置文件 schema

`launcher_config.json`（exe 同目录；模板 `launcher_config.example.json`）：

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `luker_path` | string | `""` | Luker 根目录，需含 `Start.bat` + `server.js` |
| `sillytavern_path` | string | 无 | 旧版兼容键；读取时作为 `luker_path` 回退，写入新键后清理 |
| `use_pwa_mode` | bool | `false` | 沉浸应用模式（PWA） |
| `blur_enabled` | bool | `true` | 毛玻璃；`mist_gray` 固定关闭 |
| `close_behavior` | string | `"ask"` | `ask` / `tray` / `exit` |
| `theme` | string | `"summer"` | 主题 ID；旧 ID 自动迁移 |
| `pwa_app_id` | string | `""` | Edge PWA App ID（可选） |
| `pwa_appx_family_name` | string | `""` | APPX PackageFamilyName（可选） |

未知键、类型不正确的值会被丢弃；字符串会去空白；theme/close_behavior 白名单校验。

### 9.3 关键提交速查

| 提交 | 日期 | 主题 |
|---|---|---|
| `cb75d8b` | 2026-10-02 | 初始导入（v1.0） |
| `4c91e77` | 2026-10-18 | 日志时间戳/清除/GCL 饥饿 |
| `6d2e987` | 2026-10-18 | 进程启停后台化 |
| `4c32010` | 2026-10-18 | 合并 Luker/GCL 进程管理器 |
| `0755a14` | 2026-10-18 | 拆分日志/主题/配置 |
| `c7ff0b6` | 2026-10-18 | UI 队列 + 托盘生命周期 |
| `6f2258d` | 2026-10-18 | 单实例/Job Object/外部 Luker |
| `34f95d2` | 2026-10-19 | 高 DPI 适配 |
| `555f658` | 2026-10-20 | APPX 包族名校验（命令注入） |
| `a8f9b5e` | 2026-10-20 | 日志队列/搜索上限 |
| `f93b14f` | 2026-10-20 | 日志分块重放 |
| `6f1f6ec` | 2026-10-22 | 主题切换构建时绑定 |
| `42b1e13` | 2026-10-24 | 应用主体移入独立模块 |
| `2f96c3e` | 2026-10-26 | Luker 版本检查/更新 |
| `3260c48` | 2026-10-30 | 托盘句柄/消息循环加固 |
| `69dc96f` | 2026-10-30 | 配置读取/路径边界 |
| `cc6f815` | 2026-10-30 | 构建失败返回非零 |
| `79e2a78` | 2026-10-30 | npm `NODE_ENV=production` |
| `b840bf1` | 2026-11-02 | **移除 GCL** |
| `ce3bc04` | 2026-11-02 | 托盘键盘导航 |
| `5a41744` | 2026-11-04 | CTk 私有开关适配层 |
| `547160a` | 2026-11-05 | Coordinator 基础 |
| `a66f873` | 2026-11-05 | v4.0 |
| `64f1a06` | 2026-11-08 | DeepSeek 主题 |
| `00dec31` | 2026-11-09 | 固定日志窗口/立绘 |
| `707dd44` | 2026-11-09 | 退出失败同步停止 |
| `16dbd3f` | 2026-11-09 | 高 DPI 立绘修复 |
| `3966429` | 2026-11-09 | 打包/门禁测试补强 |
| `e9bc44f` | 2026-11-09 | 回滚主题卡片悬停放大 |
| `a7a1c68` | 2026-11-10 | 最终立绘布局 |

### 9.4 事实来源

- `README.md`：产品行为、配置、构建、版本管理说明。
- `pyproject.toml`：ruff/mypy/coverage 配置。
- `check.bat` / `build.bat` / `launcher.spec` / `version_info.txt`：门禁与打包。
- `.zcode/reports/review-2026-11-09.md`：全仓库审查（两个 P2、P3 清单）。
- `.zcode/reports/review-fixes-2026-11-09.md`：P2 修复与验证记录。
- `.zcode/reports/implementation-2026-11-05.md`：Coordinator/分包执行记录。
- `.zcode/reports/launcher-refactor-and-package-plan-2026-11-05.md`：架构抽取与分包方案。
- `.zcode/reports/ai-gijika-deepseek-2026-11-08.md`、`ai-gijika-polish-2026-11-09.md`：主题/立绘迭代记录。
- Git：193 个提交、17 个标签、`git log --stat`、`git diff`、`git show`。

---

> 本册是 2026-11-14 的详细手册快照，只读。
> §10 的详细日志已按版本段拆分到 `01`–`04`；提交覆盖图见 [`../development-handbook.md`](../development-handbook.md) §10.1。
> 导航：[归档索引](README.md) · [条目索引](INDEX.md) · [主手册](../development-handbook.md)
