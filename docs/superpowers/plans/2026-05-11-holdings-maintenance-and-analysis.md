# 持仓维护与本地行情持股分析计划

> **给代理工程师：** 执行本计划时使用 `superpowers:subagent-driven-development`，每个实现任务先写测试，再实现；不要回滚已有未提交改动。

**目标：** 在 AlphaAgents MVP 中补齐“手动维护持仓 -> 执行持股分析 -> 前端展示结果”的最小闭环。系统仍只做投研、复盘、分析和决策辅助，不执行交易。

**范围：**

- 支持用户在本地维护持仓列表：代码、数量、成本价、持仓天数。
- 持仓数据持久化到 SQLite，本地开发默认存放在 `data/alphaagents-workflows.db`。
- 执行持股分析时优先读取用户维护的持仓；没有维护持仓时保留 mock 示例回退。
- 本地行情可用时，用最新日线收盘价和证券中文名称补齐 `current_price` 与 `name`。
- 前端提供轻量持仓维护面板，并在保存后可执行持股分析。

**不做：**

- 不接入券商交易接口。
- 不自动下单、撤单、买卖。
- 不做实时盯盘。
- 不做复杂账户、多组合、多币种。

## Task 1：后端持仓仓储与 API

**Files:**

- Modify: `api/app/repositories/sqlite.py`
- Modify: `api/app/api/endpoints/workflows.py` 或新增 `api/app/api/endpoints/portfolio.py`
- Modify: `api/app/api/router.py`
- Test: `tests/test_portfolio_api.py`

**要求：**

- 新增保存和读取持仓列表能力。
- API 建议：
  - `GET /api/v1/portfolio/positions`
  - `PUT /api/v1/portfolio/positions`
- 持仓字段：`symbol`、`quantity`、`cost_price`、`holding_days`。
- 保存时标准化代码为大写。
- 返回时可包含 `name`、`current_price`，但这两个字段可由行情补齐。

## Task 2：持股分析接入手动持仓与本地行情

**Files:**

- Modify: `api/app/workflows/service.py`
- Modify: `api/app/workflows/holding.py` 或新增持仓数据 provider
- Test: `tests/test_holding_workflow.py`
- Test: `tests/test_workflow_api.py`

**要求：**

- `run_holding()` 优先使用 SQLite 中的用户持仓。
- 本地行情库可用时，按代码读取最新日线：
  - `current_price` 使用最新 `close`
  - `name` 使用 `security_metadata`
  - `market_summary` 包含最新交易日、收盘价、涨跌幅等简要信息
- 无用户持仓时保留现有 mock 行为，方便空库演示。

## Task 3：前端持仓维护面板

**Files:**

- Modify: `frontend/index.html`
- Modify: `frontend/scripts/api.js`
- Modify: `frontend/scripts/app.js`
- Modify: `frontend/styles/app.css`
- Test: `tests/test_frontend_static.py`

**要求：**

- 在持股分析区域附近添加持仓维护表单。
- 支持添加一行、删除一行、保存持仓。
- 保存后调用 `PUT /portfolio/positions`。
- 页面初始化时调用 `GET /portfolio/positions` 填充表单。
- 点击“执行持股分析”后展示基于当前持仓的分析结果。

## 验证

- `.venv/bin/python -m pytest tests/test_portfolio_api.py -q`
- `.venv/bin/python -m pytest tests/test_holding_workflow.py tests/test_workflow_api.py -q`
- `.venv/bin/python -m pytest tests/test_frontend_static.py -q`
- `.venv/bin/python -m pytest -q`
- 手动验证：
  - 打开 `http://127.0.0.1:3000/index.html`
  - 添加一个持仓并保存
  - 执行持股分析
  - 确认结果显示中文名、当前价、成本价、支撑/阻力/提醒
