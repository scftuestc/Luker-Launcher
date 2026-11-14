# Luker Launcher 开发手册与持续开发日志

> **文档类型**：可持续维护的开发手册 + 只追加日志（Living Document）
> **文档编号**：`LH-LUKER-001`
> **结构版本**：`4.0`
> **文档位置**：`docs/development-handbook.md`（Git 跟踪；唯一日常写入目标）
> **事实截止**：`2026-11-14`
> **代码分支 / 最后代码提交**：`ai-gijika` / `f3ffd54`（文档提交见 `git log -- docs/development-handbook.md`）
> **当前版本**：`APP_VERSION = 4.0`（HEAD 未 bump，未重新发布）
> **质量基线**：772 tests / 75% / `check.bat` pass
> **完整历史归档**：`docs/archive/README.md`（00–04 分册，只读）
> **维护方式**：每个任务结束后，在 **§10 末尾追加** 一条 `DEV-YYYYMMDD-NN`，更新 §0.2、§6、§7，并随任务提交。

---

<a id="handoff"></a>
## 交接摘要（每次交接更新）

- **当前状态**：`ai-gijika`（最后代码提交 `f3ffd54`；文档提交见 `git log`）；`origin/ai-gijika` 落后本地、未推送；工作区 clean；772 tests / 75% / `check.bat` pass。
- **最近完成**：DeepSeek 主题、角色立绘、固定日志窗口、两个 P2 修复、审查整改、最终移除座右铭并把滚动条移到最右；清除已合并的 `dev` 分支（本地+远程）。
- **当前阻塞**：`APP_VERSION` 仍为 4.0；HEAD 未 bump、未构建 exe、未在真实 125%/150% 设备验收；是否发布需用户确认。
- **建议下一步**：先确认是否发布；若发布，按 `TODO-01` 做版本 bump + 构建 + 100%/125%/150% 验收。不要先做大重构。
- **不要重复**：不要重新引入 GCL；不要恢复主题卡片悬停放大；不要加回座右铭；不要未经确认恢复日志窗口拖拽缩放；不要改 npm 参数；不要重建已删除的 `dev` 分支。
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

**Quick facts**：工作分支 `ai-gijika`；最后代码提交 `f3ffd54`；193 基线产品提交 + 本轮 3 代码修复 + 文档提交（见 `git log`）；17 本地标签（16 远程）；772 tests / 75%；`APP_VERSION = 4.0`。

**目录**：[交接摘要](#handoff) · [§0 规范](#sec-0) · [§1 基线](#sec-1) · [§2 架构](#sec-2) · [§3 ADR](#sec-3) · [§4 组件](#sec-4) · [§5 经验](#sec-5) · [§6 风险](#sec-6) · [§7 待办](#sec-7) · [§8 测试](#sec-8) · [§9 附录](#sec-9) · [§10 日志](#sec-10)

---

<a id="sec-0"></a>
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
| 最新日志条目 | `DEV-20261114-10` | 每次追加日志 |
| 下一条日志 ID | `DEV-20261114-11` | 每次追加日志 |
| 代码分支 / 最后代码提交 | `ai-gijika` / `f3ffd54` | 每次任务开始/结束 |
| 产品 / 文档提交 | 193 基线产品 + 3 代码修复 + 文档提交（见 `git log`） | 每次任务结束 |
| 标签 | 17 本地 / 16 远程；`v3.5` 仅本地 | 发布/标签变化时 |
| 当前版本 | `APP_VERSION = 4.0` | 版本 bump 时 |
| 工作区状态 | clean（`docs/` 已跟踪；文档改动随任务提交） | 每次任务结束 |
| 质量基线 | 772 tests / 75% / check.bat pass | 每次任务结束 |
| 完整历史归档 | `docs/archive/README.md`（只读，00–04 分册） | 不再更新（只读参考） |

**ID registry**：

| 前缀 | 含义 | 位置 | 下一个 | 分配规则 |
|---|---|---|---|---|
| `DEV-YYYYMMDD-NN` | 开发日志 | §10 | `DEV-20261114-11` | 当天从 01 开始，跨天重置；写前先更新本表 |
| `ADR-NN` | 设计决策 | §3 | `ADR-16` | 追加，不重排；被取代时新增并标注 |
| `LSN-NN` | 经验教训 | §5 | `LSN-24` | 追加，不删除旧条目 |
| `OPEN-NN` | 未排期风险/技术债 | §6 | `OPEN-14` | 追加；排期后写 `tracked as TODO-xx` |
| `TODO-NN` | 行动队列 | §7 | `TODO-10` | 追加；领取时状态改 `进行中` |

> 先在本表领取 ID，再写正文；不要跳号、复用或并发抢号。

### 0.3 证据等级与写作规则

| 标签 | 含义 | 例子 |
|---|---|---|
| `[已验证]` | 代码、测试、命令或 Git 历史可直接证明 | `git rev-list --count v1.0..v1.1` = 10 |
| `[推断]` | 根据提交信息/代码结构推断，未单独实验 | “可能是为了避免重复开浏览器” |
| `[待验证]` | 代码/测试已完成，但缺少实机或真实环境验证 | “单测通过，真实 125% 设备未跑” |
| `[待确认]` | 需要用户/产品/实机确认 | “是否发布需用户确认” |

写作规则：

- 日期 `YYYY-MM-DD`；提交用 7 位短哈希；文件引用 `path:line`。
- 不粘贴大段命令输出；只写“命令 + 关键结果”。
- 不写“优化了代码”这种空话；必须写**改了什么行为、哪个文件、哪个测试**。
- 未验证的内容标 `[待验证]`/`[待确认]`，不要写成已完成。
- 旧日志不修改；发现错误在 §0.9 加“勘误”，并引用旧条目。
- 决策被推翻时，不删除旧 ADR；新增 ADR 并标注“取代 ADR-xx”。

### 0.4 状态、类型、优先级

**状态**：

| 状态 | 含义 |
|---|---|
| `待开始` | 已登记，未动工 |
| `进行中` | 正在做，可能有未提交改动 |
| `待验证` | 代码/测试完成，等待实机或真实环境验证 |
| `待确认` | 需要用户/产品确认后才能继续 |
| `已完成` | 代码、测试、必要验证完成；未发布 |
| `已发布` | 已进入 tag/release |
| `已回滚` | 做过但被撤回；保留原因 |
| `部分废弃` | 部分内容被后续决策取代；保留有效部分 |
| `已废弃` | 不再维护；保留历史 |
| `阻塞` | 等用户/外部条件 |

**类型**：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`perf`、`release`、`revert`。

**缺陷严重度**：`P0` 立即；`P1` 发布前必须；`P2` 发布前应修；`P3` 维护性/可延后。

**工作优先级**：与缺陷严重度分开写；`P1` 发布前必须、`P2` 发布前应修、`P3` 可延后。不要用 `P3/发布` 这类混写。

**处置**：`已接受`、`已知风险`、`取舍` 是处置结果，不是状态；放在 §6 的“处置”列。

### 0.5 每次任务后的追加流程（必须执行）

1. **确定 ID**：`DEV-YYYYMMDD-NN`；当天下一条见 §0.2。
2. **在 §10 末尾追加**：复制 §0.6 模板；不要插入旧条目中间，不要重排历史。
3. **填完整**：目标、改动、验证、决策/风险、遗留/下一步。验证必须写命令和结果。
4. **更新 §0.2**：最后更新、最新条目、下一条 ID、最后代码提交（文档提交见 `git log`）、质量基线。
5. **更新 §6/§7**：§7 是唯一行动队列；关闭/新增开放问题，更新 TODO 状态。
6. **架构/决策/组件变了**：更新 §2/§3/§4，并在 §0.9 加一行修订记录。
7. **随任务提交本文件**：本文件在 `docs/` 下，必须随任务提交；提交作者/签名遵循仓库约束（仅 Yaoyao、GPG 签名、无 AI 署名）。不要复制回 `.zcode/`。
8. **更新顶部“交接摘要”**：状态/阻塞/下一步变了就同步。
9. **交接时**：填写 §0.8 检查表；在 §10 最后一条写“交接点”。

**写入契约**：日常只改主手册：§10 追加 + §0.2/§6/§7；§1–§5 仅在事实/决策/组件变化时改；归档不改，勘误写 §0.9。

**任务路由**：

| 你新增/修改了什么 | 写到哪里 |
|---|---|
| 新教训/回归 | §5 `LSN` |
| 新设计决策 | §3 `ADR` |
| 新组件/工具 | §4 |
| 新风险/技术债 | §6 `OPEN` |
| 可执行任务 | §7 `TODO` |
| 新测试规则 | §8 |
| 任务完成 | §10 `DEV` + §0.2/§6/§7 |

**归档轮转**：当 §10 未归档的详细条目超过 30 条或一个主版本结束时，把较早条目的详细内容迁到 `docs/archive/05-...`，§10 只保留摘要和链接；不要删除历史。

### 0.6 开发日志条目模板（可直接复制）

```markdown
#### DEV-YYYYMMDD-NN | 一句话标题

| 字段 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| 分支 | ai-gijika |
| 提交 | abc1234（未提交则写“未提交”） |
| 类型 | feat / fix / refactor / test / docs / chore / release |
| 状态 | 待开始 / 进行中 / 待验证 / 待确认 / 已完成 / 已发布 / 已回滚 / 部分废弃 / 已废弃 / 阻塞 |
| 关联 | ADR-xx / OPEN-xx / TODO-xx |
| 证据等级 | [已验证] / [推断] / [待验证] / [待确认] |

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

> 小改动可压缩为 6~10 行，但“日期 / 提交 / 类型 / 状态 / 改动 / 验证 / 遗留”不能缺。状态/证据必须用 §0.4/§0.3 的值；`提交` 写代码提交或 docs 提交，未知时写“未提交”。

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

**文件地图**：见 [`docs/README.md`](README.md) 的“目录”；本手册只保留章节地图。

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

**勘误**（只追加，不改旧日志正文）：

| 日期 | 影响条目 | 原内容 | 更正 |
|---|---|---|---|
| 2026-11-14 | §1.5 `v1.1` | `206c1d1..38be292` 写 10 个 | 10 是 `v1.0..v1.1` 区间计数；`206c1d1` 之后是 9 个提交，加前一条 `DEV-20261002-02` 才是 10 |
| 2026-11-14 | §1.5 `v2.0` / `v3.5` | 日期分别写 2026-10-19 / 2026-11-03 | 条目跨日：v2.0 为 2026-10-18~19；v3.5 为 2026-11-03~04 |
| 2026-11-14 | §1.6 | `ruff format` 106 个文件 | 最新门禁日志为 114 个文件；以 `check.bat` 实测为准 |
| 2026-11-14 | §1.4 | “17 个标签”未区分本地/远程 | 17 本地 / 16 远程；`v3.5` 仅本地，`v3.5.0` 远程，同提交 `ec0b561` |
| 2026-11-14 | ADR-15 | “v4.0 后 19 提交未 bump” | `v4.0..a7a1c68` 共 20 个产品提交（含 README-only `fc06d38`；其中 19 个 ai-gijika 代码提交） |
| 2026-11-14 | §0.9 / §10.3 | `development-history-full-2026-11-14.md` | 已拆为 `docs/archive/00-...`（§0–§9 快照）+ `01`–`04`（§10 日志） |

---

<a id="sec-1"></a>
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
| `ai-gijika` | `f3ffd54`（最后代码提交；文档提交见 `git log`） | 当前工作分支；`fc06d38` 之后 19 个基线代码提交 + 本轮 3 个代码修复 + 文档提交 |
| `origin/ai-gijika` | `d94308d` | 落后本地、未推送 |
| `v4.0` | `a66f873` | 最新正式标签；GitHub 已发布 |
| `v3.5` / `v3.5.0` | `ec0b561` | 同提交；`v3.5` 仅本地，`v3.5.0` 远程 |

> `ai-gijika` 的代码提交没有 bump 版本，也没有重新发布。根目录现有 exe 是 4.0 时期构建，不代表 HEAD。`main` 不包含这些提交；`dev`（`a512226`）已通过 `157f22a` 合入 `ai-gijika`，并于 2026-11-14 删除本地与远程分支，不丢提交。不要自行 merge/rebase；推送/发布先问用户。

### 1.5 版本坐标（提交范围含端点）

| 版本 | 日期 | 提交范围（Git `A..B`，不含 A） | 数量 | 一句话 |
|---|---|---|---:|---|
| `v1.0` | 2026-10-02 | `cb75d8b` | 1 | 导入原型（14 文件 / 3,733 行） |
| `v1.1` | 2026-10-18 | `v1.0..v1.1` | 10 | 日志/GCL/进程/PWA/托盘第一轮修复 |
| `v1.2` | 2026-10-18 | `v1.1..v1.2` | 6 | 日志/界面资源优化、自动路径、清空队列 |
| `v2.0` | 2026-10-18~19 | `v1.2..v2.0` | 10 | 合并进程管理器、拆日志/主题/配置、UI 队列、单实例/Job Object、文件日志、首批测试 |
| `v2.1` | 2026-10-19 | `v2.0..v2.1` | 7 | ruff/CI/LICENSE、托盘菜单/设置窗口拆分、类型注解 |
| `v2.2` | 2026-10-19 | `v2.1..v2.2` | 6 | 高 DPI 跨屏、托盘/进程生命周期 |
| `v2.3` | 2026-10-20~21 | `v2.2..v2.3` | 10 | GCL/PWA 竞态、APPX 校验、日志窗口最小尺寸、队列/重放上限 |
| `v2.4` | 2026-10-21 | `v2.3..v2.4` | 17 | 日志队列/搜索/显示/重放拆分、窗口缩放、UI 调度器 |
| `v3.0` | 2026-10-22~23 | `v2.4..v3.0` | 20 | 主题/毛玻璃/圆角/按钮/呼吸 logo/关闭确认/托盘图标 |
| `v3.1` | 2026-10-24~25 | `v3.0..v3.1` | 20 | 应用主体拆分、日志/搜索拆分、目录分包 |
| `v3.2` | 2026-10-25~27 | `v3.1..v3.2` | 14 | 关闭行为记忆、版本检查/更新、设置页、本地门禁 |
| `v3.3` | 2026-10-30 | `v3.2..v3.3` | 9 | 托盘句柄、配置边界、构建失败、npm 生产环境 |
| `v3.4` | 2026-11-02 | `v3.3..v3.4` | 8 | 设计令牌、窗口淡入、日志状态、托盘键盘、**移除 GCL** |
| `v3.4.1` | 2026-11-03 | `v3.4..v3.4.1` | 1 | 版本号补丁 |
| `v3.5` | 2026-11-03~04 | `v3.4.1..v3.5` | 16 | 雾灰关闭毛玻璃、图标/字体、配置 BOM、Win32 声明、CTk 适配层 |
| `v4.0` | 2026-11-05 | `v3.5..v4.0` | 18 | **Coordinator 架构 + 单一 `luker_launcher/` 包 + 架构测试** |
| `v4.0+` | 2026-11-05~10 | `v4.0..a7a1c68` | 20 | DeepSeek 主题、立绘、DPI/退出修复、审查整改、布局迭代 |

> 总计 **193** 个已发布基线产品提交；本轮另有 3 个代码修复提交（`c8cf48d`、`c0c96bb`、`f3ffd54`）和文档提交（见 `git log`），均未发布/未推送。`v3.5`/`v3.5.0` 同提交，统计只算一次。

### 1.6 质量基线（2026-11-14 实测）

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests -q` | **772 项通过**，约 2 秒 |
| 覆盖率 | **75%**（门槛 65%） |
| `ruff format --check .` | 118 个文件已格式化 |
| `ruff check .` | 通过 |
| `mypy .` | 56 个源文件无问题 |
| 工作区 | 干净；`docs/` 已跟踪；本地仍有被忽略的 `.coverage`、`.zcode/` 报告、根目录 exe/log |
| 提交签名 | 基线 193 个产品提交中 187 个 `G`；6 个 v1.1–v1.2 时期提交为 `N`（历史事实）；本轮 3 个代码提交 + 文档提交均为 `G` |
| 作者/提交者 | 全部 Yaoyao；无 AI 署名 |

> 6 个未签名提交：`38be292`、`6343f3e`、`9ab1fa9`、`fab4cb8`、`60b7690`、`224c7ba`。之后的提交全部 GPG 签名。

### 1.7 审查结论

- 本轮审查与上一轮全仓库审查均未发现 P0/P1 **缺陷**；工作优先级另见 §7（TODO-01 是 P1 发布任务，不等于存在 P1 缺陷）。
- 上一轮确认并修复 2 个 P2：
  - 退出线程创建失败可能残留 Luker/Node（`707dd44`）；
  - 高 DPI 立绘物理/逻辑尺寸混用（`16dbd3f`）。
- 剩余 P3 见 §6；不影响基本功能，但不要重复踩。

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

<a id="sec-3"></a>
## 3. 关键设计决策（ADR）

> 新决策追加 ADR；旧 ADR 不删除，标注“被 ADR-xx 取代”。详细背景见完整历史归档。

| ADR | 决策 | 原因/后果 | 不要做 | 证据 |
|---|---|---|---|---|
| ADR-01 | 用 `node server.js`，不通过 `Start.bat` | 需要传 `--browserLaunchEnabled false`；停止/日志可控 | 不要改回 `Start.bat` | `process/managers.py:339-345` |
| ADR-02 | Job Object + 单实例 | 防止强杀后 node 占端口；防止双启动器抢端口 | 不要移除 Job Object/只 terminate 父进程 | `process/job.py`、`single_instance.py` |
| ADR-03 | 后台线程统一经 `UiDispatcher` 回主线程 | Tk 非线程安全；完成回调不能丢 | 不要在后台直接碰 Tk/用普通队列投递完成回调；退出 `finish_exit` 也走 `post_control` | `ui/dispatch.py` |
| ADR-04 | 就绪=连续 2 次成功 + READY 粘滞 | 进程活≠服务可用；避免呼吸灯抖动 | 不要每次探测直接 apply | `services/readiness.py` |
| ADR-05 | 配置归一化/原子写入/BOM/端口缓存 | 手改配置、半截写入、每秒读盘 | 不要用 yaml 整体解析只取端口 | `config.py` |
| ADR-06 | 路径切换只在停止时进行 | 运行中热切换会中断/端口冲突 | 不要运行中替换 manager | `process_coordinator.py:56-75` |
| ADR-07 | 更新固定完整 SHA、dirty 检查、可回滚 | 防注入、防意外提交、半更新可恢复；已补 Start.bat 的 `storage:install-sqlite` 条件步骤 | 不要改 npm 参数/短 SHA/给 node 加 NODE_ENV | `services/version.py:734-808` |
| ADR-08 | 移除 GCL | 无端口探测/健康检查/多实例，接受 Luker `Start.bat` 会重复启动 | 不要重新引入 | `b840bf1` |
| ADR-09 | 日志窗口固定尺寸 | 主题/立绘对尺寸敏感；跨屏仍适配 | 不要未经确认恢复拖拽缩放 | `log_window.py:242` |
| ADR-10 | 主题卡片悬停放大已回滚 | 残影修复成本高；现在只颜色过渡 | 不要加回 relwidth/图片放大 | `e9bc44f` |
| ADR-11 | 座右铭已移除 | 视觉迭代最终决策 | 不要加回 | `a7a1c68` |
| ADR-12 | 门禁只在本地 | Windows 托盘/Win32/DPI 需要 Windows 环境；提交只记录“本地执行” | 不要恢复远程 CI 并声称覆盖托盘 | `43476f0` |
| ADR-13 | CTk 私有接口隔离 + 版本锁 | 6.0 已实测；6.1 Text 接口可能变；已接受 `_canvas`/`_draw_engine`、`_get_textbox`、`_get_widget_scaling`、`ScalingTracker.get_window_dpi_scaling`/`window_dpi_scaling_dict`，全部集中在 `ui/ctk_adapter.py` | 不要新增分散的私有访问；集中到适配层 | `ui/ctk_adapter.py` |
| ADR-14 | 主题颜色与元数据分离 | 渐变只处理颜色，避免把 name/icon 当颜色 | 不要整个 `PRESET_THEMES` 传给渐变 | `theme.py:256-262` |
| ADR-15 | 版本/打包一起验证，发布需确认 | v4.0 后 20 个产品提交（含 README-only `fc06d38`）未 bump；直接发布会版本重复 | 不要未经确认 bump/构建/打标签 | `config.py:25` |

**补充说明**：

- ADR-12 的“Windows 环境原因”是 `[推断]`；提交 `43476f0` 只写“门禁改为只在本地执行”。
- ADR-10 的“修复成本高”是根据回滚结果 `[推断]`；事实是悬停放大已回滚。

> 新 ADR 追加到表末；下一条 `ADR-16`。模板：`| ADR-16 | 决策 | 原因/后果 | 不要做 | 证据 |`；被取代时新增 ADR 并写“取代 ADR-xx”。

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

**版本 bump 检查**：`config.APP_VERSION` 与 `version_info.txt` 必须同步；`tests/test_version.py` 校验；发布前按 §7 检查。

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

<a id="sec-5"></a>
## 5. 历史经验库（LSN）

> 新教训追加 `LSN-24` 及以后；模板：`| LSN-24 | 现象 | 根因 | 修复/现状 | 提交 |`；不要删除旧条目。

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

<a id="sec-6"></a>
## 6. 开放问题与技术债

> §6 只登记未排期风险/技术债；可执行任务在 §7。排期后 §6 写 `tracked as TODO-xx`，不重复优先级/状态。

| ID | 事项 | 影响 | 证据 | 建议 | 处置 |
|---|---|---|---|---|---|
| OPEN-01 | `APP_VERSION` 仍 4.0，HEAD 未构建 | 发布阻塞 | `config.py:25`、`version_info.txt` | 发布前 bump 4.1 + 构建 + 验证；先问用户 | tracked as TODO-01 |
| OPEN-02 | 真实 125%/150% 未验收 | 视觉/DPI 风险 | 只有模拟截图 | 真实设备跑 §8.4 | tracked as TODO-02 |
| OPEN-03 | 完整 PyInstaller 构建不在门禁 | 打包资源风险 | `tests/test_packaging.py` 只静态/批处理 | 发布前 `build.bat` + 启动检查 | tracked as TODO-03 |
| OPEN-04 | 真实 npm 更新未验证 | 更新/回滚风险 | 单测 fake Popen | 一次性 Luker 副本验证 | tracked as TODO-04 |
| OPEN-05 | `resizing.py` 可缩放分支是死代码 | 维护性 | 生产只 `log_window.py:242` `resizable=False` | 确认后删除或加注释 | tracked as TODO-05 |
| OPEN-06 | 设置窗口与 `WindowResizer` 重复跨屏逻辑 | 维护性/重复逻辑 | `settings_window.py:329-350` / `resizing.py:119-159` | 抽 `refit_window_to_monitor()` | tracked as TODO-06 |
| OPEN-07 | `clear_scroll_bindings` 清全局绑定 | 其他滚动区失效 | `settings_window.py:110-119` | 保留单设置窗口不变量；CTk 升级后实例级解绑 | tracked as TODO-07 |
| OPEN-08 | `_ThemeCardHighlight` 自建动画状态机 | 重复实现 | `settings_window.py:153-215`；已有 `StepTicker` | 下次改动画时复用 | tracked as TODO-08 |
| OPEN-09 | `settings_window.py` 1369 行、`log_window.py` 1294 行 | 维护性 | 文件规模 | 只在下次必然修改时小步提取 | tracked as TODO-09 |
| OPEN-11 | 托盘 `stop()` 极端失败路径 | 退出残留风险 | `tray/icon.py:604-624` | 记录日志；实机极端验证 | 已接受 |
| OPEN-12 | 当前主题只用 accent 边框 | 视觉取舍 | `settings_window.py:742-748` | 需要时加小徽标；不是 bug | 取舍 |
| OPEN-13 | DeepSeek 素材/名称授权 | 合规风险 | `luker_launcher/assets/deepseek/*` | 用户确认 | 待确认 |

**已关闭，不要重复做**：

| 事项 | 修复提交/日期 | 现状 |
|---|---|---|
| 退出线程失败残留 | `707dd44` | 已修复 |
| 高 DPI 立绘 | `16dbd3f` | 已修复 |
| 打包/门禁测试 | `3966429` | 已修复 |
| 立绘任务取消 | `d484c4a` | 已取消 |
| `_theme_cards` | `6a1f2fb` | 已删除 |
| 异常收窄 | `0e6f34a` | 已修复 |
| 组合根构造期回调 | `3ad154f` | 已修复 |
| 悬停放大回滚 | `e9bc44f` | 已回滚 |
| GCL 移除 | `b840bf1` | 已移除 |
| 座右铭移除 | `a7a1c68` | 已移除 |
| `dev` 分支删除 | `157f22a` / 2026-11-14 | 已删除 |
| CTk 私有访问集中（OPEN-10） | `f3ffd54` / 2026-11-14 | 已完成，架构测试锁定 |

---

<a id="sec-7"></a>
## 7. 待办与下一步（可领取）

> §7 是唯一行动队列。领取时状态改 `进行中`，在 §0.2 记 HEAD；完成后改 `已完成` 并追加 §10 日志。

| ID | 关联 OPEN | 优先级 | 任务 | 验收标准 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| TODO-01 | OPEN-01 | P1 | 发布验证 4.1 | bump + `build.bat` + 100/125/150% 主题/立绘/日志/设置正常 + 资源可读 | 用户确认发布 | 待确认 |
| TODO-02 | OPEN-02 | P2 | 真实高 DPI 验收 | 真实 125/150% 设备跑 §8.4；记录截图/尺寸 | 设备 | 待开始 |
| TODO-03 | OPEN-03 | P2 | 完整 exe 构建冒烟 | `build.bat` 0；`_MEIPASS` 资源存在；启动无资源告警 | PyInstaller | 待开始 |
| TODO-04 | OPEN-04 | P2 | 真实 npm 更新（含 SQLite 扩展） | 一次性副本；成功/失败回滚/依赖恢复；原生模块缺失时补装成功；不动主安装 | 用户授权副本 | 待开始 |
| TODO-05 | OPEN-05 | P3 | 固定日志窗口最终决策 | 用户确认；若否删除 `resizable=True` 分支及测试 | 产品确认 | 待确认 |
| TODO-06 | OPEN-06 | P3 | 抽 `refit_window_to_monitor()` | 两窗口共用；行为不变；补测试 | 无 | 待开始 |
| TODO-07 | OPEN-07 | P3 | 滚动绑定实例级解绑 | 关闭设置窗口不影响其他滚动区；补测试 | CTk 方案 | 待开始 |
| TODO-08 | OPEN-08 | P3 | 复用 `StepTicker` 统一悬停动画 | 颜色过渡不变；少一套状态机 | 无 | 待开始 |
| TODO-09 | OPEN-09 | P3 | 大 UI 文件按需小步提取 | 只在必然修改时做；行为不变；先补测试 | 实际需求 | 待开始 |

**发布前检查（按顺序）**：

1. 用户确认发布；确认目标版本（当前建议 4.1）。
2. `config.APP_VERSION` 与 `version_info.txt` 同步。
3. `check.bat` 通过。
4. `build.bat` 成功；检查 `_MEIPASS` 资源。
5. 100%/125%/150% 手工冒烟（§8.4）。
6. 真实 npm 更新 + SQLite 扩展在一次性副本验证（TODO-04）。
7. 打标签/发布前再次确认；默认不推送。

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
- **DEV/ADR/LSN/OPEN/TODO**：文档 ID 前缀；分配规则见 §0.2。
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
- `docs/development-handbook.md`：本文件，当前事实与决策。
- `docs/archive/`：`00` 详细手册快照；`01`–`04` 版本段历史日志；`INDEX.md` 条目/提交/决策索引。
- 本地工作记录（`.zcode/reports/`，不随仓库分发，可能不存在）：`review-2026-11-09.md`、`review-fixes-2026-11-09.md`、`implementation-2026-11-05.md`、`launcher-refactor-and-package-plan-2026-11-05.md`、`ai-gijika-deepseek-2026-11-08.md`、`ai-gijika-polish-2026-11-09.md` 等；其结论已并入本手册/归档。
- Git：193 个产品提交 + 文档维护提交、17 标签、`git log --stat`、`git diff`、`git show`。

---

<a id="sec-10"></a>
## 10. 开发日志（只追加）

> 按时间正序，最新在文件末尾。新条目追加到 §10 最后，不要插入中间。下一条 ID 见 §0.2。
> 历史细节已压缩；完整回填按版本段存放：v1.0–v2.0 → `docs/archive/01-...`，v2.1–v3.3 → `02-...`，v3.4–v3.5 → `03-...`，v4.0+ → `04-...`。索引见 `docs/archive/README.md` 和 `docs/archive/INDEX.md`。
>
> **迁移说明（2026-11-14）**：本文件原位于 `.zcode/reports/development-history-2026-11-14.md`，现迁至 `docs/development-handbook.md` 并纳入 Git。旧条目中出现的 `.zcode/reports/...` 路径是历史记录，正文保持原样；对应详细内容现在 `docs/archive/`。旧条目中“未提交 / 被忽略”的表述也只反映当时状态。

### 10.1 提交覆盖图

| 版本段 | 提交范围（Git `A..B`，不含 A） | 数量 | 日志条目 | 分册 |
|---|---|---:|---|---|
| v1.0 | `cb75d8b` | 1 | DEV-20261002-01 | [01](archive/01-v1.0-v2.0-foundation.md) |
| v1.0 → v1.1 | `v1.0..v1.1` | 10 | DEV-20261002-02、DEV-20261018-01 | [01](archive/01-v1.0-v2.0-foundation.md) |
| v1.1 → v1.2 | `v1.1..v1.2` | 6 | DEV-20261018-02 | [01](archive/01-v1.0-v2.0-foundation.md) |
| v1.2 → v2.0 | `v1.2..v2.0` | 10 | DEV-20261018-03 | [01](archive/01-v1.0-v2.0-foundation.md) |
| v2.0 → v2.1 | `v2.0..v2.1` | 7 | DEV-20261019-01 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v2.1 → v2.2 | `v2.1..v2.2` | 6 | DEV-20261019-02 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v2.2 → v2.3 | `v2.2..v2.3` | 10 | DEV-20261020-01 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v2.3 → v2.4 | `v2.3..v2.4` | 17 | DEV-20261021-01 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v2.4 → v3.0 | `v2.4..v3.0` | 20 | DEV-20261022-01 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v3.0 → v3.1 | `v3.0..v3.1` | 20 | DEV-20261024-01 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v3.1 → v3.2 | `v3.1..v3.2` | 14 | DEV-20261025-01 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v3.2 → v3.3 | `v3.2..v3.3` | 9 | DEV-20261030-01 | [02](archive/02-v2.1-v3.3-engineering.md) |
| v3.3 → v3.4 | `v3.3..v3.4` | 8 | DEV-20261102-01 | [03](archive/03-v3.4-v3.5-visual-reliability.md) |
| v3.4 → v3.4.1 | `v3.4..v3.4.1` | 1 | DEV-20261103-01 | [03](archive/03-v3.4-v3.5-visual-reliability.md) |
| v3.4.1 → v3.5 | `v3.4.1..v3.5` | 16 | DEV-20261103-02 | [03](archive/03-v3.4-v3.5-visual-reliability.md) |
| v3.5 → v4.0 | `v3.5..v4.0` | 18 | DEV-20261105-01 | [04](archive/04-v4.0-coordinator-themes-ui.md) |
| v4.0 → 最后代码提交 | `v4.0..a7a1c68` | 20 | DEV-20261108-01 … DEV-20261110-01 | [04](archive/04-v4.0-coordinator-themes-ui.md) |

> 合计 193 个已发布基线产品提交；本轮 3 个代码修复 + 文档提交另计（未发布）。回填条目根据 Git/提交信息/测试/本地报告整理；无法证明的已标 `[待确认]`。
> `DEV-20261114-01` 起为文档维护条目，不对应产品代码提交。

### 10.2 条目索引

**已归档条目（23 条，详情见 `archive/01`–`04`）**：

| ID | 日期 | 分册 | 提交/范围 | 状态 | 摘要 | 详情 |
|---|---|---|---|---|---|---|
| DEV-20261002-01 | 2026-10-02 | 01 | `cb75d8b` | 已发布 | v1.0 原型导入；14 文件/3733 行；托盘/日志/进程/PWA/GCL/6 主题 | [01](archive/01-v1.0-v2.0-foundation.md#dev-20261002-01) |
| DEV-20261002-02 | 2026-10-02 | 01 | `206c1d1` | 已完成 | 清理死代码/裸 except；新增配置模板 | [01](archive/01-v1.0-v2.0-foundation.md#dev-20261002-02) |
| DEV-20261018-01 | 2026-10-18 | 01 | `206c1d1..38be292` | 已发布 | v1.1：日志/GCL/进程/PWA/托盘修复；注释/README | [01](archive/01-v1.0-v2.0-foundation.md#dev-20261018-01) |
| DEV-20261018-02 | 2026-10-18 | 01 | `6343f3e..5cfb3b3` | 已发布 | v1.2：日志/UI 资源优化、自动路径、清空队列 | [01](archive/01-v1.0-v2.0-foundation.md#dev-20261018-02) |
| DEV-20261018-03 | 2026-10-18 | 01 | `4c32010..4e98b09` | 已发布 | v2.0：合并进程管理器、拆日志/主题/配置、UI 队列、单实例/Job Object、文件日志、首批测试 | [01](archive/01-v1.0-v2.0-foundation.md#dev-20261018-03) |
| DEV-20261019-01 | 2026-10-19 | 02 | `71a73e3..c224c69` | 已发布 | v2.1：ruff/CI/LICENSE、托盘菜单/设置拆分、类型注解 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261019-01) |
| DEV-20261019-02 | 2026-10-19 | 02 | `34f95d2..34d01e3` | 已发布 | v2.2：高 DPI 跨屏、托盘/进程生命周期 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261019-02) |
| DEV-20261020-01 | 2026-10-20 | 02 | `b5993f0..aad0cad` | 已发布 | v2.3：GCL/PWA 竞态、APPX 校验、日志窗口最小尺寸、队列/重放上限 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261020-01) |
| DEV-20261021-01 | 2026-10-21 | 02 | `b69d47d..3729554` | 已发布 | v2.4：日志队列/搜索/显示/重放拆分、窗口缩放、UI 调度器、覆盖率门禁 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261021-01) |
| DEV-20261022-01 | 2026-10-22 | 02 | `24f9db0..b480684` | 已发布 | v3.0：主题/毛玻璃/圆角/按钮/呼吸 logo/关闭确认/托盘图标 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261022-01) |
| DEV-20261024-01 | 2026-10-24 | 02 | `fe149c4..c778e3b` | 已发布 | v3.1：应用主体拆分、日志/搜索拆分、目录分包 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261024-01) |
| DEV-20261025-01 | 2026-10-25 | 02 | `43476f0..523764c` | 已发布 | v3.2：关闭行为记忆、版本检查/更新、设置页、本地门禁 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261025-01) |
| DEV-20261030-01 | 2026-10-30 | 02 | `3260c48..5f9e402` | 已发布 | v3.3：托盘句柄、配置边界、构建失败、npm 生产环境、Job/单实例测试 | [02](archive/02-v2.1-v3.3-engineering.md#dev-20261030-01) |
| DEV-20261102-01 | 2026-11-02 | 03 | `2b9ebdb..16e97be` | 已发布 | v3.4：设计令牌、窗口淡入、日志状态、托盘键盘、**移除 GCL** | [03](archive/03-v3.4-v3.5-visual-reliability.md#dev-20261102-01) |
| DEV-20261103-01 | 2026-11-03 | 03 | `ca08bb9` | 已发布 | v3.4.1 版本补丁 | [03](archive/03-v3.4-v3.5-visual-reliability.md#dev-20261103-01) |
| DEV-20261103-02 | 2026-11-03 | 03 | `5f95490..ec0b561` | 已发布 | v3.5：雾灰毛玻璃、图标/字体、配置 BOM、Win32 声明、CTk 适配层 | [03](archive/03-v3.4-v3.5-visual-reliability.md#dev-20261103-02) |
| DEV-20261105-01 | 2026-11-05 | 04 | `547160a..a66f873` | 已发布 | v4.0：Coordinator + 单一包 + 架构测试 | [04](archive/04-v4.0-coordinator-themes-ui.md#dev-20261105-01) |
| DEV-20261108-01 | 2026-11-08 | 04 | `64f1a06..9834b5e` | 已完成 | DeepSeek 主题/卡片/日志立绘 | [04](archive/04-v4.0-coordinator-themes-ui.md#dev-20261108-01) |
| DEV-20261109-01 | 2026-11-09 | 04 | `2d6acda..00dec31` | 已完成 | 图片重做、主题卡片、固定日志窗口/立绘/座右铭 | [04](archive/04-v4.0-coordinator-themes-ui.md#dev-20261109-01) |
| DEV-20261109-02 | 2026-11-09 | 04 | `707dd44..3ad154f` | 已完成 | P2 退出/DPI 修复；打包/门禁测试；低风险清理 | [04](archive/04-v4.0-coordinator-themes-ui.md#dev-20261109-02) |
| DEV-20261109-03 | 2026-11-09 | 04 | `e9bc44f..7af004a` | 部分废弃 | 回滚悬停放大、加宽面板/左渐隐、座右铭浮层/一行 | [04](archive/04-v4.0-coordinator-themes-ui.md#dev-20261109-03) |
| DEV-20261110-01 | 2026-11-10 | 04 | `157f22a..a7a1c68` | 已完成 | 方案 A 布局；移除座右铭；滚动条最右 | [04](archive/04-v4.0-coordinator-themes-ui.md#dev-20261110-01) |
| DEV-20261114-01 | 2026-11-14 | 04 | 未提交 | 已完成 | 历史文档重构为可持续日志 | [04](archive/04-v4.0-coordinator-themes-ui.md#dev-20261114-01) |

**当前条目（未归档，详情见 §10.3）**：

| ID | 日期 | 类型 | 状态 | 证据 | 摘要 | 详情 |
|---|---|---|---|---|---|---|
| DEV-20261114-02 | 2026-11-14 | docs | 已完成 | [已验证] | 精简主文档；完整细节归档 | [§10.3](#dev-20261114-02) |
| DEV-20261114-03 | 2026-11-14 | docs | 已完成 | [已验证] | 文档迁入 docs；归档拆分 00–04；明确唯一写入目标 | [§10.3](#dev-20261114-03) |
| DEV-20261114-04 | 2026-11-14 | chore/docs | 已完成 | [已验证] | 删除本地/远程 `dev`；更新分支表与交接状态 | [§10.3](#dev-20261114-04) |
| DEV-20261114-05 | 2026-11-14 | docs | 已完成 | [已验证] | 追加点/读写契约/架构事实/版本坐标修正 | [§10.3](#dev-20261114-05) |
| DEV-20261114-06 | 2026-11-14 | fix/refactor | 已完成 | [已验证] | lifecycle 控制通道、Start.bat SQLite 步骤、CTk 私有访问集中 | [§10.3](#dev-20261114-06) |
| DEV-20261114-07 | 2026-11-14 | docs | 已完成 | [已验证] | 统一词表、ID registry、§6/§7 工作队列、测试数据规则 | [§10.3](#dev-20261114-07) |
| DEV-20261114-08 | 2026-11-14 | docs | 已完成 | [已验证] | TOC、docs/README 重写、§10 索引/去重、主题检查 | [§10.3](#dev-20261114-08) |
| DEV-20261114-09 | 2026-11-14 | docs | 已完成 | [已验证] | 归档锚点、INDEX.md、归档契约/已取代声明、重新冻结 | [§10.3](#dev-20261114-09) |
| DEV-20261114-10 | 2026-11-14 | test/docs | 已完成 | [已验证] | 文档结构校验器 + 测试，772/75/118 收尾 | [§10.3](#dev-20261114-10) |

### 10.3 保留的详细条目（未归档）

> 已归档条目的详细正文在 `docs/archive/01`–`04`；本节只保留尚未归档的条目。归档详情不要复制回主手册。

<a id="dev-20261114-02"></a>
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

<a id="dev-20261114-03"></a>
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

<a id="dev-20261114-04"></a>
#### DEV-20261114-04 | 清除已合并的 dev 分支并同步文档

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/development-handbook.md`） |
| 类型 | chore / docs |
| 状态 | 已完成 |
| 关联 | §1.4、§0.2、§10 |
| 证据等级 | [已验证] |

**目标/背景**

- `dev` 是方案 A 的比较分支，指向 `a512226`；该分支已通过合并提交 `157f22a` 完整进入 `ai-gijika`，没有独有提交。
- 保留本地/远程同名分支只会增加“当前工作分支”歧义；用户明确要求本地与远程一并删除，并推送文档。

**改动**

- 删除本地 `dev`（`a512226`）：删除前 `git rev-list --count ai-gijika..dev` = 0，`dev` 是 `ai-gijika` 祖先。
- 删除远程 `origin/dev`：`git push origin --delete dev`。
- 更新 §1.4：移除 `dev` 行；改写 `ai-gijika`/`origin/ai-gijika` 的提交范围与同步说明；注明 `dev` 已合并且删除。
- 更新顶部交接摘要、§0.2 控制表、§6“已关闭，不要重复做”。
- §7 无分支相关待办，状态不变；发布/DPI/构建仍为 OPEN-01/02/03、TODO-01/02/03。

**验证**

- 删除前：`git merge-base --is-ancestor dev ai-gijika` 返回成功；`ai-gijika..dev` = 0。
- 删除后：`git branch -vv` 只剩 `ai-gijika`/`main`；`git ls-remote --heads origin` 只剩 `main`/`ai-gijika`。
- 文档提交推送后：本地 `ai-gijika` 与 `origin/ai-gijika` 同步，`git status` clean。
- `check.bat` 通过：758 tests / 74%；ruff format/check、mypy 通过。
- 提交作者 `Yaoyao <jiayinyao24@outlook.com>`，GPG `%G?` = `G`，无 AI/Co-authored-by 署名。

**决策/风险**

- 删除远程分支不可从本地恢复远端 ref，但 `a512226` 及其历史仍可从 `ai-gijika` 到达，不丢代码。
- 本次仅按用户明确授权删除远程 `dev` 并推送 `ai-gijika`；不涉及标签、Release、版本 bump、真实用户配置。

**遗留/下一步**

- 发布验证仍待用户确认（TODO-01）；真实高 DPI、完整构建为 TODO-02/03。
- 下一条日志 `DEV-20261114-05`。

<a id="dev-20261114-05"></a>
#### DEV-20261114-05 | 修正文档追加点、读写契约与架构事实

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/development-handbook.md`） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | §0、§1、§2、§3、§4、§9、§10 |
| 证据等级 | [已验证] |

**目标/背景**

- 追加点位于 `DEV-20261114-04` 之前，下一个 Agent 会插错位置。
- `docs/README.md` 的“只写 §10”与 §0.5 的更新流程矛盾。
- §2.1 的 config/bootstrap 规则与 `config.py:12`、`main.py:3`、`__main__.py:3`、`tests/test_architecture.py:137-156` 不符。
- §1.4/§1.5/§1.6 的 HEAD、标签、提交范围、日期与实测不一致。

**改动**

- 追加点/页脚移到文件 EOF；模板 `###` 改 `####`；§0.2 增加当前 HEAD/提交数/标签。
- 统一写入契约：§10 追加 + §0.2/§6/§7；§1–§5 仅在变化时改；归档不改。
- 修正 §2.1/§2.2/§2.3：`config` 可依赖 `paths`/`theme`；`main.py` 与 `__main__.py` 都允许导入 bootstrap；补 `python -m luker_launcher`。
- 修正 §2.4/§2.5/§2.6/§4.1：lifecycle 当前普通 post 例外、shutdown 不停止 Luker、日志单源、调度器限额、config 写入者。
- 修正 §4.6/§4.7：托盘状态/局部 ctypes、测试工具四列 schema、假 Luker 配方。
- §1.4/§1.5/§10.1 改用 tag 区间；v2.0/v3.5 日期、v1.1 计数、ruff 114、标签本地/远程、ADR-15 20 提交。
- §0.9 增加勘误表；§9.2 修正 trim；§9.4 标注本地报告可能不存在。
- 根 README 标注 Start.bat `storage:install-sqlite` 缺口（批次 2 修复）。

**验证**

- Markdown 代码围栏 6 个成对；表格列数检查 0 异常；追加标记是最后一个非空行。
- `check.bat` 通过；docs-only，代码基线不变（758 tests / 74%）。
- 未修改生产代码/测试；未改 `launcher_config.json`。

**决策/风险**

- 批次 1 只改文档；Start.bat 缺口、lifecycle 通道在批次 2 用独立提交修复。
- 旧日志正文不修改；旧文件名/计数用 §0.9 勘误解释。

**遗留/下一步**

- 批次 2：lifecycle `post_control`、Start.bat storage 步骤、CTk 适配层、日志注释。
- 下一条 `DEV-20261114-06`。

<a id="dev-20261114-06"></a>
#### DEV-20261114-06 | 修复 lifecycle、更新依赖与 CTk 私有访问不一致

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | `c8cf48d`、`c0c96bb`、`f3ffd54` + 本条 docs 提交 |
| 类型 | fix / refactor |
| 状态 | 已完成 |
| 关联 | ADR-03、ADR-07、ADR-13、OPEN-10、§2.4/§2.5/§4.1/§4.5 |
| 证据等级 | [已验证] |

**目标/背景**

- 退出完成回调走普通 post，可能被普通队列丢弃；文档却要求 `post_control`。
- 更新依赖只执行 npm install，漏掉 Start.bat 在 `better_sqlite3.node` 缺失时的 `storage:install-sqlite`。
- CTk 私有访问分散在 `log_window.py`/`dpi.py`，ADR-13 的隔离承诺不成立。
- `log/store.py` 仍写“按来源”，实际只有一个 Luker 日志源。

**改动**

- `lifecycle_coordinator.exit()` 改 `post_control`；移除 `exit_key`；测试断言控制通道。
- `services/version.py` 增加 `SQLITE_NATIVE_PATH`、`_needs_storage_install()`、`_run_storage_install()`；npm install 后条件执行 `npm run storage:install-sqlite`。
- `ui/ctk_adapter.py` 增加 textbox/scaling/ScalingTracker 辅助函数；`log_window.py`/`dpi.py` 不再直接访问私有属性；`tests/test_architecture.py` 增加隔离检查。
- `log/store.py` 注释改为单一日志源。
- 更新 ADR-03/07/13、OPEN-10、§2.4/§2.5/§4.1/§4.5、§8.1、README。

**验证**

- `check.bat`：771 tests / 75% / 115 files；ruff format/check、mypy 通过。
- lifecycle 18 项、version 64 项、CTk 8 项、architecture 14 项、DPI 26 项、log search 26 项通过。
- `test_architecture.py::test_ctk_private_access_is_isolated` 通过；`ui/` 下仅适配层访问 CTk 私有属性。
- Start.bat 真实更新未在用户主安装上执行；单测覆盖存在/缺失/失败三条路径，真实副本验证仍见 TODO-04。

**决策/风险**

- `post_control` 是无界控制队列，退出回调不再被普通队列丢弃；`lifecycle.exiting` 防重复。
- storage 步骤只在原生模块缺失时执行，不改 `NPM_INSTALL_ARGS`，不影响正常启动。
- CTk 适配层保持行为不变；DPI 测试和架构测试锁定访问边界。

**遗留/下一步**

- 批次 3：词表、ID registry、§6/§7 工作队列。
- 真实 Start.bat 更新（一次性副本）仍为 TODO-04；真实 125/150% 仍为 TODO-02。
- 下一条 `DEV-20261114-07`。

<a id="dev-20261114-07"></a>
#### DEV-20261114-07 | 统一文档词表、ID 与工作队列

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/development-handbook.md`） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | §0、§3、§5、§6、§7、§8、§9 |
| 证据等级 | [已验证] |

**目标/背景**

- §6/§7 双份工作项优先级冲突；状态/证据/优先级词表漂移；ADR/LSN/OPEN/TODO 没有 ID 分配表。
- 测试数据规则只在冻结归档里，主手册缺少。

**改动**

- §0.2 增加 ID registry（DEV/ADR/LSN/OPEN/TODO）。
- §0.3 改名“证据等级”；§0.4 恢复状态定义，区分缺陷严重度/工作优先级/处置。
- §0.5 增加任务路由；§0.6 模板改为 `####` 并使用统一词表。
- §6 只留未排期风险/债（`影响` + `处置`）；§7 唯一行动队列（关联 OPEN/优先级/状态）；已关闭改表。
- §3/§5 增加 next ID 与模板；§8.2 加 pause 说明；§8.5 恢复测试数据规则；§9.1 补 ID/GCL/方案 A；§9.3 补引用哈希。
- 更新 §0.2 最新/下一条、§10.2 索引。

**验证**

- Markdown 围栏/表格检查通过；ID registry 与 §10.2/§6/§7 一致。
- `check.bat` 771 tests / 75% / 115 files（docs-only，代码基线不变）。
- 未改生产代码/测试；未改用户配置。

**决策/风险**

- §7 是唯一行动队列；§6 不再重复优先级/状态，避免冲突。
- 旧日志不改；历史状态词保留原样，新条目用新词表。

**遗留/下一步**

- 批次 4：TOC、§10.2/§10.3 去重、docs/README 重写。
- 下一条 `DEV-20261114-08`。

<a id="dev-20261114-08"></a>
#### DEV-20261114-08 | 重组主手册索引与阅读路径

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/development-handbook.md`） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | §0.7、§4.2、§10、`docs/README.md` |
| 证据等级 | [已验证] |

**目标/背景**

- 主手册 1,300+ 行没有 TOC；§10.2 混合已归档/当前条目，§10.3 重复 A04 详细正文。
- 文件地图在 §0.7 和 docs/README 重复；新 Agent 缺少任务配方。

**改动**

- 顶部增加 Quick facts + 显式锚点 TOC（handoff/sec-0..10）。
- §0.7 文件地图改为链接 docs/README；README 重写为入口/10 分钟接手/任务配方/写入契约/目录/本地工具警告。
- §10.2 拆“已归档 23 条 / 当前 6 条”，加详情链接；§10.3 删除 3 条已归档重复详情，只留未归档条目并加锚点。
- §10.1 分册列改为 archive 链接；§4.2 增加新增主题/版本 bump 检查。
- 保留旧日志正文；不修改归档。

**验证**

- Markdown 表格/围栏检查；§10.2 23+6 行；§10.3 未归档条目；TOC 锚点存在。
- `check.bat` 771 tests / 75% / 115 files（docs-only）。
- docs/README 链接可解析。

**决策/风险**

- 主手册仍是唯一写入目标；归档详情只链接，不复制。
- 当前条目表只保留未归档条目，后续新条目继续加。

**遗留/下一步**

- 批次 5：归档锚点/INDEX/已取代声明。
- 下一条 `DEV-20261114-09`。

<a id="dev-20261114-09"></a>
#### DEV-20261114-09 | 规范归档导航并新增 INDEX

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/`） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | §10、`archive/README.md`、`archive/INDEX.md` |
| 证据等级 | [已验证] |

**目标/背景**

- 归档正文只读但含硬编码 `01/04`、上一册/下一册；加 `05` 需要改只读文件。
- 没有条目/提交/决策索引；A00 被当成“完整原文”过度阅读。

**改动**

- 23 条 DEV 加 `<a id="dev-...">`；A00 加 15 个 ADR 锚点与 3 个阅读地图锚点。
- 去掉分册 `01/04` 分母和上一册/下一册；页脚统一 INDEX/主手册。
- 新增 `archive/INDEX.md`：23+7 条 DEV、36 个关键提交、15 ADR、23 LSN。
- 重写 `archive/README.md`：归档契约、查 X 去哪、A00 阅读地图、已取代声明、frontier、轮转清单。
- 主手册 §10.2 详情链接指向锚点；§9.4/docs README 增加 INDEX。

**验证**

- 23 个 DEV 锚点、15 个 ADR 锚点、3 个 A00 阅读锚点；INDEX 23+7 条。
- 链接可解析；表格/围栏检查通过。
- `check.bat` 771/75/115（docs-only）。
- 归档正文除锚点/导航外未改。

**决策/风险**

- 分册正文冻结；索引可变；勘误只写主手册 §0.9。
- A00 不拆；只读 §3/§2.4/§8.3/§8.5。

**遗留/下一步**

- 批次 6：文档校验器 + 最终检查。
- 下一条 `DEV-20261114-10`。

<a id="dev-20261114-10"></a>
#### DEV-20261114-10 | 增加文档结构校验器并收尾

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/`） |
| 类型 | test / docs |
| 状态 | 已完成 |
| 关联 | §8、§10、`docs/tools/check_docs.py` |
| 证据等级 | [已验证] |

**目标/背景**

- 追加点、DEV ID、链接、表格和归档计数需要自动检查，防止下一位 Agent 再次写坏。

**改动**

- 新增 `docs/tools/check_docs.py`：追加标记、最新/下一条 DEV、TOC 锚点、相对链接/锚点、表格/围栏、归档 5+8+3+7 计数、INDEX 与主手册当前条目一致。
- 新增 `tests/test_docs.py`，纳入 `check.bat`。
- 更新 §1.6/§8.1/§8.2、`docs/README`、§0.2/§10.2。

**验证**

- `python docs/tools/check_docs.py`：`docs structure: OK`。
- `check.bat`：772 tests / 75% / 118 files；ruff/mypy 通过。
- 全部相对链接/显式锚点可解析；表格/围栏一致。
- 未改生产代码/测试（除新增 docs 测试）；未改用户配置。

**决策/风险**

- 校验器只查结构，不评判历史措辞；历史旧状态词保持原样。
- 文档测试依赖 Python 标准库，无新依赖。

**遗留/下一步**

- 发布验证/真实 DPI/真实更新仍为 TODO-01/02/04。
- 下一条 `DEV-20261114-11`。

---

> 下一条日志 ID：`DEV-20261114-11`。追加后请更新 §0.2 控制表、§6/§7 状态；只有结构/事实变化时才在 §0.9 记录。
>
> **追加点（本行之后）**：

<!-- ===== 新开发日志追加点：请在本行之后追加下一条 DEV 记录（复制 §0.6 模板） ===== -->
