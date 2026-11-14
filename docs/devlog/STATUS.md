# 当前状态与行动队列

> **文档类型**：日常开发维护（动态；每次任务更新）
> **文档编号**：`DL-STATUS`
> **事实截止**：2026-11-14
> **当前日志**：[`current.md`](current.md) · **条目索引**：[`INDEX.md`](INDEX.md) · **写作规范**：[`README.md`](README.md)
> **导航**：[文档总入口](../README.md) · [架构手册](../handbook/README.md)

本文件是**当前事实、风险和待办的唯一来源**；架构知识在 [`../handbook/`](../handbook/README.md)，历史在 [`archive/`](archive/README.md)。

## 1. 交接摘要（每次交接更新）

- **当前状态**：`ai-gijika`（最后代码提交 `f3ffd54`；文档提交见 `git log`）；`origin/ai-gijika` 落后本地、未推送；工作区 clean；772 tests / 75% / `check.bat` pass。
- **最近完成**：文档体系拆分为 `handbook/`（稳定架构知识）+ `devlog/`（状态/日志）；01–04 归档合并为两册；新增根 `AGENTS.md` 固化 agent 开工说明。
- **当前阻塞**：`APP_VERSION` 仍为 4.0；HEAD 未 bump、未构建 exe、未在真实 125%/150% 设备验收；是否发布需用户确认。
- **建议下一步**：先确认是否发布；若发布，按 `TODO-01` 做版本 bump + 构建 + 100%/125%/150% 验收。不要先做大重构。
- **不要重复**：不要重新引入 GCL；不要恢复主题卡片悬停放大；不要加回座右铭；不要未经确认恢复日志窗口拖拽缩放；不要改 npm 参数；不要重建已删除的 `dev` 分支；不要恢复已拆分的单文件手册。
- **文档入口**：先读 [`docs/README.md`](../README.md)；日常只写本目录（`current.md` + `STATUS.md`）；架构查 [`../handbook/`](../handbook/README.md)；历史查 [`archive/`](archive/README.md)。

**常见问题速查**：

| 你可能问 | 看这里 |
|---|---|
| 某个能力是不是已经实现过？ | [`../handbook/04-components.md`](../handbook/04-components.md) |
| 为什么代码这样设计？ | [`../handbook/03-decisions.md`](../handbook/03-decisions.md) |
| 这个坑以前踩过吗？ | [`../handbook/05-lessons.md`](../handbook/05-lessons.md) |
| 现在还有什么没做？ | 本文 §3 OPEN + §4 TODO |
| 最近一次改了什么？ | [`current.md`](current.md) 末尾的 `DEV` 条目 |
| 发布前要做什么？ | 本文 §5 + [`../handbook/06-testing.md`](../handbook/06-testing.md) §8.4 |
| 详细历史在哪？ | [`archive/README.md`](archive/README.md) |

**最小必读（约 20 分钟）**：[`../handbook/README.md`](../handbook/README.md)、`01`、`02`、`03`、`04`，本文 §3/§4。不要从头读到尾。

**权威顺序**：代码/测试/根 `README.md` > [`../handbook/`](../handbook/README.md) > 本文 > [`current.md`](current.md) > [`archive/`](archive/README.md) > 本地工作记录。

## 2. 控制表

| 字段 | 当前值 | 更新时机 |
|---|---|---|
| 文档结构版本 | `5.0`（handbook + devlog 两类） | 结构调整时 |
| 最后更新 | `2026-11-14` | 每次追加日志 |
| 最新日志条目 | `DEV-20261114-12` | 每次追加日志 |
| 下一条日志 ID | `DEV-20261114-13` | 每次追加日志 |
| 代码分支 / 最后代码提交 | `ai-gijika` / `f3ffd54` | 每次任务开始/结束 |
| 产品 / 代码修复提交 | 193 基线产品 + 3 代码修复 + 文档提交（见 `git log`） | 每次任务结束 |
| 标签 | 17 本地 / 16 远程；`v3.5` 仅本地 | 发布/标签变化时 |
| 当前版本 | `APP_VERSION = 4.0` | 版本 bump 时 |
| 工作区状态 | clean（文档改动随任务提交） | 每次任务结束 |
| 质量基线 | 772 tests / 75% / `check.bat` pass | 每次任务结束 |
| 历史归档 | 23 条已归档 + 当前 10 条；两册 + 00 快照 | 轮转时 |

## 3. 开放问题与技术债（OPEN）

> 只登记未排期风险/技术债；可执行任务在 §4。排期后写 `tracked as TODO-xx`，不重复优先级/状态。

| ID | 事项 | 影响 | 证据 | 建议 | 处置 |
|---|---|---|---|---|---|
| OPEN-01 | `APP_VERSION` 仍 4.0，HEAD 未构建 | 发布阻塞 | `config.py:25`、`version_info.txt` | 发布前 bump 4.1 + 构建 + 验证；先问用户 | tracked as TODO-01 |
| OPEN-02 | 真实 125%/150% 未验收 | 视觉/DPI 风险 | 只有模拟截图 | 真实设备跑 `06-testing` §8.4 | tracked as TODO-02 |
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
| 单文件手册拆分（本次） | 2026-11-14 | 已拆为 `handbook/` + `devlog/`，不要恢复 |

## 4. 行动队列（TODO）

> 唯一行动队列。领取时状态改 `进行中`，在 §2 记 HEAD；完成后改 `已完成` 并追加 `DEV` 日志。

| ID | 关联 OPEN | 优先级 | 任务 | 验收标准 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| TODO-01 | OPEN-01 | P1 | 发布验证 4.1 | bump + `build.bat` + 100/125/150% 主题/立绘/日志/设置正常 + 资源可读 | 用户确认发布 | 待确认 |
| TODO-02 | OPEN-02 | P2 | 真实高 DPI 验收 | 真实 125/150% 设备跑 `06-testing` §8.4；记录截图/尺寸 | 设备 | 待开始 |
| TODO-03 | OPEN-03 | P2 | 完整 exe 构建冒烟 | `build.bat` 0；`_MEIPASS` 资源存在；启动无资源告警 | PyInstaller | 待开始 |
| TODO-04 | OPEN-04 | P2 | 真实 npm 更新（含 SQLite 扩展） | 一次性副本；成功/失败回滚/依赖恢复；原生模块缺失时补装成功；不动主安装 | 用户授权副本 | 待开始 |
| TODO-05 | OPEN-05 | P3 | 固定日志窗口最终决策 | 用户确认；若否删除 `resizable=True` 分支及测试 | 产品确认 | 待确认 |
| TODO-06 | OPEN-06 | P3 | 抽 `refit_window_to_monitor()` | 两窗口共用；行为不变；补测试 | 无 | 待开始 |
| TODO-07 | OPEN-07 | P3 | 滚动绑定实例级解绑 | 关闭设置窗口不影响其他滚动区；补测试 | CTk 方案 | 待开始 |
| TODO-08 | OPEN-08 | P3 | 复用 `StepTicker` 统一悬停动画 | 颜色过渡不变；少一套状态机 | 无 | 待开始 |
| TODO-09 | OPEN-09 | P3 | 大 UI 文件按需小步提取 | 只在必然修改时做；行为不变；先补测试 | 实际需求 | 待开始 |

## 5. 发布前检查（按顺序）

1. 用户确认发布；确认目标版本（当前建议 4.1）。
2. `config.APP_VERSION` 与 `version_info.txt` 同步。
3. `check.bat` 通过。
4. `build.bat` 成功；检查 `_MEIPASS` 资源。
5. 100%/125%/150% 手工冒烟（[`06-testing.md`](../handbook/06-testing.md) §8.4）。
6. 真实 npm 更新 + SQLite 扩展在一次性副本验证（TODO-04）。
7. 打标签/发布前再次确认；默认不推送。

## 6. 文档修订与勘误

**修订记录**：

| 日期 | 版本 | 修改人 | 说明 |
|---|---|---|---|
| 2026-11-14 | 1.0 | 上一轮审查 | 初版叙述式历史文档（994 行） |
| 2026-11-14 | 2.0 | ZCode | 重构为“稳定知识 + 只追加日志”；修正 v1.2/v2.0 提交区间 |
| 2026-11-14 | 3.0 | ZCode | 精简主文档；完整细节归档 |
| 2026-11-14 | 4.0 | 文档维护 | 迁入 `docs/` 并纳入 Git；拆 00–04 分册 |
| 2026-11-14 | 5.0 | 文档维护 | 拆为 `handbook/`（HB-01–07）+ `devlog/`（STATUS/current/INDEX/archive）；01–04 归档合并为 01–02；移除单文件手册 |

**勘误（只追加，不改旧日志正文）**：

| 日期 | 影响条目 | 原内容 | 更正 |
|---|---|---|---|
| 2026-11-14 | 旧 §1.5 `v1.1` | `206c1d1..38be292` 写 10 个 | 10 是 `v1.0..v1.1` 区间计数；`206c1d1` 之后是 9 个提交，加前一条 `DEV-20261002-02` 才是 10 |
| 2026-11-14 | 旧 §1.5 `v2.0` / `v3.5` | 日期分别写 2026-10-19 / 2026-11-03 | 条目跨日：v2.0 为 2026-10-18~19；v3.5 为 2026-11-03~04 |
| 2026-11-14 | 旧 §1.6 | `ruff format` 106/118 个文件 | 格式化文件计数随环境变化；以 `check.bat` 实测为准 |
| 2026-11-14 | 旧 §1.4 | “17 个标签”未区分本地/远程 | 17 本地 / 16 远程；`v3.5` 仅本地，`v3.5.0` 远程，同提交 `ec0b561` |
| 2026-11-14 | ADR-15 | “v4.0 后 19 提交未 bump” | `v4.0..a7a1c68` 共 20 个产品提交（含 README-only `fc06d38`） |
| 2026-11-14 | 旧归档路径 | `archive/00`–`04` | 本轮合并为 `devlog/archive/00`（快照）+ `01`（v1.0–v3.3）+ `02`（v3.4–v4.0）；旧路径只存在于历史日志 |
| 2026-11-14 | 旧章节号 | 历史日志中的 `§0`–`§10` | 拆分后映射见 [`../README.md#legacy-numbering`](../README.md#legacy-numbering)；旧日志正文不改 |

---

[文档总入口](../README.md) · [架构手册](../handbook/README.md) · [当前日志](current.md) · [条目索引](INDEX.md)
