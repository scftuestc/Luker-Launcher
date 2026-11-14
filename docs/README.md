# Luker Launcher 文档

> 本目录随 Git 提交，是长期维护的开发文档区。
> `.zcode/reports/` 是本地工作区，不随仓库分发；其中的结论已并入本目录。

## 当前状态（2026-11-14）

| 字段 | 值 |
|---|---|
| 分支 / HEAD | `ai-gijika` / `d94308d`（docs） |
| 最后代码提交 | `a7a1c68` |
| 提交数 | 193 产品 + 2 文档 = 195 |
| 标签 | 17 本地 / 16 远程（`v3.5` 仅本地） |
| 版本 | `APP_VERSION = 4.0`（未 bump、未重新发布） |
| 质量基线 | 771 tests / 75% / `check.bat` pass |

## 先读哪一份

| 你的任务 | 读什么 |
|---|---|
| 接手项目、开始一个开发任务 | [`development-handbook.md`](development-handbook.md)（主手册） |
| 查某个能力是否已实现 | 主手册 §4 可复用组件目录 |
| 查某个设计为什么这样做 | 主手册 §3 ADR；需要完整论证时只查 [`archive/00-detailed-handbook-2026-11-14.md`](archive/00-detailed-handbook-2026-11-14.md) §3，不要整份读 |
| 查某个坑以前是否踩过 | 主手册 §5 经验库（LSN） |
| 查现在还有什么没做 | 主手册 §6 风险 + §7 行动队列 |
| 查某段历史/某版本的详细改动 | [`archive/README.md`](archive/README.md)，按版本段选分册 |
| 记录本次任务 | 只改主手册：§10 追加（模板见 §0.6），并更新 §0.2/§6/§7；§1–§5 仅在事实/决策/组件变化时改 |

## 10 分钟接手

1. 读主手册顶部：交接摘要、Quick facts、目录。
2. 读 §1（基线）、§2（架构）、§3（ADR）、§4（组件）、§6（风险）、§7（待办）。
3. 跑 `check.bat`，确认 771 tests / 75%；记录当前 HEAD。
4. 选一个 `TODO` 或用户任务；写代码前先查 §4，做设计前查 §3，遇到异常查 §5。
5. 任务结束按 §0.5/§0.6 追加 `DEV`，更新 §0.2/§6/§7，并随任务提交。

## 任务配方

| 任务 | 先读 | 常用入口 |
|---|---|---|
| UI / 主题 / 立绘 | §2.4 主题/DPI、§4.5 | `ui/log_window.py`、`ui/settings_window.py`、`theme.py`、`ui/tokens.py` |
| 进程 / 启停 / 退出 | §2.4、§4.1/§4.4 | `application/process_coordinator.py`、`process/managers.py`、`application/lifecycle_coordinator.py` |
| 版本检查 / 更新 | §2.4、ADR-07、§4.4 | `services/version.py`、`application/update_coordinator.py` |
| 日志 / 搜索 | §2.4、§4.3 | `log/`、`ui/log_view/` |
| 托盘 / 窗口 | §2.4、§4.5/§4.6 | `tray/icon.py`、`tray/menu.py`、`ui/dpi.py`、`ui/resizing.py` |
| 测试 / 门禁 | §8 | `tests/`、`check.bat`、`build.bat` |
| 发布 | §7 发布前检查 | `config.py`、`version_info.txt`、`build.bat` |
| 查历史 | `archive/README.md` | 按版本段选一册，不要从头读 |

## 写入契约（唯一）

日常任务只改主手册：

1. 在 §10 末尾追加 `DEV-YYYYMMDD-NN`（模板见 §0.6）。
2. 更新 §0.2 控制表、§6/§7 状态。
3. 只有事实/决策/组件变化时才改 §1–§5，并在 §0.9 记一行。
4. 归档不改；发现错误写主手册 §0.9 勘误，并引用旧条目。

## 权威顺序

1. 代码、测试、根 `README.md`（产品行为的最终依据）
2. `docs/development-handbook.md`（当前事实、决策、待办）
3. `docs/archive/`（历史快照，可能包含过时路径/规则）
4. `.zcode/reports/` 本地工作记录（不随仓库分发）

冲突时以更靠前的来源为准。归档中的旧规则（例如“文件不进入版本库”）已被主手册 §0 取代。

## 目录

| 文件 | 内容 | 读写 |
|---|---|---|
| [`README.md`](README.md) | 本文件：文档入口、阅读路径、写入契约 | 只读；结构变更时更新 |
| [`development-handbook.md`](development-handbook.md) | 主手册：稳定知识 + 风险/TODO + 只追加日志 | **唯一日常写入目标** |
| [`archive/README.md`](archive/README.md) | 归档契约、分册导航、快照边界、轮转清单 | 只读；轮转时更新 |
| `archive/INDEX.md` | DEV/提交/决策索引（批次 5 新增） | 只读；轮转时更新 |
| [`archive/00-detailed-handbook-2026-11-14.md`](archive/00-detailed-handbook-2026-11-14.md) | 2026-11-14 详细手册快照（§0–§9） | 只读 |
| [`archive/01-v1.0-v2.0-foundation.md`](archive/01-v1.0-v2.0-foundation.md) | v1.0–v2.0 基座期日志 | 只读 |
| [`archive/02-v2.1-v3.3-engineering.md`](archive/02-v2.1-v3.3-engineering.md) | v2.1–v3.3 工程化与视觉日志 | 只读 |
| [`archive/03-v3.4-v3.5-visual-reliability.md`](archive/03-v3.4-v3.5-visual-reliability.md) | v3.4–v3.5 设计令牌与可靠性日志 | 只读 |
| [`archive/04-v4.0-coordinator-themes-ui.md`](archive/04-v4.0-coordinator-themes-ui.md) | v4.0+ Coordinator/主题/UI 日志 | 只读 |
| `tools/check_docs.py` | 文档结构校验器（批次 6 新增） | 只读 |

## 维护规则

- **只改主手册**：日常任务不改 `docs/README.md` 和 `archive/README.md`；只有归档轮转或文档结构变更时才改索引。
- **归档只读**：不修改 `archive/` 下的历史正文；发现错误在主手册 §0.9 记勘误，并引用旧条目。
- **轮转**：主手册 §10 未归档的详细条目超过 30 条或主版本结束时，把较早条目的详细内容迁到 `docs/archive/05-...`，并更新 `archive/INDEX.md`/`archive/README.md`/§10.1/§10.2。
- **提交**：文档改动随任务提交；作者仅 `Yaoyao <jiayinyao24@outlook.com>`，GPG 签名，无 AI/Co-authored-by 署名；不推送、不打标签、不发布（除非用户明确要求）。

## 本地工具与数据

- `.zcode/reports/`、`.zcode/build_docs.py` 是本地临时文件，可能不存在或过时；**不要**用它们重新生成 `docs/`。文档以 Git 中的版本为准。
- 真实验证用一次性 Luker 副本；不要修改用户的 `launcher_config.json`。
