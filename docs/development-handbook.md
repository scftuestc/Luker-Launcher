# Luker Launcher 开发手册与持续开发日志

> **文档类型**：可持续维护的开发手册 + 只追加日志（Living Document）
> **文档编号**：`LH-LUKER-001`
> **结构版本**：`4.0`
> **文档位置**：`docs/development-handbook.md`（Git 跟踪；唯一日常写入目标）
> **事实截止**：`2026-11-14`
> **代码分支 / 最后代码提交**：`ai-gijika` / `a7a1c68`（文档提交见 `git log -- docs/development-handbook.md`）
> **当前版本**：`APP_VERSION = 4.0`（HEAD 未 bump，未重新发布）
> **质量基线**：758 tests / 74% / `check.bat` pass
> **完整历史归档**：`docs/archive/README.md`（00–04 分册，只读）
> **维护方式**：每个任务结束后，在 **§10 末尾追加** 一条 `DEV-YYYYMMDD-NN`，更新 §0.2、§6、§7，并随任务提交。

---

## 交接摘要（每次交接更新）

- **当前状态**：`ai-gijika` / `a7a1c68`（最后代码提交；文档提交见 `git log`）；工作区 clean；758 tests / 74% / `check.bat` pass。
- **最近完成**：DeepSeek 主题、角色立绘、固定日志窗口、两个 P2 修复、审查整改、最终移除座右铭并把滚动条移到最右。
- **当前阻塞**：`APP_VERSION` 仍为 4.0；HEAD 未 bump、未构建 exe、未在真实 125%/150% 设备验收；是否发布需用户确认。
- **建议下一步**：先确认是否发布；若发布，按 `TODO-01` 做版本 bump + 构建 + 100%/125%/150% 验收。不要先做大重构。
- **不要重复**：不要重新引入 GCL；不要恢复主题卡片悬停放大；不要加回座右铭；不要恢复日志窗口拖拽缩放；不要改 npm 参数。
- **文档入口**：先读 `docs/README.md`；日常只写 `docs/development-handbook.md`；历史按版本段查 `docs/archive/`。
- **文档使用**：任务完成后在 §10 末尾追加 `DEV-YYYYMMDD-NN`，更新 §0.2、§6、§7，并随任务提交。

**常见问题速查**：

| 你可能问 | 看这里 |
|---|---|
| 某个能力是不是已经实现过？ | §4 可复用组件目录 |
| 为什么代码这样设计？ | §3 ADR |
| 这个坑以前踩过吗？ | §5 经验库（LSN） |
| 现在还有什么没做？ | §6 开放问题 + §7 待办 |
| 最近一次改了什么？ | §10 末尾的 `DEV` 条目 |
| 发布前要做什么？ | §7 `TODO-01` + §8.4 |
| 详细历史在哪？ | `docs/archive/README.md`（按版本段选分册） |

**最小必读（约 20 分钟）**：`docs/README.md`、§0（规范）、§1（基线）、§2（架构）、§3（ADR）、§4（组件）、§6（开放问题）、§7（待办）。§5/§10 按需查；不要从头读到尾。

**权威顺序**：代码/测试/README > 本手册 > `docs/archive/` > 本地工作记录。冲突时以更靠前的来源为准。

---

## 0. 文档使用规范

### 0.1 文档目的

这个文件解决三个问题：

1. **项目记忆**：193 个提交、17 个标签之后，新 Agent 不需要从零猜“为什么代码长这样”。
2. **避免重复造轮子**：已有组件、工具、设计决策集中登记；写新代码前先查 §4。
3. **可持续交接**：每个任务结束后按统一格式追加日志；下一个 Agent 可以接着写，而不是重写整份文档。

**边界**：本文件记录事实、决策、验证、遗留，不替代 README、代码注释和测试。产品行为以 README + 代码 + 测试为准；本文件解释原因和历史。

### 0.2 文档控制表

| 字段 | 当前值 | 更新时机 |
|---|---|---|
| 文档编号 | `LH-LUKER-001` | 结构变更时 |
| 文档位置 | `docs/development-handbook.md`（Git 跟踪） | 结构变更时 |
| 结构版本 | `4.0` | 结构调整时 |
| 最后更新 | `2026-11-14` | 每次追加日志 |
| 最新日志条目 | `DEV-20261114-03` | 每次追加日志 |
| 下一条日志 ID | `DEV-20261114-04` | 每次追加日志 |
| 代码基线 / 最后代码提交 | `ai-gijika` / `a7a1c68` | 每次任务开始/结束 |
| 当前版本 | `APP_VERSION = 4.0` | 版本 bump 时 |
| 工作区状态 | clean（`docs/` 已跟踪；文档改动随任务提交） | 每次任务结束 |
| 质量基线 | 758 tests / 74% / check.bat pass | 每次任务结束 |
| 完整历史归档 | `docs/archive/README.md`（只读，00–04 分册） | 不再更新（只读参考） |

### 0.3 事实等级与写作规则

| 标签 | 含义 | 例子 |
|---|---|---|
| `[已验证]` | 代码、测试、命令或 Git 历史可直接证明 | `git rev-list --count v1.0..v1.1` = 10 |
| `[推断]` | 根据提交信息/代码结构推断，未单独实验 | “可能是为了避免重复开浏览器” |
| `[待确认]` | 需要用户/产品/实机确认 | “真实 150% 设备观感” |

写作规则：

- 日期 `YYYY-MM-DD`；提交用 7 位短哈希；文件引用 `path:line`。
- 不粘贴大段命令输出；只写“命令 + 关键结果”。
- 不写“优化了代码”这种空话；必须写**改了什么行为、哪个文件、哪个测试**。
- 未验证的内容标 `[待验证]`/`[待确认]`，不要写成已完成。
- 旧日志不修改；发现错误在 §0.9 加“勘误”，并引用旧条目。
- 决策被推翻时，不删除旧 ADR；新增 ADR 并标注“取代 ADR-xx”。

### 0.4 状态、类型、优先级

**状态**：`待开始`、`进行中`、`待验证`、`已完成`、`已发布`、`已回滚`、`已废弃`、`阻塞`。

**类型**：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`perf`、`release`、`revert`。

**优先级**：`P0` 立即；`P1` 发布前必须；`P2` 发布前应修；`P3` 维护性/可延后。

### 0.5 每次任务后的追加流程（必须执行）

1. **确定 ID**：`DEV-YYYYMMDD-NN`；当天下一条见 §0.2。
2. **在 §10 末尾追加**：复制 §0.6 模板；不要插入旧条目中间，不要重排历史。
3. **填完整**：目标、改动、验证、决策/风险、遗留/下一步。验证必须写命令和结果。
4. **更新 §0.2**：最后更新、最新条目、下一条 ID、HEAD、质量基线。
5. **更新 §6/§7**：关闭/新增开放问题；更新 TODO 状态。
6. **架构/决策/组件变了**：更新 §2/§3/§4，并在 §0.9 加一行修订记录。
7. **随任务提交本文件**：本文件在 `docs/` 下，必须随任务提交；提交作者/签名遵循仓库约束（仅 Yaoyao、GPG 签名、无 AI 署名）。不要复制回 `.zcode/`。
8. **更新顶部“交接摘要”**：状态/阻塞/下一步变了就同步。
9. **交接时**：填写 §0.8 检查表；在 §10 最后一条写“交接点”。

**归档轮转**：当 §10 超过 30 条或一个主版本结束时，把较早条目的详细内容迁到 `docs/archive/05-...`，§10 只保留摘要和链接；不要删除历史。

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

> 小改动可压缩为 6~10 行，但“日期 / 提交 / 类型 / 状态 / 改动 / 验证 / 遗留”不能缺。

### 0.7 文档地图

| 章节 | 内容 | 更新频率 |
|---|---|---|
| §0 | 规范、控制表、模板 | 结构变更时 |
| §1 | 基线、分支/版本、质量 | 每次发布/交接 |
| §2 | 架构、启动、运行流程 | 架构变更时 |
| §3 | ADR 决策表 | 决策变更时 |
| §4 | 可复用组件目录 | 新增/删除组件时 |
| §5 | 历史经验库（LSN） | 新增教训时 |
| §6 | 开放问题/技术债 | 状态变化时 |
| §7 | 待办（可领取） | 领取/完成时 |
| §8 | 测试与验证手册 | 命令/覆盖变化时 |
| §9 | 术语、配置、来源 | 按需 |
| §10 | **开发日志（只追加）** | 每个任务结束 |

**文件地图**：

| 文件 | 内容 | 读写 |
|---|---|---|
| `docs/README.md` | 文档入口、阅读路径、权威顺序 | 只读；结构变更时更新 |
| `docs/development-handbook.md` | 本文件：稳定知识 + 开放问题/TODO + 只追加日志 | **唯一日常写入目标** |
| `docs/archive/README.md` | 归档索引、分册导航、快照边界 | 只读 |
| `docs/archive/00-detailed-handbook-2026-11-14.md` | 2026-11-14 详细手册快照（§0–§9） | 只读 |
| `docs/archive/01-v1.0-v2.0-foundation.md` | v1.0–v2.0 基座期日志 | 只读 |
| `docs/archive/02-v2.1-v3.3-engineering.md` | v2.1–v3.3 工程化与视觉日志 | 只读 |
| `docs/archive/03-v3.4-v3.5-visual-reliability.md` | v3.4–v3.5 设计令牌与可靠性日志 | 只读 |
| `docs/archive/04-v4.0-coordinator-themes-ui.md` | v4.0+ Coordinator/主题/UI 日志 | 只读 |

> 日常任务只改主手册；只有归档轮转或文档结构变更时，才改 `docs/README.md` 和 `archive/README.md`。

### 0.8 交接检查表

接手时：

- [ ] 已读 §1、§2、§3、§4。
- [ ] `git status` 干净；当前分支/最后代码提交已写入 §0.2。
- [ ] 已跑 `check.bat`；测试数/覆盖率已记录。
- [ ] 已看 §6 开放问题、§7 待办。
- [ ] 已确认硬约束：不推送、不改用户配置、GPG 签名、作者只有 Yaoyao、无 AI 署名。
- [ ] 已确认 `docs/` 已跟踪；本次文档改动会随提交进入版本库；作者/签名符合约束（仅 Yaoyao、GPG、无 AI 署名）。

交班时：

- [ ] 最后一条 §10 日志写清“已完成/未完成/下一步”。
- [ ] §0.2 的 HEAD/质量基线是最新的。
- [ ] §6/§7 状态已更新。
- [ ] 未验证项已标 `[待验证]`。
- [ ] 工作区没有未说明的改动。

### 0.9 文档修订记录

| 日期 | 版本 | 修改人 | 说明 |
|---|---|---|---|
| 2026-11-14 | 1.0 | 上一轮审查 | 初版叙述式历史文档（994 行） |
| 2026-11-14 | 2.0 | ZCode | 重构为“稳定知识 + 只追加日志”；修正 v1.2/v2.0 提交区间 |
| 2026-11-14 | 3.0 | ZCode | 精简主文档；完整细节归档到 `development-history-full-2026-11-14.md` |
| 2026-11-14 | 4.0 | 文档维护 | 迁入 `docs/` 并纳入 Git；主文档改名 `development-handbook.md`；完整归档拆为 00–04 只读分册；明确唯一写入目标。原“文件需 gitignore”的要求已被本次用户决定取代。 |

> 勘误格式：`日期 | 影响条目 | 原内容 | 更正`。

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

Luker 是基于 SillyTavern 的 LLM 前端；启动器只要求目录包含 `Start.bat`、`server.js`，并从 `config.yaml` 读取端口。

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

### 1.3 硬约束（来自用户）

- **不要推送到远程**；不要打标签、不要发布 Release，除非用户明确确认。
- **作者/提交者只能是** `Yaoyao <jiayinyao24@outlook.com>`；不要 `Co-authored-by`、`Signed-off-by` 或 AI/GPT 署名。
- **提交必须 GPG 签名**；提交后 `git log --format='%G?'` 必须是 `G`。
- **不要修改用户的 `launcher_config.json`**；测试/冒烟用临时目录或临时配置。
- **不要改变 UI 行为、npm 参数、配置格式、窗口尺寸策略**，除非任务明确要求。
- **不要把架构抽取和包文件搬家混在一个大提交里**。
- 远程仓库：`https://github.com/scftuestc/Luker-Launcher.git`。

### 1.4 分支与发布

| 分支/标签 | 指向 | 说明 |
|---|---|---|
| `main` | `fc06d38` | 已发布主线；`v4.0` 之后只有 README 精简 |
| `dev` | `a512226` | 主题分支中间点（含座右铭浮层版本） |
| `ai-gijika` | `a7a1c68` | 当前工作分支；比 `main` 多 19 个提交，比 `dev` 多 3 个 |
| `origin/ai-gijika` | `a7a1c68` | 远程已有同名分支，本地同步；**不要据此推送** |
| `v4.0` | `a66f873` | 最新正式标签；GitHub 已发布 |
| `v3.5` / `v3.5.0` | `ec0b561` | 重复标签，历史遗留 |

> `ai-gijika` 的 19 个提交没有 bump 版本，也没有重新发布。根目录现有 exe 是 4.0 时期构建，不代表 HEAD。`main`/`dev` 不包含这 19 个提交；不要自行 merge/rebase/推送，先问用户。

### 1.5 版本坐标（提交范围含端点）

| 版本 | 日期 | 提交范围 | 数量 | 一句话 |
|---|---|---|---:|---|
| `v1.0` | 2026-10-02 | `cb75d8b` | 1 | 导入原型（14 文件 / 3,733 行） |
| `v1.1` | 2026-10-18 | `206c1d1..38be292` | 10 | 日志/GCL/进程/PWA/托盘第一轮修复 |
| `v1.2` | 2026-10-18 | `6343f3e..5cfb3b3` | 6 | 日志/界面资源优化、自动路径、清空队列 |
| `v2.0` | 2026-10-19 | `4c32010..4e98b09` | 10 | 合并进程管理器、拆日志/主题/配置、UI 队列、单实例/Job Object、文件日志、首批测试 |
| `v2.1` | 2026-10-19 | `71a73e3..c224c69` | 7 | ruff/CI/LICENSE、托盘菜单/设置窗口拆分、类型注解 |
| `v2.2` | 2026-10-19 | `34f95d2..34d01e3` | 6 | 高 DPI 跨屏、托盘/进程生命周期 |
| `v2.3` | 2026-10-20~21 | `b5993f0..aad0cad` | 10 | GCL/PWA 竞态、APPX 校验、日志窗口最小尺寸、队列/重放上限 |
| `v2.4` | 2026-10-21 | `b69d47d..3729554` | 17 | 日志队列/搜索/显示/重放拆分、窗口缩放、UI 调度器 |
| `v3.0` | 2026-10-22~23 | `24f9db0..b480684` | 20 | 主题/毛玻璃/圆角/按钮/呼吸 logo/关闭确认/托盘图标 |
| `v3.1` | 2026-10-24~25 | `fe149c4..c778e3b` | 20 | 应用主体拆分、日志/搜索拆分、目录分包 |
| `v3.2` | 2026-10-25~27 | `43476f0..523764c` | 14 | 关闭行为记忆、版本检查/更新、设置页、本地门禁 |
| `v3.3` | 2026-10-30 | `3260c48..5f9e402` | 9 | 托盘句柄、配置边界、构建失败、npm 生产环境 |
| `v3.4` | 2026-11-02 | `2b9ebdb..16e97be` | 8 | 设计令牌、窗口淡入、日志状态、托盘键盘、**移除 GCL** |
| `v3.4.1` | 2026-11-03 | `ca08bb9` | 1 | 版本号补丁 |
| `v3.5` | 2026-11-03~04 | `5f95490..ec0b561` | 16 | 雾灰关闭毛玻璃、图标/字体、配置 BOM、Win32 声明、CTk 适配层 |
| `v4.0` | 2026-11-05 | `547160a..a66f873` | 18 | **Coordinator 架构 + 单一 `luker_launcher/` 包 + 架构测试** |
| `v4.0+` | 2026-11-05~10 | `fc06d38` + `64f1a06..a7a1c68` | 20 | DeepSeek 主题、立绘、DPI/退出修复、审查整改、布局迭代 |

> 总计 **193**。`v3.5.0` 与 `v3.5` 同提交，统计只算一次。

### 1.6 质量基线（2026-11-14 实测）

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests -q` | **758 项通过**，约 2 秒 |
| 覆盖率 | **74%**（门槛 65%） |
| `ruff format --check .` | 106 个文件已格式化 |
| `ruff check .` | 通过 |
| `mypy .` | 55 个源文件无问题 |
| 工作区 | 干净；`docs/` 已跟踪；本地仍有被忽略的 `.coverage`、`.zcode/` 报告、根目录 exe/log |
| 提交签名 | 193 个提交中 187 个 `G`；6 个 v1.1 时期提交为 `N`（历史事实） |
| 作者/提交者 | 全部 Yaoyao；无 AI 署名 |

> 6 个未签名提交：`38be292`、`6343f3e`、`9ab1fa9`、`fab4cb8`、`60b7690`、`224c7ba`。之后的提交全部 GPG 签名。

### 1.7 审查结论

- 本轮审查与上一轮全仓库审查均未发现 P0/P1。
- 上一轮确认并修复 2 个 P2：
  - 退出线程创建失败可能残留 Luker/Node（`707dd44`）；
  - 高 DPI 立绘物理/逻辑尺寸混用（`16dbd3f`）。
- 剩余 P3 见 §6；不影响基本功能，但不要重复踩。

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
- `config` 不得导入 `application/`、`ui/`、`tray/`；当前只依赖标准库与纯数据 `theme`。
- `ui/` 不得导入 `application/`。
- `theme.py`、`paths.py` 只允许标准库。
- 只有 `luker_launcher.__main__` 可以导入 `bootstrap`。
- 根目录只能有 `main.py` 一个 Python 文件；`main.py` 只导入 `bootstrap.entrypoint`。
- 不允许 import cycle。

### 2.2 模块地图

| 路径 | 职责 | 关键入口 |
|---|---|---|
| `main.py` | 薄入口 | `main()` |
| `bootstrap/entrypoint.py` | 日志、配置错误补报、DPI、单实例、主循环 | `main()`、`setup_dpi_awareness()` |
| `application/launcher.py` | 组装根：UI/托盘/Coordinator、首次运行、主循环 | `LukerLauncher.run()` |
| `application/task_runner.py` | 后台守护线程，失败返回 `False` | `TaskRunner.run()` |
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
- `exit()`：设 `exiting`，后台 `status.stop()` → `process.stop_all()` → `finish_exit`。
- 线程创建失败：主线程同步 `stop_all()`，`finally` 退出（`707dd44`）。
- `finish_exit()` → 幂等 `shutdown()` → `window.quit()`；主循环返回后再兜底。

**版本检查/更新**

- 只有点击“检查更新”才访问 GitHub/`git fetch`；本地 dirty/缺 npm/路径不匹配/Git 失败都是 blocker。
- 更新目标必须是完整 40 位 SHA；`checkout --detach` 后 npm 安装；失败回滚代码并尝试恢复依赖。
- npm 参数与 `Start.bat` 一致，额外 `NODE_ENV=production`；只作用于 npm，不改 `node server.js`。
- `UpdateCoordinator` 用 `version_check_seq` 丢弃过期结果；更新阶段走 `post_control`。

**日志管线**

- `LogStore`：每源 3000 条 / 8 MB；`BoundedLogQueue`：5000 条 / 8 MB。
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
- 立绘：`winfo_*` ÷ `_get_widget_scaling()` → 逻辑尺寸；`render_character()` 按物理像素渲染；`CTkImage(size=逻辑)` 再缩放一次。
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

**不变量**：后台线程不直接碰 Tk；生命周期完成回调走 `post_control`，不会被普通队列丢弃。

### 2.6 状态归属

| 状态 | 所有者 | 主要读者 |
|---|---|---|
| `config` | `config.py` 全局单例 | 所有层只读 |
| `LifecycleState.exiting` | `LifecycleCoordinator` | 所有 Coordinator |
| `ProcessCoordinator.manager/busy` | `ProcessCoordinator` | Status/Update/Lifecycle |
| `StatusCoordinator.last_state` | `StatusCoordinator` | LogWindow/TrayMenu |
| `UpdateCoordinator` 缓存/序号 | `UpdateCoordinator` | SettingsWindow |
| 日志 store/queue/replay | `LogController` | LogWindow |
| 窗口视觉状态 | LogWindow/SettingsWindow | 自身 |
| 托盘状态 | TrayIcon/TrayMenu | Launcher/Status |

---

## 3. 关键设计决策（ADR）

> 新决策追加 ADR；旧 ADR 不删除，标注“被 ADR-xx 取代”。详细背景见完整历史归档。

| ADR | 决策 | 原因/后果 | 不要做 | 证据 |
|---|---|---|---|---|
| ADR-01 | 用 `node server.js`，不通过 `Start.bat` | 需要传 `--browserLaunchEnabled false`；停止/日志可控 | 不要改回 `Start.bat` | `process/managers.py:339-345` |
| ADR-02 | Job Object + 单实例 | 防止强杀后 node 占端口；防止双启动器抢端口 | 不要移除 Job Object/只 terminate 父进程 | `process/job.py`、`single_instance.py` |
| ADR-03 | 后台线程统一经 `UiDispatcher` 回主线程 | Tk 非线程安全；完成回调不能丢 | 不要在后台直接碰 Tk/用普通队列投递完成回调 | `ui/dispatch.py` |
| ADR-04 | 就绪=连续 2 次成功 + READY 粘滞 | 进程活≠服务可用；避免呼吸灯抖动 | 不要每次探测直接 apply | `services/readiness.py` |
| ADR-05 | 配置归一化/原子写入/BOM/端口缓存 | 手改配置、半截写入、每秒读盘 | 不要用 yaml 整体解析只取端口 | `config.py` |
| ADR-06 | 路径切换只在停止时进行 | 运行中热切换会中断/端口冲突 | 不要运行中替换 manager | `process_coordinator.py:56-75` |
| ADR-07 | 更新固定完整 SHA、dirty 检查、可回滚 | 防注入、防意外提交、半更新可恢复 | 不要改 npm 参数/短 SHA/给 node 加 NODE_ENV | `services/version.py:734-808` |
| ADR-08 | 移除 GCL | 无端口探测/健康检查/多实例，接受 Luker `Start.bat` 会重复启动 | 不要重新引入 | `b840bf1` |
| ADR-09 | 日志窗口固定尺寸 | 主题/立绘对尺寸敏感；跨屏仍适配 | 不要未经确认恢复拖拽缩放 | `log_window.py:242` |
| ADR-10 | 主题卡片悬停放大已回滚 | 残影修复成本高；现在只颜色过渡 | 不要加回 relwidth/图片放大 | `e9bc44f` |
| ADR-11 | 座右铭已移除 | 视觉迭代最终决策 | 不要加回 | `a7a1c68` |
| ADR-12 | 门禁只在本地 | Windows 托盘/Win32/DPI 需要 Windows 环境；提交只记录“本地执行” | 不要恢复远程 CI 并声称覆盖托盘 | `43476f0` |
| ADR-13 | CTk 私有接口隔离 + 版本锁 | 6.0 已实测；6.1 Text 接口可能变 | 不要到处直接访问私有属性 | `ui/ctk_adapter.py` |
| ADR-14 | 主题颜色与元数据分离 | 渐变只处理颜色，避免把 name/icon 当颜色 | 不要整个 `PRESET_THEMES` 传给渐变 | `theme.py:256-262` |
| ADR-15 | 版本/打包一起验证，发布需确认 | v4.0 后 19 提交未 bump；直接发布会版本重复 | 不要未经确认 bump/构建/打标签 | `config.py:25` |

**补充说明**：

- ADR-12 的“Windows 环境原因”是 `[推断]`；提交 `43476f0` 只写“门禁改为只在本地执行”。
- ADR-10 的“修复成本高”是根据回滚结果 `[推断]`；事实是悬停放大已回滚。

---

## 4. 可复用组件目录（不要重复造轮子）

> 写新代码前先在这里找；新增组件更新本表；删除组件标记“已废弃”，不要删历史。

### 4.1 应用层

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 后台一次性任务 | `TaskRunner.run()` | `application/task_runner.py` | 失败返回 `False`，调用方复位状态 |
| 跨线程投递 UI | `UiDispatcher.post()`/`post_control()` | `ui/dispatch.py` | 完成回调必须 `post_control` |
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

### 4.3 日志

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 日志级别 | `get_tag_for_line()` | `log/classify.py` | 错误/警告/信息/默认 |
| 有界历史 | `LogStore` | `log/store.py` | 3000 条/8 MB |
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
| CTk 私有接口 | `CtkSwitchAdapter` | `ui/ctk_adapter.py` | 升级只回归这里 |
| 主题图片 | `load_theme_image()`/`theme_card_image()`/`theme_log_image()` | `ui/theme_assets.py` | 缺失返回 None |
| 立绘 | `render_character()`/`left_fade_mask()` | `ui/character_art.py` | 不改源图 |
| 关闭确认 | `CloseChoiceDialog`/`show_close_choice()` | `ui/dialogs.py` | 记住选择/托盘降级 |
| 路径选择 | `select_luker_path()`/`ensure_luker_path_configured()` | `ui/dialogs.py` | 自动识别 |

### 4.6 托盘与基础设施

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 托盘图标/消息循环 | `TrayIcon.run_detached()`/`stop()` | `tray/icon.py` | 消息循环必须在托盘线程 |
| 托盘状态 | `update_status()`/`set_window_visible()` | `tray/icon.py` | 通过消息转交 |
| 托盘菜单 | `TrayMenu` | `tray/menu.py` | 键盘/焦点/无激活 |
| Win32 声明 | `infrastructure/win32.py` | 集中声明 | 新增调用先声明 |
| 文件日志 | `setup_logging()`/`add_ui_log_sink()` | `infrastructure/logging_setup.py` | 不可写回退 `%TEMP%` |
| 全局异常 | `sys.excepthook`/`threading.excepthook` | `infrastructure/logging_setup.py` | 已安装，不要覆盖 |

### 4.7 测试工具

| 需要什么 | 现成实现 | 位置 | 注意 |
|---|---|---|---|
| 架构边界 | `tests/test_architecture.py` | 测试 | 新增包/导入后跑 |
| 批处理行为 | `BuildScriptBehaviorTests`/`CheckScriptBehaviorTests` | `tests/test_packaging.py` | Windows-only/临时目录 |
| 应用组合 | `tests/test_application_launcher_composition.py` | 测试 | 构造期回调/接线 |
| UI 特征 | `tests/test_log_window_*.py`/`test_settings_window.py` | 测试 | fake 控件 |
| 本地冒烟 | `.zcode/smoke_*.py` | 本地未跟踪 | 不要当生产代码 |
| 假 Luker | `.zcode/build/dummy-luker/` | 本地未跟踪 | 临时 E2E |

---

## 5. 历史经验库（LSN）

> 新教训追加 `LSN-24` 及以后；不要删除旧条目。

| ID | 现象 | 根因 | 修复/现状 | 提交 |
|---|---|---|---|---|
| LSN-01 | 日志时间戳错乱、清空后旧日志复现、GCL 日志饥饿 | 日志读取/队列/清空没有统一所有权 | `LogStore`+`BoundedLogQueue`+`LogController`；清空同时丢队列 | `4c91e77`、`60b7690` |
| LSN-02 | 启停 Luker 时界面卡住 | 主线程同步 `Popen/stop` | 后台线程 + `TaskRunner` | `6d2e987` |
| LSN-03 | 主题切换后旧回调操作已销毁控件 | 回调注册/注销不完整 | `add/remove_*_callback` + 销毁移除 | `b412050` |
| LSN-04 | 托盘/进程线程直接操作 Tk 随机崩溃 | Tk 非线程安全 | `UiDispatcher` | `c7ff0b6` |
| LSN-05 | 托盘图标消失/重复/残影 | HICON 生命周期/Explorer 重启/消息循环 | 新图标生效再释放旧；`TaskbarCreated`；stop 兜底 | `c7ff0b6`、`3260c48` |
| LSN-06 | 64 位 Windows 句柄偶发异常 | ctypes 未声明 restype，按 C int 截断 | `infrastructure/win32.py` 集中声明 | `b3a7066`、`77b9a75` |
| LSN-07 | 启动器强杀后 node 占端口 | 无 Job Object 兜底 | `KILL_ON_JOB_CLOSE` | `6f2258d` |
| LSN-08 | 150% 下立绘过大/裁切 | 物理 `winfo_*` 传给逻辑 `CTkImage(size)` | 除以 `_get_widget_scaling()`；缓存含 scale | `16dbd3f` |
| LSN-09 | 长时间运行内存上涨 | 日志队列/存储无上限 | 条数+字节上限；搜索结果上限 | `a8f9b5e` |
| LSN-10 | 打开日志窗口卡顿 | 一次性插入全部历史 | 200 条/批、1ms 让出 | `f93b14f` |
| LSN-11 | 实时日志到达搜索跳回第一条 | 每次全量重跑并重置当前项 | 250ms 合并；保留结果/视口 | `8f3f84b` |
| LSN-12 | 关闭设置窗口后其他滚动区滚轮失效 | CTkScrollableFrame `bind_all` 不解绑 | `clear_scroll_bindings()` + 单设置窗口不变量 | `994ce62` |
| LSN-13 | CTk 升级后开关/文本失效 | 依赖 `_canvas`/`_draw_engine`/`_textbox` | `CtkSwitchAdapter` + 版本锁 | `5a41744` |
| LSN-14 | 副屏在左/上时窗口跑到另一端 | Tk 把 `-100` 当距右/下偏移 | `format_geometry()` 输出 `+-100` | `fe149c4` |
| LSN-15 | 标题栏空白不能拖动 | Tk 事件不冒泡 | `bind_window_drag()` 绑所有子控件 | 早期版本 |
| LSN-16 | `check.bat` 门禁失败却继续/静默中断 | `.bat` 包装器不返回 | 全部 `call python ...` + 失败传播测试 | `3966429` |
| LSN-17 | 更新提交号可能被 git 当选项 | 短 SHA/任意字符串拼命令 | 只接受完整 40 位 SHA | `7e50e68` |
| LSN-18 | npm 安装环境与 Start.bat 不一致 | 少 `NODE_ENV=production` | 只给 npm 安装补，不改 node 运行 | `79e2a78` |
| LSN-19 | 主题卡片悬停残影 | 快速进出/滚轮/Leave 指针校准复杂 | 回滚放大，只颜色过渡 | `b6ce9f5`、`e9bc44f` |
| LSN-20 | 退出线程失败残留 Luker | 失败分支没 `stop_all()` | 主线程同步 stop + finally 退出 | `707dd44` |
| LSN-21 | 组合根构造期回调访问未初始化 `_status` | lambda 延迟绑定/构造顺序 | `getattr(...,None)` + 测试 | `3ad154f` |
| LSN-22 | 打包后图片缺失但测试通过 | 只查 spec 文本/源文件 | 解析 datas 目标目录断言 | `3966429` |
| LSN-23 | 座右铭/字体/立绘反复 | 产品视觉迭代 | 最终移除座右铭；保留左渐隐/320 面板 | `a512226`…`a7a1c68` |

---

## 6. 开放问题与技术债

| ID | 优先级 | 事项 | 证据 | 建议 | 状态 |
|---|---|---|---|---|---|
| OPEN-01 | P3/发布 | `APP_VERSION` 仍 4.0，HEAD 未构建 | `config.py:25`、`version_info.txt` | 发布前 bump 4.1 + 构建 + 验证；先问用户 | 未开始 |
| OPEN-02 | P3/验证 | 真实 125%/150% 未验收 | 只有模拟截图 | 真实设备跑 §8.4 | 未开始 |
| OPEN-03 | P3/打包 | 完整 PyInstaller 构建不在门禁 | `tests/test_packaging.py` 只静态/批处理 | 发布前 `build.bat` + 启动检查 | 未开始 |
| OPEN-04 | P3/更新 | 真实 npm 更新未验证 | 单测 fake Popen | 一次性 Luker 副本验证 | 未开始 |
| OPEN-05 | P3 | `resizing.py` 可缩放分支是死代码 | 生产只 `log_window.py:242` `resizable=False` | 确认后删除或加注释 | 待产品确认 |
| OPEN-06 | P3 | 设置窗口与 `WindowResizer` 重复跨屏逻辑 | `settings_window.py:329-350` / `resizing.py:119-159` | 抽 `refit_window_to_monitor()` | 未开始 |
| OPEN-07 | P3 | `clear_scroll_bindings` 清全局绑定 | `settings_window.py:110-119` | 保留单设置窗口不变量；CTk 升级后实例级解绑 | 已知风险 |
| OPEN-08 | P3 | `_ThemeCardHighlight` 自建动画状态机 | `settings_window.py:153-215`；已有 `StepTicker` | 下次改动画时复用 | 未开始 |
| OPEN-09 | P3 | `settings_window.py` 1369 行、`log_window.py` 1294 行 | 文件规模 | 只在下次必然修改时小步提取 | 未开始 |
| OPEN-10 | P3 | `LogWindow._get_textbox()` 访问 CTk 私有 | `log_window.py:1126-1128` | 保持版本锁；新增私有访问放适配层 | 已接受 |
| OPEN-11 | P3 | 托盘 `stop()` 极端失败路径 | `tray/icon.py:604-624` | 记录日志；实机极端验证 | 已接受 |
| OPEN-12 | 产品 | 当前主题只用 accent 边框 | `settings_window.py:742-748` | 需要时加小徽标；不是 bug | 取舍 |
| OPEN-13 | 合规 | DeepSeek 素材/名称授权 | `assets/deepseek/*` | 用户确认 | 待确认 |

**已关闭，不要重复做**：退出失败 `707dd44`；DPI `16dbd3f`；打包/门禁测试 `3966429`；立绘任务取消 `d484c4a`；`_theme_cards` `6a1f2fb`；异常收窄 `0e6f34a`；组合根 `3ad154f`；悬停回滚 `e9bc44f`；GCL 移除 `b840bf1`；座右铭移除 `a7a1c68`。

---

## 7. 待办与下一步（可领取）

> 领取时状态改 `进行中`，在 §0.2 记 HEAD；完成后改 `已完成` 并追加 §10 日志。

| ID | 优先级 | 任务 | 验收标准 | 依赖 | 状态 |
|---|---|---|---|---|---|
| TODO-01 | P1/发布 | 发布验证 4.1 | bump + `build.bat` + 100/125/150% 主题/立绘/日志/设置正常 + 资源可读 | 用户确认发布 | 待确认 |
| TODO-02 | P2/验证 | 真实高 DPI 验收 | 真实 125/150% 设备跑 §8.4；记录截图/尺寸 | 设备 | 待开始 |
| TODO-03 | P2/打包 | 完整 exe 构建冒烟 | `build.bat` 0；`_MEIPASS` 资源存在；启动无资源告警 | PyInstaller | 待开始 |
| TODO-04 | P2/更新 | 真实 npm 更新 | 一次性副本；成功/失败回滚/依赖恢复；不动主安装 | 用户授权副本 | 待开始 |
| TODO-05 | P3/决策 | 固定日志窗口最终决策 | 用户确认；若否删除 `resizable=True` 分支及测试 | 产品确认 | 待确认 |
| TODO-06 | P3/重构 | 抽 `refit_window_to_monitor()` | 两窗口共用；行为不变；补测试 | 无 | 待开始 |
| TODO-07 | P3/加固 | 滚动绑定实例级解绑 | 关闭设置窗口不影响其他滚动区；补测试 | CTk 方案 | 待开始 |
| TODO-08 | P3/重构 | 复用 `StepTicker` 统一悬停动画 | 颜色过渡不变；少一套状态机 | 无 | 待开始 |
| TODO-09 | P3/拆分 | 大 UI 文件按需小步提取 | 只在必然修改时做；行为不变；先补测试 | 实际需求 | 待开始 |

---

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
| `test_architecture.py` | 13 | 依赖方向/根目录/import cycle |
| 其余 | — | 日志存储/显示、进程、托盘键盘、主题、Win32 API |

> 总计 **758**。`test_architecture.py` 不是可选检查。

### 8.2 门禁命令

```bat
check.bat
```

五道：`ruff format --check` → `ruff check` → `mypy` → `coverage run -m unittest discover -s tests -q` → `coverage report`（门槛 65%）。每道都用 `call python ...`；失败 `goto fail`，输出 `Check failed.`，返回非零。

`build.bat`：`call pyinstaller launcher.spec --noconfirm --distpath .`；失败不清理 `build/`、不打印 `Done!`、返回非零。

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

---

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

未知键/错误类型丢弃；字符串去空白；theme/close_behavior 白名单。

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

### 9.4 事实来源

- `README.md`、`pyproject.toml`、`check.bat`、`build.bat`、`launcher.spec`、`version_info.txt`。
- `docs/development-handbook.md`：本文件，当前事实与决策。
- `docs/archive/`：`00` 详细手册快照；`01`–`04` 版本段历史日志。
- 本地工作记录（`.zcode/reports/`，不随仓库分发）：`review-2026-11-09.md`、`review-fixes-2026-11-09.md`、`implementation-2026-11-05.md`、`launcher-refactor-and-package-plan-2026-11-05.md`、`ai-gijika-deepseek-2026-11-08.md`、`ai-gijika-polish-2026-11-09.md`；其结论已并入本手册/归档。
- Git：193 提交、17 标签、`git log --stat`、`git diff`、`git show`。

---

## 10. 开发日志（只追加）

> 按时间正序，最新在文件末尾。新条目追加到 §10 最后，不要插入中间。下一条 ID 见 §0.2。
> 历史细节已压缩；完整回填按版本段存放：v1.0–v2.0 → `docs/archive/01-...`，v2.1–v3.3 → `02-...`，v3.4–v3.5 → `03-...`，v4.0+ → `04-...`。索引见 `docs/archive/README.md`。
>
> **迁移说明（2026-11-14）**：本文件原位于 `.zcode/reports/development-history-2026-11-14.md`，现迁至 `docs/development-handbook.md` 并纳入 Git。旧条目中出现的 `.zcode/reports/...` 路径是历史记录，正文保持原样；对应详细内容现在 `docs/archive/`。旧条目中“未提交 / 被忽略”的表述也只反映当时状态。

### 10.1 提交覆盖图

| 版本段 | 提交范围（含端点） | 数量 | 日志条目 | 分册 |
|---|---|---:|---|---|
| v1.0 | `cb75d8b` | 1 | DEV-20261002-01 | 01 |
| v1.0 → v1.1 | `206c1d1..38be292` | 10 | DEV-20261002-02、DEV-20261018-01 | 01 |
| v1.1 → v1.2 | `6343f3e..5cfb3b3` | 6 | DEV-20261018-02 | 01 |
| v1.2 → v2.0 | `4c32010..4e98b09` | 10 | DEV-20261018-03 | 01 |
| v2.0 → v2.1 | `71a73e3..c224c69` | 7 | DEV-20261019-01 | 02 |
| v2.1 → v2.2 | `34f95d2..34d01e3` | 6 | DEV-20261019-02 | 02 |
| v2.2 → v2.3 | `b5993f0..aad0cad` | 10 | DEV-20261020-01 | 02 |
| v2.3 → v2.4 | `b69d47d..3729554` | 17 | DEV-20261021-01 | 02 |
| v2.4 → v3.0 | `24f9db0..b480684` | 20 | DEV-20261022-01 | 02 |
| v3.0 → v3.1 | `fe149c4..c778e3b` | 20 | DEV-20261024-01 | 02 |
| v3.1 → v3.2 | `43476f0..523764c` | 14 | DEV-20261025-01 | 02 |
| v3.2 → v3.3 | `3260c48..5f9e402` | 9 | DEV-20261030-01 | 02 |
| v3.3 → v3.4 | `2b9ebdb..16e97be` | 8 | DEV-20261102-01 | 03 |
| v3.4 → v3.4.1 | `ca08bb9` | 1 | DEV-20261103-01 | 03 |
| v3.4.1 → v3.5 | `5f95490..ec0b561` | 16 | DEV-20261103-02 | 03 |
| v3.5 → v4.0 | `547160a..a66f873` | 18 | DEV-20261105-01 | 04 |
| v4.0 → HEAD | `fc06d38`, `64f1a06..a7a1c68` | 20 | DEV-20261108-01 … DEV-20261110-01 | 04 |

> 合计 193。回填条目根据 Git/提交信息/测试/本地报告整理；无法证明的已标 `[待确认]`。
> `DEV-20261114-01` 起为文档维护条目，不对应产品代码提交。

### 10.2 历史条目摘要

| ID | 日期 | 提交/范围 | 类型 | 状态 | 摘要 | 关键验证 |
|---|---|---|---|---|---|---|
| DEV-20261002-01 | 2026-10-02 | `cb75d8b` | feat | 已发布 | v1.0 原型导入；14 文件/3733 行；托盘/日志/进程/PWA/GCL/6 主题 | 初始提交统计 |
| DEV-20261002-02 | 2026-10-02 | `206c1d1` | chore | 已完成 | 清理死代码/裸 except；新增配置模板 | 6 files/10+/13- |
| DEV-20261018-01 | 2026-10-18 | `206c1d1..38be292` | fix | 已发布 | v1.1：日志/GCL/进程/PWA/托盘修复；注释/README | 10 commits |
| DEV-20261018-02 | 2026-10-18 | `6343f3e..5cfb3b3` | perf | 已发布 | v1.2：日志/UI 资源优化、自动路径、清空队列 | 6 commits |
| DEV-20261018-03 | 2026-10-18 | `4c32010..4e98b09` | refactor | 已发布 | v2.0：合并进程管理器、拆日志/主题/配置、UI 队列、单实例/Job Object、文件日志、首批测试 | 10 commits；首批测试出现 |
| DEV-20261019-01 | 2026-10-19 | `71a73e3..c224c69` | chore | 已发布 | v2.1：ruff/CI/LICENSE、托盘菜单/设置拆分、类型注解 | 7 commits |
| DEV-20261019-02 | 2026-10-19 | `34f95d2..34d01e3` | fix | 已发布 | v2.2：高 DPI 跨屏、托盘/进程生命周期 | 6 commits |
| DEV-20261020-01 | 2026-10-20 | `b5993f0..aad0cad` | fix | 已发布 | v2.3：GCL/PWA 竞态、APPX 校验、日志窗口最小尺寸、队列/重放上限 | 10 commits |
| DEV-20261021-01 | 2026-10-21 | `b69d47d..3729554` | refactor | 已发布 | v2.4：日志队列/搜索/显示/重放拆分、窗口缩放、UI 调度器、覆盖率门禁 | 17 commits |
| DEV-20261022-01 | 2026-10-22 | `24f9db0..b480684` | feat | 已发布 | v3.0：主题/毛玻璃/圆角/按钮/呼吸 logo/关闭确认/托盘图标 | 20 commits；UI 测试扩展 |
| DEV-20261024-01 | 2026-10-24 | `fe149c4..c778e3b` | refactor | 已发布 | v3.1：应用主体拆分、日志/搜索拆分、目录分包 | 20 commits |
| DEV-20261025-01 | 2026-10-25 | `43476f0..523764c` | feat | 已发布 | v3.2：关闭行为记忆、版本检查/更新、设置页、本地门禁 | 14 commits |
| DEV-20261030-01 | 2026-10-30 | `3260c48..5f9e402` | fix | 已发布 | v3.3：托盘句柄、配置边界、构建失败、npm 生产环境、Job/单实例测试 | 9 commits |
| DEV-20261102-01 | 2026-11-02 | `2b9ebdb..16e97be` | refactor | 已发布 | v3.4：设计令牌、窗口淡入、日志状态、托盘键盘、**移除 GCL** | 8 commits；b840bf1 -1079 行 |
| DEV-20261103-01 | 2026-11-03 | `ca08bb9` | release | 已发布 | v3.4.1 版本补丁 | 1 commit |
| DEV-20261103-02 | 2026-11-03 | `5f95490..ec0b561` | fix | 已发布 | v3.5：雾灰毛玻璃、图标/字体、配置 BOM、Win32 声明、CTk 适配层 | 16 commits |
| DEV-20261105-01 | 2026-11-05 | `547160a..a66f873` | refactor | 已发布 | v4.0：Coordinator + 单一包 + 架构测试 | 715 tests/74%；build 成功 |
| DEV-20261108-01 | 2026-11-08 | `64f1a06..9834b5e` | feat | 已完成 | DeepSeek 主题/卡片/日志立绘 | 726 tests/74%；exe 20,774,565 |
| DEV-20261109-01 | 2026-11-09 | `2d6acda..00dec31` | feat | 已完成 | 图片重做、主题卡片、固定日志窗口/立绘/座右铭 | 745 tests/74%；exe 21,084,062 |
| DEV-20261109-02 | 2026-11-09 | `707dd44..3ad154f` | fix | 已完成 | P2 退出/DPI 修复；打包/门禁测试；低风险清理 | 756 tests/74%；DPI 100/125/150 模拟 |
| DEV-20261109-03 | 2026-11-09 | `e9bc44f..7af004a` | fix | 部分废弃 | 回滚悬停放大、加宽面板/左渐隐、座右铭浮层/一行 | 中间点未单独记录 |
| DEV-20261110-01 | 2026-11-10 | `157f22a..a7a1c68` | feat | 已完成 | 方案 A 布局；移除座右铭；滚动条最右 | 当前 758 tests/74% |
| DEV-20261114-01 | 2026-11-14 | 未提交 | docs | 已完成 | 历史文档重构为可持续日志 | 结构/表格/gitignore 校验 |
| DEV-20261114-02 | 2026-11-14 | 未提交 | docs | 已完成 | 精简主文档；完整细节归档 | 结构/表格校验 |
| DEV-20261114-03 | 2026-11-14 | 随本次 docs 提交 | docs | 已完成 | 文档迁入 docs；归档拆分 00–04；明确唯一写入目标 | 8 文件/23 条目/链接与 check.bat |

### 10.3 最近详细条目

#### DEV-20261109-02 | 审查 P2 修复与测试补强

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-09 |
| 分支 | ai-gijika |
| 提交 | `707dd44`、`16dbd3f`、`3966429`、`d484c4a`、`6a1f2fb`、`0e6f34a`、`3ad154f` |
| 类型 | fix / test / refactor |
| 状态 | 已完成（未发布） |
| 关联 | OPEN-01/02/03、LSN-08/16/20/21/22、ADR-03/05 |

**改动**

- 退出线程失败：主线程同步 `process.stop_all()`，`finally` 退出；测试断言 `stop_all_calls == 1`。
- DPI：`widget_scaling()`；`winfo_*` 除以缩放；缓存键含 scale；补 125%/150% 测试。
- 打包/门禁：`datas` 目标目录断言；`check.bat` 失败传播测试；五道门禁改 `call python`；主题资源测试改容差。
- 清理：取消 `_character_fit_job`；删除 `_theme_cards`；异常收窄；组合根空值保护。

**验证**

- `check.bat` 通过；修复记录称 756 tests / 74%；ruff/mypy 通过。
- DPI 150% 修复前 `(388,517)`，修复后 `(256,341)`；100/125/150% 模拟视觉通过。
- `check.bat` 失败测试暴露 `.bat` 包装器不返回的真实问题，已用 `call` 修复。

**遗留**

- 真实 125/150% 设备、发布 bump/构建（OPEN-01/02/03）。

#### DEV-20261110-01 | 最终立绘布局

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-10 |
| 分支 | ai-gijika |
| 提交 | `157f22a`、`a7a1c68`（当前 HEAD） |
| 类型 | feat / refactor |
| 状态 | 已完成（未发布） |
| 关联 | ADR-09/11、LSN-23 |

**改动**

- 合并“方案 A”的立绘布局。
- 移除座右铭：`theme.py`/`character_art.py`/`log_window.py`/`tokens.py`/`window_utils.py` 及测试。
- 滚动条独立到 `body` 第 2 列，最右侧。
- 最终：固定 960×640；文本区 + 320 角色面板 + 最右滚动条；DeepSeek 显示立绘；无座右铭；左侧 16% alpha 渐隐。

**验证**

- 当前 `python -m unittest discover -s tests -q`：758 项通过。
- 覆盖率 74%；ruff format/check、mypy 通过；工作区 clean；`a7a1c68` 与 `origin/ai-gijika` 同步。
- 未验证：真实 125/150% 设备；HEAD 未构建 exe。

**遗留**

- TODO-01/02/03；未 bump、未推送、未打标签、未发布。

#### DEV-20261114-01 | 开发历史文档重构为可持续日志

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 未提交（`.zcode/` 被忽略） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | §0、§5-§10 |

**改动**

- 重构为“稳定知识（§1-§4）+ 经验库（§5）+ 开放问题/待办（§6-§7）+ 验证（§8）+ 附录（§9）+ 只追加日志（§10）”。
- 增加控制表、事实等级、状态/类型词表、日志模板、提交覆盖图、交接检查表。
- 修正 v1.2/v2.0 提交区间：v1.2 是资源优化；v2.0 才是进程管理器合并/拆分/UI 队列/单实例/文件日志/首批测试。

**验证**

- `git check-ignore` 命中 `.gitignore:15:.zcode/`；`git status` 干净；758/74% 基线不变；Markdown 表格/围栏检查通过。

**遗留**

- 文档较长，需要精简（由下一条处理）。

#### DEV-20261114-02 | 精简主文档并保留完整历史归档

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 未提交（`.zcode/` 被忽略） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | §0、§10、`development-history-full-2026-11-14.md` |

**目标/背景**

- 1,874 行/98 KB 对下一个 Agent 过重；稳定知识与逐阶段长日志混在一起，不利于快速接手。

**改动**

- 主文档精简为“基线/架构/ADR 表/组件目录/经验库/开放问题/待办/验证/只追加日志”。
- 历史日志压缩为摘要表；关键条目（`DEV-20261109-02`、`DEV-20261110-01`、`DEV-20261114-01`、本条目）保留详细字段；完整回填细节移到 `development-history-full-2026-11-14.md`。
- 更新文档控制表、修订记录、交接摘要、最小必读路径。

**验证**

- Markdown 表格列数/代码围栏检查通过；`.zcode/` 仍被忽略；工作区 clean；未修改生产代码/测试。
- 当前基线仍为 758 tests / 74% / `check.bat` pass。

**决策/风险**

- 主文档保持可读；历史细节不丢，归档只读参考。
- 后续新任务仍按 §0.6 模板追加到主文档末尾，不回填归档。

**遗留/下一步**

- 下一个 Agent 从 `DEV-20261114-03` 开始。
- 发布验证、真实 DPI、完整构建仍是 OPEN-01/02/03 与 TODO-01/02/03。

#### DEV-20261114-03 | 文档迁入 docs 并按版本拆分历史归档

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/development-handbook.md`） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | §0、§9.4、§10 |
| 证据等级 | [已验证] |

**目标/背景**

- 原文档在 `.zcode/` 下被 gitignore，无法随仓库交接；完整归档 98 KB 对 Agent 过重。
- 需要明确“唯一写入目标”，避免多个文档并存导致记录分散。

**改动**

- 新增 `docs/README.md`：文档入口、阅读路径、权威顺序。
- 主文档迁至 `docs/development-handbook.md`，结构版本 4.0；更新 §0.2/§0.5/§0.7/§0.8/§0.9/§9.4。
- 完整归档拆分：`docs/archive/00-detailed-handbook-2026-11-14.md`（§0–§9 快照）+ `01`–`04` 版本分册（23 条 DEV 条目）。
- 新增 `docs/archive/README.md`：分册导航、回填说明、快照边界、维护规则。
- 根 `README.md` 增加“开发文档”入口。
- 删除 `.zcode/reports/` 下两份旧历史文档，避免双源；其余本地报告保留。

**验证**

- `git ls-files docs`：8 个文件；`docs/` 未被 `.gitignore` 命中。
- 归档分册 `### DEV-` 条目合计 23，ID 与原归档一致；正文抽样比对无丢失。
- 相对链接可解析；主手册无新增失效的归档路径（旧日志条目已加迁移说明）。
- Markdown 代码围栏成对、表格列数一致。
- `check.bat` 通过；docs-only，代码基线仍 758 tests / 74%。
- 提交作者 `Yaoyao <jiayinyao24@outlook.com>`，GPG `G`；未推送。

**决策/风险**

- 主手册是唯一日常读写目标；归档只读。理由：当前事实集中、上下文成本低、归档不会污染日常记忆。
- 按版本段而非主题拆分：历史天然按时间演进，版本边界清晰，避免跨主题重复和“该写哪一份”的歧义。
- 归档 `00` 是冻结快照，可能与当前代码不一致；权威顺序已写入 `docs/README.md`。

**遗留/下一步**

- 下一个 Agent 从 `DEV-20261114-04` 开始；日常只改主手册。
- §10 超过 30 条或主版本结束时，按 §0.5 轮转规则新增 `05+` 分册。
- 发布/DPI/构建仍是 OPEN-01/02/03、TODO-01/02/03。

---

> 下一条日志 ID：`DEV-20261114-04`。追加后请更新 §0.2 控制表、§6/§7 状态，并在 §0.9 加一行文档修订记录。

<!-- ===== 新开发日志追加点：请在本行之后追加下一条 DEV 记录（复制 §0.6 模板） ===== -->
