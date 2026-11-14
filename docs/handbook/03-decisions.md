# 关键设计决策（ADR）

> **文档类型**：架构手册（稳定知识，低频更新）
> **文档编号**：`HB-03`
> **对应旧章节**：§3（2026-11-14 拆分前）
> **内容**：不可轻易推翻的设计决策与“不要做”清单
> **更新时机**：新决策或被取代时
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md`；高于历史归档。
> **导航**：[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)

---

<a id="sec-3"></a>
## 3. 关键设计决策（ADR）

> 新决策追加 ADR；旧 ADR 不删除，标注“被 ADR-xx 取代”。详细背景见完整历史归档。

| ADR | 决策 | 原因/后果 | 不要做 | 证据 |
|---|---|---|---|---|
| <a id="adr-01"></a>ADR-01 | 用 `node server.js`，不通过 `Start.bat` | 需要传 `--browserLaunchEnabled false`；停止/日志可控 | 不要改回 `Start.bat` | `process/managers.py:339-345` |
| <a id="adr-02"></a>ADR-02 | Job Object + 单实例 | 防止强杀后 node 占端口；防止双启动器抢端口 | 不要移除 Job Object/只 terminate 父进程 | `process/job.py`、`single_instance.py` |
| <a id="adr-03"></a>ADR-03 | 后台线程统一经 `UiDispatcher` 回主线程 | Tk 非线程安全；完成回调不能丢 | 不要在后台直接碰 Tk/用普通队列投递完成回调；退出 `finish_exit` 也走 `post_control` | `ui/dispatch.py` |
| <a id="adr-04"></a>ADR-04 | 就绪=连续 2 次成功 + READY 粘滞 | 进程活≠服务可用；避免呼吸灯抖动 | 不要每次探测直接 apply | `services/readiness.py` |
| <a id="adr-05"></a>ADR-05 | 配置归一化/原子写入/BOM/端口缓存 | 手改配置、半截写入、每秒读盘 | 不要用 yaml 整体解析只取端口 | `config.py` |
| <a id="adr-06"></a>ADR-06 | 路径切换只在停止时进行 | 运行中热切换会中断/端口冲突 | 不要运行中替换 manager | `process_coordinator.py:56-75` |
| <a id="adr-07"></a>ADR-07 | 更新固定完整 SHA、dirty 检查、可回滚 | 防注入、防意外提交、半更新可恢复；已补 Start.bat 的 `storage:install-sqlite` 条件步骤 | 不要改 npm 参数/短 SHA/给 node 加 NODE_ENV | `services/version.py:734-808` |
| <a id="adr-08"></a>ADR-08 | 移除 GCL | 无端口探测/健康检查/多实例，接受 Luker `Start.bat` 会重复启动 | 不要重新引入 | `b840bf1` |
| <a id="adr-09"></a>ADR-09 | 日志窗口固定尺寸 | 主题/立绘对尺寸敏感；跨屏仍适配 | 不要未经确认恢复拖拽缩放 | `log_window.py:242` |
| <a id="adr-10"></a>ADR-10 | 主题卡片悬停放大已回滚 | 残影修复成本高；现在只颜色过渡 | 不要加回 relwidth/图片放大 | `e9bc44f` |
| <a id="adr-11"></a>ADR-11 | 座右铭已移除 | 视觉迭代最终决策 | 不要加回 | `a7a1c68` |
| <a id="adr-12"></a>ADR-12 | 门禁只在本地 | Windows 托盘/Win32/DPI 需要 Windows 环境；提交只记录“本地执行” | 不要恢复远程 CI 并声称覆盖托盘 | `43476f0` |
| <a id="adr-13"></a>ADR-13 | CTk 私有接口隔离 + 版本锁 | 6.0 已实测；6.1 Text 接口可能变；已接受 `_canvas`/`_draw_engine`、`_get_textbox`、`_get_widget_scaling`、`ScalingTracker.get_window_dpi_scaling`/`window_dpi_scaling_dict`，全部集中在 `ui/ctk_adapter.py` | 不要新增分散的私有访问；集中到适配层 | `ui/ctk_adapter.py` |
| <a id="adr-14"></a>ADR-14 | 主题颜色与元数据分离 | 渐变只处理颜色，避免把 name/icon 当颜色 | 不要整个 `PRESET_THEMES` 传给渐变 | `theme.py:256-262` |
| <a id="adr-15"></a>ADR-15 | 版本/打包一起验证，发布需确认 | v4.0 后 20 个产品提交（含 README-only `fc06d38`）未 bump；直接发布会版本重复 | 不要未经确认 bump/构建/打标签 | `config.py:25` |

**补充说明**：

- ADR-12 的“Windows 环境原因”是 `[推断]`；提交 `43476f0` 只写“门禁改为只在本地执行”。
- ADR-10 的“修复成本高”是根据回滚结果 `[推断]`；事实是悬停放大已回滚。

> 新 ADR 追加到表末；下一条 `ADR-16`。模板：`| ADR-16 | 决策 | 原因/后果 | 不要做 | 证据 |`；被取代时新增 ADR 并写“取代 ADR-xx”。

---

[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)
