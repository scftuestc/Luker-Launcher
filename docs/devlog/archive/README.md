# Luker Launcher 历史归档

> **文档类型**：历史归档索引（正文只读；索引可维护）
> **事实截止**：2026-11-14
> **当前事实**：以 [`../STATUS.md`](../STATUS.md) 与 [`../../handbook/`](../../handbook/README.md) 为准
> **条目/提交/决策索引**：[`../INDEX.md`](../INDEX.md)

## 1. 归档契约

- 分册正文（`00`–`02`）**冻结**；不再修改，也不追加新日志。
- 新日志只写 [`../current.md`](../current.md)；勘误写 [`../STATUS.md`](../STATUS.md) 的“文档修订与勘误”，引用旧条目，不改归档正文。
- 本文件和 `../INDEX.md` 是索引，可在轮转/结构变更时更新；分册内不写“上一册/下一册”，导航统一走索引。
- 权威顺序：代码/测试/README > [`../../handbook/`](../../handbook/README.md) > [`../STATUS.md`](../STATUS.md) > 归档 > 本地报告。

## 2. 归档是什么

这里保存 2026-11-14 之前的详细开发历史：每个阶段的改动、验证数据、提交范围和决策背景。当前日志只保留摘要；需要“当时具体做了什么/为什么”时查这里。

**不要从头读到尾。** 先看 [`../STATUS.md`](../STATUS.md) 和 [`../current.md`](../current.md)，只有摘要不够时再按版本段选一册，或直接用 [`../INDEX.md`](../INDEX.md) 查 DEV/提交/决策。

## 3. 分册导航

| 分册 | 版本段 | 日期 | DEV 条目 | 主题 |
|---|---|---|---|---|
| [`00-detailed-handbook-2026-11-14.md`](00-detailed-handbook-2026-11-14.md) | — | 截至 2026-11-14 | — | 详细手册快照（structure 2.0）：架构、ADR、组件、经验、测试 |
| [`01-v1.0-v3.3.md`](01-v1.0-v3.3.md) | v1.0–v3.3 | 2026-10-02–10-30 | DEV-20261002-01 … DEV-20261030-01（13 条） | 原型导入、稳定性修复、架构基座、工程化、视觉与版本管理 |
| [`02-v3.4-v4.0.md`](02-v3.4-v4.0.md) | v3.4–v4.0+ | 2026-11-02–11-14 | DEV-20261102-01 … DEV-20261114-01（10 条） | 设计令牌、GCL 移除、Coordinator、DeepSeek 主题、日志窗口/立绘、P2 修复 |

> 2026-11-14 合并：原 `01`+`02` → [`01-v1.0-v3.3.md`](01-v1.0-v3.3.md)，原 `03`+`04` → [`02-v3.4-v4.0.md`](02-v3.4-v4.0.md)；条目正文与 `#dev-...` 锚点不变。

## 4. 查 X 去哪

| 问题 | 去哪 |
|---|---|
| v2.0 的架构基线是什么？ | [`01`](01-v1.0-v3.3.md#dev-20261018-03) |
| v3.0 视觉改版/高 DPI 怎么做的？ | [`01`](01-v1.0-v3.3.md#dev-20261022-01) |
| GCL 为什么移除/设计令牌怎么落地？ | [`02`](02-v3.4-v4.0.md#dev-20261102-01) + [`00 §3 ADR-08`](00-detailed-handbook-2026-11-14.md#adr-08) |
| v4.0 Coordinator 怎么拆？ | [`02`](02-v3.4-v4.0.md#dev-20261105-01) |
| DeepSeek 主题/立绘布局？ | [`02`](02-v3.4-v4.0.md#dev-20261108-01)、[`02`](02-v3.4-v4.0.md#dev-20261110-01) |
| 某个 DEV/提交/ADR 在哪一册？ | [`../INDEX.md`](../INDEX.md) |
| ADR 完整论证 | `00` §3（`#adr-01`…`#adr-15`）；当前 ADR 见 [`../../handbook/03-decisions.md`](../../handbook/03-decisions.md) |
| 详细运行流程 | `00` §2.4（`#a00-flows`）；当前流程见 [`../../handbook/02-architecture.md`](../../handbook/02-architecture.md) |
| 测试覆盖理由/测试数据规则 | `00` §8.3/§8.5（`#a00-test-gaps`、`#a00-test-data`）；当前规则见 [`../../handbook/06-testing.md`](../../handbook/06-testing.md) |

## 5. A00 阅读地图

`00` 是 2026-11-14 的 **structure 2.0** 快照，约 1,082 行，和当前手册有大量重复。只读以下部分：

- §3 ADR 完整论证（`#adr-01`…`#adr-15`）
- §2.4 详细运行流程（`#a00-flows`）
- §8.3/§8.5 覆盖理由与测试数据规则（`#a00-test-gaps`、`#a00-test-data`）

**不要**用 `00` 的 §0/§1/§4/§5/§7/§9 作为当前事实；它们已被 [`../../handbook/`](../../handbook/README.md) 和 [`../STATUS.md`](../STATUS.md) 取代。

## 6. 已取代声明（读旧分册前先看）

| 旧位置 | 旧说法 | 当前 |
|---|---|---|
| `00` §0.2/§0.5/§0.8 | 文档在 `.zcode/`、被忽略、不要提交 | [`../README.md`](../README.md)：`docs/` 已跟踪，文档随任务提交 |
| `00` §1.4 | 存在 `dev` 分支 | [`../../handbook/01-baseline.md`](../../handbook/01-baseline.md)：`dev` 已合并且删除 |
| `00` §1.6 | 工作区只有忽略文件 | [`../../handbook/01-baseline.md`](../../handbook/01-baseline.md)：`docs/` 已跟踪 |
| `00` §4/§5/§7/§9 | 组件/LSN/TODO/来源的旧快照 | 组件/LSN/附录见 `../../handbook/04`/`05`/`07`；TODO 见 [`../STATUS.md`](../STATUS.md) |
| `02` `DEV-20261114-01` | 文档未提交、不进入版本库 | [`../README.md`](../README.md)：文档随任务提交 |
| 旧 `docs/development-handbook.md` | 单文件手册 + `§0`–`§10` | 已拆为 [`../../handbook/`](../../handbook/README.md) + [`../`](../README.md)；旧 `§` 映射见 [`../../README.md#legacy-numbering`](../../README.md#legacy-numbering) |
| 旧 `docs/archive/01`–`04` | 四个版本分册 | 已合并为 `01`/`02` 两册；旧路径只存在于历史日志 |

## 7. 快照边界与 archive frontier

- 最后归档条目：`DEV-20261114-01`（在 [`02`](02-v3.4-v4.0.md#dev-20261114-01)）；首个未归档条目：`DEV-20261114-02`（在 [`../current.md`](../current.md#dev-20261114-02)）。
- `02` 里的 `DEV-20261114-01` 是 docs-meta 条目，属于历史拆分遗留；未来 docs-meta 条目在轮转时进入 `03-docs-workflow.md`，不要混进产品分册。
- 归档不更新；新日志只写 [`../current.md`](../current.md)。

## 8. 轮转清单

当 [`../current.md`](../current.md) 未归档条目超过 30 条或主版本结束时：

1. 冻结当前分册；不再改正文。
2. 新建 `03-<版本段>-<主题>.md`，把较早条目的详细正文迁入；保留 `<a id="dev-...">` 锚点。
3. `../current.md` 只保留未归档条目；`../INDEX.md` 加归档行。
4. 更新 `../INDEX.md`、本 README 的分册表/frontier、[`../STATUS.md`](../STATUS.md) 的控制表。
5. 跑 `python docs/tools/check_docs.py`；检查 DEV ID 唯一、链接、条目计数。
6. 按批次提交；作者/签名遵循 [`../README.md`](../README.md) 第 2 节。

## 9. 回填说明

`DEV-20261002-01` 至 `DEV-20261110-01` 根据 Git 历史、提交信息、测试和本地报告**回填**；`DEV-20261114-01` 起为实时维护条目。回填条目的“验证”以当时报告/当前代码可证明的内容为准，无法证明的已标 `[待确认]`。

---

[文档总入口](../../README.md) · [架构手册](../../handbook/README.md) · [当前状态](../STATUS.md) · [条目索引](../INDEX.md)
