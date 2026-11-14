# Luker Launcher 架构手册

> **文档类型**：架构手册（稳定知识，低频更新）
> **文档编号**：`HB-INDEX`
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md`；高于历史归档。
> **导航**：[文档总入口](../README.md) · [当前状态](../devlog/STATUS.md) · [当前日志](../devlog/current.md)

本目录只放**基本不变动**的知识：项目基线、当前架构、设计决策、可复用组件、历史经验、测试规范和附录。
日常状态、风险、TODO、交接摘要和开发日志在 [`../devlog/`](../devlog/README.md)。

## 1. 文档地图

| 编号 | 文件 | 对应旧章节 | 内容 | 更新时机 |
|---|---|---|---|---|
| `HB-01` | [`01-baseline.md`](01-baseline.md) | §1 | 产品、环境、硬约束、分支/版本坐标、质量基线 | 发布、分支或质量基线变化时 |
| `HB-02` | [`02-architecture.md`](02-architecture.md) | §2 | 分层依赖、模块地图、启动顺序、运行流程、线程与状态 | 架构/流程变化时 |
| `HB-03` | [`03-decisions.md`](03-decisions.md) | §3 | ADR 决策表与“不要做”清单 | 新决策或被取代时 |
| `HB-04` | [`04-components.md`](04-components.md) | §4 | 可复用组件目录（不要重复造轮子） | 新增/删除/迁移组件时 |
| `HB-05` | [`05-lessons.md`](05-lessons.md) | §5 | 历史经验库（LSN） | 新增教训时 |
| `HB-06` | [`06-testing.md`](06-testing.md) | §8 | 测试布局、门禁、覆盖盲区、冒烟与测试数据规则 | 测试命令/覆盖/门禁变化时 |
| `HB-07` | [`07-reference.md`](07-reference.md) | §9 | 术语、配置 schema、关键提交、事实来源 | 术语/配置/来源变化时 |

旧章节与现文件的完整映射见 [`../README.md#legacy-numbering`](../README.md#legacy-numbering)；`§0`、`§6`、`§7`、`§10` 已迁到 [`../devlog/`](../devlog/README.md)。

## 2. 阅读路径

| 你的任务 | 建议顺序 |
|---|---|
| 第一次接手项目 | `01` → `02` → `03` → `04`；`05`/`06`/`07` 按需查 |
| 写新功能/新组件 | 先查 `04`，再查 `03` 是否有相反决策 |
| 改架构/线程/启动流程 | `02`，并检查 `03` 的 ADR |
| 排障/避免重复踩坑 | `05`；需要完整背景时查归档 `00` 的 §3/§2.4 |
| 跑测试/发布前验证 | `06`；风险和 TODO 看 [`../devlog/STATUS.md`](../devlog/STATUS.md) |
| 查术语/配置/历史提交 | `07` |

不要从头读到尾；按任务选一册。每册控制在 50–220 行。

## 3. 更新规则

- **只在事实、决策或组件变化时改本目录**；日常任务结束只写 [`../devlog/current.md`](../devlog/current.md)，并更新 [`../devlog/STATUS.md`](../devlog/STATUS.md)。
- **ADR/LSN 只追加**：不删除旧条目；被取代时新增 ADR 并标注“取代 ADR-xx”。
- **组件删除**：在 `04` 标记“已废弃”，保留历史，不直接删行。
- **测试基线**：`06` 的测试数量和覆盖率以最近一次 `check.bat` 实测为准；改代码导致基线变化时同步。
- **旧章节引用**：历史日志里的 `§N` 是拆分前编号，按 `../README.md#legacy-numbering` 映射，不需要改写旧日志。
- **勘误**：发现旧条目/归档错误时，只追加到 [`../devlog/STATUS.md`](../devlog/STATUS.md) 的“文档修订与勘误”，不改历史正文。

## 4. 权威顺序

1. 代码、测试、根 `README.md`（产品行为的最终依据）
2. 本目录（当前架构、决策、组件、经验）
3. [`../devlog/STATUS.md`](../devlog/STATUS.md)（当前状态、风险、TODO）
4. [`../devlog/current.md`](../devlog/current.md)（最近任务记录）
5. [`../devlog/archive/`](../devlog/archive/README.md)（历史快照，可能过时）

冲突时以更靠前的来源为准；历史归档中的旧规则已被本手册和 `docs/README.md` 取代。

---

[文档总入口](../README.md) · [当前状态](../devlog/STATUS.md) · [当前日志](../devlog/current.md)
