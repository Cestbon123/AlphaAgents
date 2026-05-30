# AlphaAgents 复盘案例持久化计划

日期：2026-05-12

## 背景

当前实际操作记录、选股快照、沉淀候选和结构化日报都已经写入 SQLite，但每日复盘生成的 `ReviewCase` 仍主要保存在运行时内存中。这样会影响日报、周报和后续偏差统计的稳定性，也不利于服务重启后的回看。

## 成功标准

1. 每日复盘生成的复盘案例写入 SQLite workflow 库。
2. 服务重启后可读取最新复盘案例。
3. Dashboard 返回持久化复盘案例，前端可以展示最新复盘案例。
4. 日报复盘摘要优先使用持久化复盘案例，包含偏差统计。
5. 复盘案例仍只用于投研复盘和决策辅助，不触发交易执行。

## 任务拆分

### 任务 1：后端持久化与 API

- SQLite workflow 仓储新增 `review_cases` 表。
- 新增 `save_review_cases(review_date, cases)`，按日期替换当天复盘案例。
- 新增 `list_review_cases(review_date=None)` 和 `get_latest_review_cases()`。
- 每日复盘生成 cases 后同步写入 SQLite。
- 新增 `GET /api/v1/review/cases`，支持可选 `review_date`。
- 新增 `GET /api/v1/review/cases/latest`。

### 任务 2：Dashboard 与日报接入

- Dashboard 返回 `review_cases`。
- 结构化日报的复盘摘要优先使用持久化复盘案例，展示案例数和偏差分布。

### 任务 3：前端展示

- 新增“复盘案例”区域，展示股票、系统结论、用户动作、偏差和关键原因。
- 页面初始化和每日复盘运行后刷新复盘案例。

### 任务 4：验证与文档

- 增加 API/仓储/前端静态测试。
- 运行完整测试和 JS 语法检查。
- 更新 `docs/project-status.md`。

