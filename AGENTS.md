# Luker Launcher Agent 工作说明

> 本文件是进入本仓库的默认工作说明。用户只给任务时，按本文件执行。
> 文档体系入口：[`docs/README.md`](docs/README.md)；架构手册：[`docs/handbook/README.md`](docs/handbook/README.md)；日常状态：[`docs/devlog/STATUS.md`](docs/devlog/STATUS.md)。

## 1. 开始前必读（按顺序）

1. `docs/README.md`：两类文档、阅读路径、旧章节映射。
2. `docs/handbook/README.md`，然后读 `01-baseline`、`02-architecture`、`03-decisions`、`04-components`。
3. `docs/devlog/STATUS.md`：当前状态、OPEN、TODO。
4. `docs/devlog/current.md` **最后 1 条** `DEV`。

按任务加读：

- 排障/回归：`docs/handbook/05-lessons.md`
- 测试/发布：`docs/handbook/06-testing.md`、`STATUS.md` §5
- 术语/配置：`docs/handbook/07-reference.md`
- 历史：先用 `docs/devlog/INDEX.md` 定位，**不要从头读** `docs/devlog/archive/`。
- 旧日志里的 `§N`：按 `docs/README.md#legacy-numbering` 映射到新文件。

## 2. 工作方式

- 写代码前先查 `docs/handbook/04-components.md`，优先复用现有组件/工具，避免重复造轮子。
- 做设计前查 `docs/handbook/03-decisions.md`（ADR），不要推翻已有决策；需要推翻时新增 ADR 并标注取代关系。
- 大改动先给 3–5 行方案和影响文件；小改动可直接做。
- 不改变 UI 行为、npm 参数、配置格式、窗口尺寸策略，除非任务明确要求。
- 不修改用户的 `launcher_config.json`；测试/冒烟用临时目录或假 Luker。
- 不把架构抽取和包文件搬家混在一个大提交里。
- 不恢复已移除的 GCL、主题卡片悬停放大、座右铭、日志窗口拖拽缩放（见 ADR-08/10/11/09）。

## 3. 完成标准

- 跑 `check.bat`（ruff format/check、mypy、unittest、coverage）；文档结构变化时跑 `python docs/tools/check_docs.py`。
- 在 `docs/devlog/current.md` **末尾**追加 `DEV-YYYYMMDD-NN`，模板见 `docs/devlog/README.md` 第 5 节。
- 更新 `docs/devlog/STATUS.md`：控制表、OPEN、TODO、交接摘要。
- 更新 `docs/devlog/INDEX.md`：当前条目加一行。
- 只有架构/决策/组件/测试基线等稳定知识变化时，才改 `docs/handbook/`，并在 `STATUS.md` 的“文档修订与勘误”记录。
- 归档只读；发现错误写 `STATUS.md` 勘误，不改归档正文。

## 4. 提交约束

- 作者/提交者仅 `Yaoyao <jiayinyao24@outlook.com>`。
- 必须 GPG 签名；`git log -1 --format='%G?'` 必须为 `G`。
- 不加 `Co-authored-by`、`Signed-off-by` 或 AI/GPT 署名。
- 不推送、不打标签、不发布，除非用户明确要求。

## 5. 最终回报（5 项）

1. 改动文件
2. 验证命令与结果（`check.bat` 的测试数/覆盖率）
3. 未完成/风险
4. 新增的 `DEV` ID；`STATUS.md`/`INDEX.md` 是否已更新
5. 是否改过 `docs/handbook/`，以及原因

## 6. 常用任务路由

| 用户说 | 你怎么做 |
|---|---|
| “做 STATUS 里的 TODO-xx” | 在 `STATUS.md` §4 领取，状态改 `进行中`；完成后改 `已完成` 并追加 `DEV` |
| “查 DEV-xxx / ADR-xx / LSN-xx” | 用 `docs/devlog/INDEX.md` 定位；ADR/LSN 在 `docs/handbook/03`/`05` |
| “接手继续” | 从 `docs/devlog/current.md` 最后一条的“遗留/下一步”开始 |
| “发布/打包” | 严格按 `STATUS.md` §5；未确认不 bump/build/tag |
| “只查资料” | 只读不改；不要写 `DEV`，除非用户要求记录 |

## 7. 文档边界

- `docs/handbook/`：稳定知识，低频更新。
- `docs/devlog/`：状态、TODO、只追加日志、归档。
- `docs/devlog/archive/`：历史正文，只读。
- `.zcode/`：本地工作区，不随仓库分发；不要把它当事实源。

---

最后更新：2026-11-14。
