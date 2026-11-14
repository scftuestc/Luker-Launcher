# 开发日志规范

> **文档类型**：日常开发维护（写作契约，低频更新）
> **文档编号**：`DL-INDEX`
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md` 和 [`../handbook/`](../handbook/README.md)；高于历史归档。
> **导航**：[文档总入口](../README.md) · [架构手册](../handbook/README.md) · [当前状态](STATUS.md) · [当前日志](current.md)

本目录是**日常开发维护类**文档：当前状态、风险、TODO、交接摘要和只追加的开发日志。
基本不变动的架构知识在 [`../handbook/`](../handbook/README.md)。

## 1. 文件地图

| 文件 | 内容 | 更新时机 |
|---|---|---|
| [`STATUS.md`](STATUS.md) | 当前状态、交接摘要、OPEN 风险、TODO 行动队列、发布检查、勘误 | **每次任务结束** |
| [`current.md`](current.md) | 尚未归档的 `DEV` 条目，按时间正序，**只追加** | **每次任务结束**（末尾追加） |
| [`INDEX.md`](INDEX.md) | 已归档/当前 `DEV` 索引、关键提交、ADR/LSN 索引 | 新增条目时加一行 |
| [`archive/README.md`](archive/README.md) | 归档契约、分册导航、阅读地图、轮转清单 | 轮转时 |
| [`archive/00-detailed-handbook-2026-11-14.md`](archive/00-detailed-handbook-2026-11-14.md) | 拆分前详细手册快照（只读） | 不再更新 |
| [`archive/01-v1.0-v3.3.md`](archive/01-v1.0-v3.3.md) | v1.0–v3.3 历史日志（13 条，只读） | 不再更新 |
| [`archive/02-v3.4-v4.0.md`](archive/02-v3.4-v4.0.md) | v3.4–v4.0 历史日志（10 条，只读） | 不再更新 |

> 当前日志只保留未归档条目；归档正文冻结。`STATUS.md` 是当前事实/待办的唯一来源。

## 2. 每次任务的写入流程（必须执行）

1. **读状态**：先读 [`STATUS.md`](STATUS.md) 的交接摘要、OPEN、TODO；确认硬约束。
2. **领 ID**：在下面 ID registry 领取 `DEV-YYYYMMDD-NN`；当天从 `01` 开始，跨天重置。
3. **追加日志**：复制第 5 节模板，追加到 [`current.md`](current.md) **末尾**；不要插入旧条目中间。
4. **更新状态**：[`STATUS.md`](STATUS.md) 的控制表（最新条目、下一条、HEAD、质量基线）、OPEN/TODO 状态。
5. **更新索引**：[`INDEX.md`](INDEX.md) 的“当前条目”加一行；归档轮转时才动归档索引。
6. **稳定知识变了才改 handbook**：架构→`02`，决策→`03`，组件→`04`，教训→`05`，测试→`06`，基线→`01`，术语→`07`；并在 `STATUS.md` 的“文档修订与勘误”记一行。
7. **提交**：文档随任务提交；作者仅 `Yaoyao <jiayinyao24@outlook.com>`，GPG 签名，无 AI/Co-authored-by 署名。

**边界**：任务不改变架构/决策/组件时，不要改 `../handbook/`；不要复制归档正文回 `current.md`。

## 3. ID registry（写前先领）

| 前缀 | 含义 | 正文位置 | 下一个 | 分配规则 |
|---|---|---|---|---|
| `DEV-YYYYMMDD-NN` | 开发日志 | [`current.md`](current.md) | `DEV-20261114-13` | 当天从 01 开始，跨天重置；追加，不跳号 |
| `ADR-NN` | 设计决策 | [`../handbook/03-decisions.md`](../handbook/03-decisions.md) | `ADR-16` | 追加，不重排；被取代时新增并标注 |
| `LSN-NN` | 经验教训 | [`../handbook/05-lessons.md`](../handbook/05-lessons.md) | `LSN-24` | 追加，不删除旧条目 |
| `OPEN-NN` | 未排期风险/技术债 | [`STATUS.md`](STATUS.md) | `OPEN-14` | 追加；排期后写 `tracked as TODO-xx` |
| `TODO-NN` | 行动队列 | [`STATUS.md`](STATUS.md) | `TODO-10` | 追加；领取时状态改 `进行中` |

> 先在本表领取 ID，再写正文；不要跳号、复用或并发抢号。`DEV` 日期用任务完成日 `YYYY-MM-DD`。

## 4. 词表与写作规则

**证据等级**：

| 标签 | 含义 | 例子 |
|---|---|---|
| `[已验证]` | 代码、测试、命令或 Git 历史可直接证明 | `check.bat` 通过；`git rev-list` 计数 |
| `[推断]` | 根据提交信息/代码结构推断，未单独实验 | “可能是为了避免重复开浏览器” |
| `[待验证]` | 代码/测试已完成，但缺少实机或真实环境验证 | 单测通过，真实 125% 设备未跑 |
| `[待确认]` | 需要用户/产品/实机确认 | “是否发布需用户确认” |

**状态**：`待开始`、`进行中`、`待验证`、`待确认`、`已完成`、`已发布`、`已回滚`、`部分废弃`、`已废弃`、`阻塞`。
**类型**：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`perf`、`release`、`revert`。
**缺陷严重度**：`P0` 立即；`P1` 发布前必须；`P2` 发布前应修；`P3` 维护性/可延后。
**工作优先级**：与缺陷严重度分开写；不要在优先级里混写“发布”等场景。
**处置**：`已接受`、`已知风险`、`取舍` 是处置结果，不是状态；只用于 `STATUS.md` 的风险表。

写作规则：

- 日期 `YYYY-MM-DD`；提交用 7 位短哈希；文件引用 `path:line`。
- 写“改了什么行为、哪个文件、哪个测试”，不写“优化了代码”这类空话。
- 未验证的内容标 `[待验证]`/`[待确认]`，不要写成已完成。
- 旧日志不修改；发现错误在 `STATUS.md` 的“文档修订与勘误”追加，并引用旧条目。
- 决策被推翻时不删除旧 ADR；新增 ADR 并标注“取代 ADR-xx”。

## 5. 开发日志模板（可直接复制）

```markdown
#### DEV-YYYYMMDD-NN | 一句话标题

| 字段 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| 分支 | ai-gijika |
| 提交 | abc1234（未提交则写“未提交”） |
| 类型 | feat / fix / refactor / test / docs / chore / release |
| 状态 | 待开始 / 进行中 / 待验证 / 待确认 / 已完成 / 已发布 / 已回滚 / 部分废弃 / 已废弃 / 阻塞 |
| 关联 | ADR-xx / OPEN-xx / TODO-xx / HB-xx |
| 证据等级 | [已验证] / [推断] / [待验证] / [待确认] |

**目标/背景**

- 为什么做；对应哪个用户问题或审查项。

**改动**

- `path:line`：改了什么行为；新增/删除的组件、配置、测试。

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

## 6. 任务路由

| 你新增/修改了什么 | 写到哪里 |
|---|---|
| 新教训/回归 | [`../handbook/05-lessons.md`](../handbook/05-lessons.md) `LSN` |
| 新设计决策 | [`../handbook/03-decisions.md`](../handbook/03-decisions.md) `ADR` |
| 新组件/工具 | [`../handbook/04-components.md`](../handbook/04-components.md) |
| 新风险/技术债 | [`STATUS.md`](STATUS.md) `OPEN` |
| 可执行任务 | [`STATUS.md`](STATUS.md) `TODO` |
| 新测试规则 | [`../handbook/06-testing.md`](../handbook/06-testing.md) |
| 架构/流程变化 | [`../handbook/02-architecture.md`](../handbook/02-architecture.md) |
| 任务完成 | [`current.md`](current.md) `DEV` + `STATUS.md` + `INDEX.md` |

## 7. 归档轮转

当 [`current.md`](current.md) 未归档条目超过 **30 条**或一个主版本结束时：

1. 新建 `archive/03-<版本段>.md`，把最早条目的正文迁入；保留 `<a id="dev-...">` 锚点。
2. `current.md` 只保留摘要/链接，或删除已迁条目。
3. 更新 [`INDEX.md`](INDEX.md)、[`archive/README.md`](archive/README.md)、[`STATUS.md`](STATUS.md) 的归档边界。
4. 冻结新分册正文；之后只改索引。
5. 跑 `python docs/tools/check_docs.py`，确认计数/链接。

## 8. 接手/交班检查表

接手：

- [ ] 已读 [`../handbook/README.md`](../handbook/README.md)、`01`、`02`、`03`、`04`。
- [ ] 已读 [`STATUS.md`](STATUS.md) 的交接摘要、OPEN、TODO。
- [ ] `git status` 干净；当前分支/最后代码提交已记录。
- [ ] 已跑 `check.bat`；测试数/覆盖率已记录。
- [ ] 已确认硬约束：不推送、不改用户配置、GPG 签名、作者只有 Yaoyao、无 AI 署名。

交班：

- [ ] 最后一条 `DEV` 写清“已完成/未完成/下一步”。
- [ ] `STATUS.md` 的控制表、OPEN、TODO 已更新。
- [ ] `current.md` 的追加点仍是文件最后一个非空行。
- [ ] 未验证项已标 `[待验证]`/`[待确认]`。
- [ ] 工作区没有未说明的改动。

## 9. 旧章节映射

2026-11-14 拆分前的 `§0`–`§10` 编号映射见 [`../README.md#legacy-numbering`](../README.md#legacy-numbering)。历史日志中的 `§N` 保持原样，按该表定位新文件。

---

[文档总入口](../README.md) · [架构手册](../handbook/README.md) · [当前状态](STATUS.md) · [当前日志](current.md)
