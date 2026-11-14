# Luker Launcher 开发文档

> 本目录随 Git 提交，是长期维护的开发文档区。
> `.zcode/reports/` 是本地工作区，不随仓库分发；其中的结论已并入本目录。

文档分为**两类**，职责不重叠：

| 类别 | 目录 | 内容 | 更新频率 | 谁写 |
|---|---|---|---|---|
| **架构手册** | [`handbook/`](handbook/README.md) | 项目基线、当前架构、ADR、可复用组件、经验、测试、附录 | 低（事实/决策/组件变化时） | 改架构的人 |
| **日常开发维护** | [`devlog/`](devlog/README.md) | 当前状态、OPEN 风险、TODO、交接摘要、只追加日志、历史归档 | 高（每个任务） | 每个任务执行者 |

> 当前分支、最后代码提交、质量基线、风险和待办以 [`devlog/STATUS.md`](devlog/STATUS.md) 为唯一来源；本文件不重复这些易变值。

## 1. 先读哪一份

| 你的任务 | 读什么 |
|---|---|
| 第一次接手、开始一个开发任务 | [`handbook/README.md`](handbook/README.md) → `01` → `02` → `03` → `04`；再看 [`devlog/STATUS.md`](devlog/STATUS.md) |
| 查某个能力是否已实现 | [`handbook/04-components.md`](handbook/04-components.md) |
| 查某个设计为什么这样做 | [`handbook/03-decisions.md`](handbook/03-decisions.md)；完整论证查 [`devlog/archive/00`](devlog/archive/00-detailed-handbook-2026-11-14.md) §3 |
| 查某个坑以前是否踩过 | [`handbook/05-lessons.md`](handbook/05-lessons.md) |
| 查现在还有什么没做 | [`devlog/STATUS.md`](devlog/STATUS.md) §3 OPEN + §4 TODO |
| 查最近一次改了什么 | [`devlog/current.md`](devlog/current.md) 末尾的 `DEV` 条目 |
| 查某段历史/某版本的详细改动 | [`devlog/archive/README.md`](devlog/archive/README.md)，按版本段选一册 |
| 记录本次任务 | 只写 [`devlog/current.md`](devlog/current.md) + [`devlog/STATUS.md`](devlog/STATUS.md) + [`devlog/INDEX.md`](devlog/INDEX.md) |

## 2. 10 分钟接手

1. 读 [`handbook/README.md`](handbook/README.md) 的文档地图。
2. 读 [`handbook/01-baseline.md`](handbook/01-baseline.md)、[`02-architecture.md`](handbook/02-architecture.md)、[`03-decisions.md`](handbook/03-decisions.md)、[`04-components.md`](handbook/04-components.md)。
3. 读 [`devlog/STATUS.md`](devlog/STATUS.md) 的交接摘要、OPEN、TODO。
4. 跑 `check.bat`，确认测试数/覆盖率；记录当前 HEAD。
5. 选一个 `TODO` 或用户任务；写代码前查 `04`，做设计前查 `03`，遇到异常查 `05`。
6. 任务结束按 [`devlog/README.md`](devlog/README.md) 第 2 节追加 `DEV`，更新 `STATUS.md` 和 `INDEX.md`，并随任务提交。

## 3. 任务配方

| 任务 | 先读 | 常用入口 |
|---|---|---|
| UI / 主题 / 立绘 | HB-02 §2.4、HB-04 §4.5 | `ui/log_window.py`、`ui/settings_window.py`、`theme.py`、`ui/tokens.py` |
| 进程 / 启停 / 退出 | HB-02 §2.4、HB-04 §4.1/§4.4 | `application/process_coordinator.py`、`process/managers.py`、`application/lifecycle_coordinator.py` |
| 版本检查 / 更新 | HB-02 §2.4、ADR-07、HB-04 §4.4 | `services/version.py`、`application/update_coordinator.py` |
| 日志 / 搜索 | HB-02 §2.4、HB-04 §4.3 | `log/`、`ui/log_view/` |
| 托盘 / 窗口 | HB-02 §2.4、HB-04 §4.5/§4.6 | `tray/icon.py`、`tray/menu.py`、`ui/dpi.py`、`ui/resizing.py` |
| 测试 / 门禁 | HB-06 | `tests/`、`check.bat`、`build.bat` |
| 发布 | STATUS §5 | `config.py`、`version_info.txt`、`build.bat` |
| 查历史 | [`devlog/archive/README.md`](devlog/archive/README.md) | 按版本段选一册，不要从头读 |

> HB-01–HB-07 的编号与“旧章节”对照见 [`handbook/README.md`](handbook/README.md)。

## 4. 写入契约（唯一）

日常任务只写 `devlog/`：

1. 在 [`devlog/current.md`](devlog/current.md) 末尾追加 `DEV-YYYYMMDD-NN`（模板见 [`devlog/README.md`](devlog/README.md) 第 5 节）。
2. 更新 [`devlog/STATUS.md`](devlog/STATUS.md)：控制表、OPEN、TODO、交接摘要。
3. 在 [`devlog/INDEX.md`](devlog/INDEX.md) 的“当前条目”加一行。
4. **只有稳定知识变化时**才改 [`handbook/`](handbook/README.md)：架构→`02`，决策→`03`，组件→`04`，教训→`05`，测试→`06`，基线→`01`，术语→`07`；并在 `STATUS.md` 的“文档修订与勘误”记一行。
5. 归档不改；发现错误写 `STATUS.md` 勘误，并引用旧条目。

## 5. 权威顺序

1. 代码、测试、根 `README.md`（产品行为的最终依据）
2. [`handbook/`](handbook/README.md)（当前架构、决策、组件、经验）
3. [`devlog/STATUS.md`](devlog/STATUS.md)（当前状态、风险、TODO）
4. [`devlog/current.md`](devlog/current.md)（最近任务记录）
5. [`devlog/archive/`](devlog/archive/README.md)（历史快照，可能包含过时路径/规则）
6. `.zcode/reports/` 本地工作记录（不随仓库分发）

冲突时以更靠前的来源为准。归档中的旧规则（例如“文件不进入版本库”）已被本目录取代。

<a id="legacy-numbering"></a>
## 6. 旧章节映射（2026-11-14 拆分前）

历史日志和归档里的 `§N` / `§N.M` 指拆分前的单文件手册；按下表定位，`§N.M` 对应该文件内的 `N.M` 小节。

| 旧章节 | 现在的位置 |
|---|---|
| `§0` 文档使用规范 | 本文件 + [`devlog/README.md`](devlog/README.md) |
| `§1` 项目基线 | [`handbook/01-baseline.md`](handbook/01-baseline.md) |
| `§2` 当前架构 | [`handbook/02-architecture.md`](handbook/02-architecture.md) |
| `§3` 设计决策（ADR） | [`handbook/03-decisions.md`](handbook/03-decisions.md) |
| `§4` 可复用组件 | [`handbook/04-components.md`](handbook/04-components.md) |
| `§5` 历史经验（LSN） | [`handbook/05-lessons.md`](handbook/05-lessons.md) |
| `§6` 开放问题/技术债 | [`devlog/STATUS.md`](devlog/STATUS.md) §3 |
| `§7` 待办与下一步 | [`devlog/STATUS.md`](devlog/STATUS.md) §4 |
| `§8` 测试与验证 | [`handbook/06-testing.md`](handbook/06-testing.md) |
| `§9` 术语与附录 | [`handbook/07-reference.md`](handbook/07-reference.md) |
| `§10` 开发日志 | [`devlog/current.md`](devlog/current.md) + [`devlog/INDEX.md`](devlog/INDEX.md) |

## 7. 目录

| 文件 | 内容 | 读写 |
|---|---|---|
| [`README.md`](README.md) | 本文件：两类文档、阅读路径、写入契约、旧章节映射 | 只读；结构变更时更新 |
| [`handbook/README.md`](handbook/README.md) | 架构手册目录、阅读路径、更新规则 | 只读；结构变更时更新 |
| [`handbook/01-baseline.md`](handbook/01-baseline.md) | HB-01 项目基线（旧 §1） | 低频 |
| [`handbook/02-architecture.md`](handbook/02-architecture.md) | HB-02 当前架构（旧 §2） | 低频 |
| [`handbook/03-decisions.md`](handbook/03-decisions.md) | HB-03 ADR（旧 §3） | 低频 |
| [`handbook/04-components.md`](handbook/04-components.md) | HB-04 可复用组件（旧 §4） | 低频 |
| [`handbook/05-lessons.md`](handbook/05-lessons.md) | HB-05 历史经验 LSN（旧 §5） | 低频 |
| [`handbook/06-testing.md`](handbook/06-testing.md) | HB-06 测试与验证（旧 §8） | 低频 |
| [`handbook/07-reference.md`](handbook/07-reference.md) | HB-07 术语与附录（旧 §9） | 低频 |
| [`devlog/README.md`](devlog/README.md) | 写作契约、ID registry、词表、模板、轮转 | 低频 |
| [`devlog/STATUS.md`](devlog/STATUS.md) | 当前状态、OPEN、TODO、发布检查、勘误 | **每个任务** |
| [`devlog/current.md`](devlog/current.md) | 未归档 DEV 日志（只追加） | **每个任务** |
| [`devlog/INDEX.md`](devlog/INDEX.md) | DEV/提交/ADR/LSN 索引 | 新增条目时 |
| [`devlog/archive/README.md`](devlog/archive/README.md) | 归档契约、分册导航、阅读地图、轮转清单 | 轮转时 |
| [`devlog/archive/00-detailed-handbook-2026-11-14.md`](devlog/archive/00-detailed-handbook-2026-11-14.md) | 拆分前详细手册快照（只读） | 只读 |
| [`devlog/archive/01-v1.0-v3.3.md`](devlog/archive/01-v1.0-v3.3.md) | v1.0–v3.3 历史日志（13 条） | 只读 |
| [`devlog/archive/02-v3.4-v4.0.md`](devlog/archive/02-v3.4-v4.0.md) | v3.4–v4.0 历史日志（10 条） | 只读 |
| [`tools/check_docs.py`](tools/check_docs.py) | 文档结构校验器；由 `tests/test_docs.py` 纳入门禁 | 只读 |

## 8. 维护规则

- **两类分开**：稳定知识写 `handbook/`，日常状态/日志写 `devlog/`；不要把逐阶段长日志写进架构手册。
- **归档只读**：不修改 `devlog/archive/` 下的历史正文；发现错误在 `STATUS.md` 记勘误，并引用旧条目。
- **轮转**：`devlog/current.md` 未归档条目超过 30 条或主版本结束时，把较早条目迁到 `devlog/archive/03-...`，并更新 `INDEX.md`/`archive/README.md`/`STATUS.md`。
- **提交**：文档改动随任务提交；作者仅 `Yaoyao <jiayinyao24@outlook.com>`，GPG 签名，无 AI/Co-authored-by 署名；不推送、不打标签、不发布（除非用户明确要求）。

## 9. 本地工具与数据

- `.zcode/reports/`、`.zcode/build_docs.py` 是本地临时文件，可能不存在或过时；**不要**用它们重新生成 `docs/`。文档以 Git 中的版本为准。
- 真实验证用一次性 Luker 副本；不要修改用户的 `launcher_config.json`。
- 文档结构检查：`python docs/tools/check_docs.py`（`check.bat` 会通过 `tests/test_docs.py` 执行）。
