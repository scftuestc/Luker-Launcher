# 当前开发日志（未归档）

<a id="devlog-current"></a>

> **文档类型**：只追加开发日志（当前窗口，日常写入目标）
> **唯一写入点**：本文件末尾的追加点
> **写作规范**：[`README.md`](README.md)（ID、词表、模板、轮转）
> **条目索引**：[`INDEX.md`](INDEX.md)
> **历史归档**：[`archive/README.md`](archive/README.md)
> **事实截止**：2026-11-14
>
> 本文件只保留尚未归档的 `DEV` 条目；已归档条目的正文在 `archive/01`/`02`。
> 2026-11-14 拆分前的章节编号（§0–§10）对照见 [`../README.md#legacy-numbering`](../README.md#legacy-numbering)。

---

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

<a id="dev-20261114-11"></a>
#### DEV-20261114-11 | 文档体系拆分为架构手册与开发日志两类

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 分支 | ai-gijika |
| 提交 | 随本次 `docs:` 提交（见 `git log -- docs/`） |
| 类型 | docs |
| 状态 | 已完成 |
| 关联 | HB-01–HB-07、DL-INDEX、DL-STATUS |
| 证据等级 | [已验证] |

**目标/背景**

- 单文件 `development-handbook.md` 1,442 行，稳定知识与日常状态/日志混在一起，阅读和写入成本高。
- 01–04 归档按版本段拆得过细，导航和轮转需要改多份冻结文件。

**改动**

- 新增 `docs/handbook/`：README + 01 基线、02 架构、03 ADR、04 组件、05 LSN、06 测试、07 附录；保留旧 `§` 编号与 `sec-N` 锚点，便于历史日志定位。
- 新增 `docs/devlog/`：README（写作契约/ID/模板/轮转）、STATUS（状态/OPEN/TODO/发布/勘误）、current（只追加 DEV）、INDEX（条目/提交/ADR/LSN 索引）。
- 归档合并：`archive/01`+`02` → `01-v1.0-v3.3.md`（13 条）；`03`+`04` → `02-v3.4-v4.0.md`（10 条）；`00` 快照保留为 `archive/00-detailed-handbook-2026-11-14.md`。
- 删除 `docs/development-handbook.md` 与旧 `docs/archive/01`–`04`，避免双源。
- 更新 `docs/README.md`、根 `README.md`、`docs/tools/check_docs.py`、`tests/test_docs.py`。

**验证**

- `python docs/tools/check_docs.py`：`docs structure: OK`。
- `check.bat`：772 tests / 75% / 126 files；ruff format/check、mypy 通过。
- 23 条归档锚点全部保留；归档计数 13+10；INDEX 与 current/归档一致；相对链接可解析。
- 未改生产代码/测试（除文档校验器）；未改用户配置。

**决策/风险**

- 稳定知识（handbook）与动态记录（devlog）分离；日常只写 devlog，避免每次任务改架构手册。
- 归档按“早期（v1.0–v3.3）/近期（v3.4–v4.0）”两册合并，未来按 `03-...` 轮转，减少分册数量。
- 旧日志中的 `§` 与旧路径不改，通过 `docs/README.md#legacy-numbering` 映射；历史正文保持可追溯。
- 移除单文件手册是路径变更；仓库内所有入口已更新，旧链接统一从 `docs/README.md` 进入。

**遗留/下一步**

- 发布验证/真实 DPI/真实更新仍为 TODO-01/02/04。
- 下一条 `DEV-20261114-12`。

---

> 下一条日志 ID：`DEV-20261114-12`。追加后请更新 [`STATUS.md`](STATUS.md) 和 [`INDEX.md`](INDEX.md)；只有稳定知识变化时才改 [`../handbook/`](../handbook/README.md)。
>
> **追加点（本行之后）**：

<!-- ===== 新开发日志追加点：请在本行之后追加下一条 DEV 记录（复制 README.md 模板） ===== -->
