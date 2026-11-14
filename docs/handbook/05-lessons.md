# 历史经验库（LSN）

> **文档类型**：架构手册（稳定知识，低频更新）
> **文档编号**：`HB-05`
> **对应旧章节**：§5（2026-11-14 拆分前）
> **内容**：踩过的坑、根因、修复与提交
> **更新时机**：新增教训时
> **事实截止**：2026-11-14
> **权威性**：低于代码/测试/根 `README.md`；高于历史归档。
> **导航**：[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)

---

<a id="sec-5"></a>
## 5. 历史经验库（LSN）

> 新教训追加 `LSN-24` 及以后；模板：`| LSN-24 | 现象 | 根因 | 修复/现状 | 提交 |`；不要删除旧条目。

| ID | 现象 | 根因 | 修复/现状 | 提交 |
|---|---|---|---|---|
| <a id="lsn-01"></a>LSN-01 | 日志时间戳错乱、清空后旧日志复现、GCL 日志饥饿 | 日志读取/队列/清空没有统一所有权 | `LogStore`+`BoundedLogQueue`+`LogController`；清空同时丢队列 | `4c91e77`、`60b7690` |
| <a id="lsn-02"></a>LSN-02 | 启停 Luker 时界面卡住 | 主线程同步 `Popen/stop` | 后台线程 + `TaskRunner` | `6d2e987` |
| <a id="lsn-03"></a>LSN-03 | 主题切换后旧回调操作已销毁控件 | 回调注册/注销不完整 | `add/remove_*_callback` + 销毁移除 | `b412050` |
| <a id="lsn-04"></a>LSN-04 | 托盘/进程线程直接操作 Tk 随机崩溃 | Tk 非线程安全 | `UiDispatcher` | `c7ff0b6` |
| <a id="lsn-05"></a>LSN-05 | 托盘图标消失/重复/残影 | HICON 生命周期/Explorer 重启/消息循环 | 新图标生效再释放旧；`TaskbarCreated`；stop 兜底 | `c7ff0b6`、`3260c48` |
| <a id="lsn-06"></a>LSN-06 | 64 位 Windows 句柄偶发异常 | ctypes 未声明 restype，按 C int 截断 | `infrastructure/win32.py` 集中声明 | `b3a7066`、`77b9a75` |
| <a id="lsn-07"></a>LSN-07 | 启动器强杀后 node 占端口 | 无 Job Object 兜底 | `KILL_ON_JOB_CLOSE` | `6f2258d` |
| <a id="lsn-08"></a>LSN-08 | 150% 下立绘过大/裁切 | 物理 `winfo_*` 传给逻辑 `CTkImage(size)` | 除以 `_get_widget_scaling()`；缓存含 scale | `16dbd3f` |
| <a id="lsn-09"></a>LSN-09 | 长时间运行内存上涨 | 日志队列/存储无上限 | 条数+字节上限；搜索结果上限 | `a8f9b5e` |
| <a id="lsn-10"></a>LSN-10 | 打开日志窗口卡顿 | 一次性插入全部历史 | 200 条/批、1ms 让出 | `f93b14f` |
| <a id="lsn-11"></a>LSN-11 | 实时日志到达搜索跳回第一条 | 每次全量重跑并重置当前项 | 250ms 合并；保留结果/视口 | `8f3f84b` |
| <a id="lsn-12"></a>LSN-12 | 关闭设置窗口后其他滚动区滚轮失效 | CTkScrollableFrame `bind_all` 不解绑 | `clear_scroll_bindings()` + 单设置窗口不变量 | `994ce62` |
| <a id="lsn-13"></a>LSN-13 | CTk 升级后开关/文本失效 | 依赖 `_canvas`/`_draw_engine`/`_textbox` | `CtkSwitchAdapter` + 版本锁 | `5a41744` |
| <a id="lsn-14"></a>LSN-14 | 副屏在左/上时窗口跑到另一端 | Tk 把 `-100` 当距右/下偏移 | `format_geometry()` 输出 `+-100` | `fe149c4` |
| <a id="lsn-15"></a>LSN-15 | 标题栏空白不能拖动 | Tk 事件不冒泡 | `bind_window_drag()` 绑所有子控件 | 早期版本 |
| <a id="lsn-16"></a>LSN-16 | `check.bat` 门禁失败却继续/静默中断 | `.bat` 包装器不返回 | 全部 `call python ...` + 失败传播测试 | `3966429` |
| <a id="lsn-17"></a>LSN-17 | 更新提交号可能被 git 当选项 | 短 SHA/任意字符串拼命令 | 只接受完整 40 位 SHA | `7e50e68` |
| <a id="lsn-18"></a>LSN-18 | npm 安装环境与 Start.bat 不一致 | 少 `NODE_ENV=production` | 只给 npm 安装补，不改 node 运行 | `79e2a78` |
| <a id="lsn-19"></a>LSN-19 | 主题卡片悬停残影 | 快速进出/滚轮/Leave 指针校准复杂 | 回滚放大，只颜色过渡 | `b6ce9f5`、`e9bc44f` |
| <a id="lsn-20"></a>LSN-20 | 退出线程失败残留 Luker | 失败分支没 `stop_all()` | 主线程同步 stop + finally 退出 | `707dd44` |
| <a id="lsn-21"></a>LSN-21 | 组合根构造期回调访问未初始化 `_status` | lambda 延迟绑定/构造顺序 | `getattr(...,None)` + 测试 | `3ad154f` |
| <a id="lsn-22"></a>LSN-22 | 打包后图片缺失但测试通过 | 只查 spec 文本/源文件 | 解析 datas 目标目录断言 | `3966429` |
| <a id="lsn-23"></a>LSN-23 | 座右铭/字体/立绘反复 | 产品视觉迭代 | 最终移除座右铭；保留左渐隐/320 面板 | `a512226`…`a7a1c68` |

---

[手册目录](README.md) · [文档总入口](../README.md) · [当前状态](../devlog/STATUS.md)
