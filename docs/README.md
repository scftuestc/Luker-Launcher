# Luker Launcher 文档

> 本目录随 Git 提交，是长期维护的开发文档区。
> `.zcode/reports/` 仍是本地工作区，不随仓库分发；其中的结论已并入本目录。

## 先读哪一份

| 你的任务 | 读什么 |
|---|---|
| 接手项目、开始一个开发任务 | [`development-handbook.md`](development-handbook.md)（主手册） |
| 查某个能力是否已实现 | 主手册 §4 可复用组件目录 |
| 查某个设计为什么这样做 | 主手册 §3 ADR；需要完整论证时只查 [`archive/00-detailed-handbook-2026-11-14.md`](archive/00-detailed-handbook-2026-11-14.md) §3，不要整份读 |
| 查某个坑以前是否踩过 | 主手册 §5 经验库（LSN） |
| 查现在还有什么没做 | 主手册 §6 开放问题、§7 待办 |
| 查某段历史/某版本的详细改动 | [`archive/README.md`](archive/README.md)，按版本段选分册 |
| 记录本次任务 | 只改主手册：§10 追加（模板见 §0.6），并更新 §0.2/§6/§7；§1–§5 仅在事实/决策/组件变化时改 |

## Agent 最短路径

1. 读主手册顶部“交接摘要”和 §1（基线）、§2（架构）、§3（ADR）、§4（组件）、§6（开放问题）、§7（待办）。
2. 写代码前先在 §4 查是否已有组件；做设计前先在 §3 查是否已有决策；遇到异常先在 §5 查是否踩过。
3. 任务结束后在 §10 末尾追加 `DEV-YYYYMMDD-NN`，更新 §0.2 控制表、§6/§7 状态，并随任务提交；§1–§5 仅在事实/决策/组件变化时更新，归档不改，勘误写 §0.9。
4. 不要从 `archive/` 从头读到尾；只有主手册的摘要不够时才按版本段读一份。

## 权威顺序

1. 代码、测试、根 `README.md`（产品行为的最终依据）
2. `docs/development-handbook.md`（当前事实、决策、待办）
3. `docs/archive/`（历史快照，可能包含过时路径/规则）
4. `.zcode/reports/` 本地工作记录（不随仓库分发）

冲突时以更靠前的来源为准。归档中的旧规则（例如“文件不进入版本库”）已被主手册 §0 取代。

## 目录

| 文件 | 内容 | 读写 |
|---|---|---|
| [`README.md`](README.md) | 本文件：文档入口 | 只读；结构变更时更新 |
| [`development-handbook.md`](development-handbook.md) | 主手册：稳定知识 + 开放问题/TODO + 只追加日志 | **唯一日常写入目标** |
| [`archive/README.md`](archive/README.md) | 归档索引、分册导航、快照边界 | 只读 |
| [`archive/00-detailed-handbook-2026-11-14.md`](archive/00-detailed-handbook-2026-11-14.md) | 2026-11-14 详细手册快照（§0–§9） | 只读 |
| [`archive/01-v1.0-v2.0-foundation.md`](archive/01-v1.0-v2.0-foundation.md) | v1.0–v2.0 基座期日志 | 只读 |
| [`archive/02-v2.1-v3.3-engineering.md`](archive/02-v2.1-v3.3-engineering.md) | v2.1–v3.3 工程化与视觉日志 | 只读 |
| [`archive/03-v3.4-v3.5-visual-reliability.md`](archive/03-v3.4-v3.5-visual-reliability.md) | v3.4–v3.5 设计令牌与可靠性日志 | 只读 |
| [`archive/04-v4.0-coordinator-themes-ui.md`](archive/04-v4.0-coordinator-themes-ui.md) | v4.0+ Coordinator/主题/UI 日志 | 只读 |

## 维护规则

- **只改主手册**：日常任务不改 `docs/README.md` 和 `archive/README.md`；只有归档轮转或文档结构变更时才改索引。
- **归档只读**：不修改 `archive/` 下的历史正文；发现错误在主手册 §0.9 记勘误，并引用旧条目。
- **轮转**：主手册 §10 超过 30 条或主版本结束时，把较早条目的详细内容迁到 `docs/archive/05-...`，§10 保留摘要和链接。
- **提交**：文档改动随任务提交；作者仅 `Yaoyao <jiayinyao24@outlook.com>`，GPG 签名，无 AI/Co-authored-by 署名；不推送、不打标签、不发布（除非用户明确要求）。
