# AlphaAgents 可用初版收口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐一个可用的 MVP 初版，让本地日线选股、TdxQuant 只读元数据、持股分析、每日/每周复盘、沉淀确认和前端工作台形成完整闭环。

**Architecture:** TdxQuant 只作为只读元数据来源，通过导出 JSON 再导入项目 SQLite，避免后端运行时直接依赖 Windows DLL。后端继续以 SQLite 为运行数据源，工作流结果按需持久化，前端只消费 FastAPI 接口。

**Tech Stack:** FastAPI、Pydantic、SQLite、原生 HTML/CSS/JS、KLineCharts、本地 TDX/TdxQuant 只读数据。

---

### Task 1: TdxQuant 只读元数据导入

**Files:**
- Modify: `api/app/local_data/repository.py`
- Create: `api/app/local_data/tdxquant_metadata.py`
- Create: `scripts/export-tdxquant-metadata.py`
- Create: `scripts/import-tdxquant-metadata.py`
- Test: `tests/test_tdxquant_metadata_importer.py`

- [ ] **Step 1: Write failing tests**

验证股票基础信息、市场分类、ST 标记、板块列表、板块成分和个股所属板块能落入 SQLite 并读取。

- [ ] **Step 2: Implement repository schema and importer**

新增 `security_profile`、`sector_metadata`、`sector_members` 表；导入器规范化 TdxQuant JSON。

- [ ] **Step 3: Add scripts**

Windows 侧导出 TdxQuant JSON；WSL/项目侧导入 JSON 到 `LocalMarketRepository`。

### Task 2: 真实元数据接入选股过滤

**Files:**
- Modify: `api/app/strategies/filters.py`
- Modify: `api/app/strategies/zhixing.py`
- Test: `tests/test_strategy_filters.py`
- Test: `tests/test_zhixing_selection_strategy.py`

- [ ] **Step 1: Write failing tests**

验证已落库的创业板/科创板/北交所/ST 标记会被默认策略过滤；普通沪深主板保留。

- [ ] **Step 2: Implement filter lookup**

优先使用 SQLite 中的 TdxQuant `list_type`/`is_st`/板块数据；缺失时保留当前代码前缀兜底。

### Task 3: 持股分析结果持久化

**Files:**
- Modify: `api/app/repositories/sqlite.py`
- Modify: `api/app/workflows/service.py`
- Test: `tests/test_workflow_sqlite_repository.py`
- Test: `tests/test_workflow_api.py`

- [ ] **Step 1: Write failing tests**

验证执行持股分析后服务重启仍能在 dashboard 和日报中看到最新持股分析结果。

- [ ] **Step 2: Implement SQLite storage**

以 JSON payload 形式保存最新持股分析结果，避免展开复杂模型表。

### Task 4: 每周复盘聚合

**Files:**
- Modify: `api/app/repositories/sqlite.py`
- Modify: `api/app/workflows/review.py`
- Modify: `api/app/workflows/service.py`
- Modify: `frontend/index.html`
- Modify: `frontend/scripts/api.js`
- Modify: `frontend/scripts/app.js`
- Modify: `frontend/styles/app.css`
- Test: `tests/test_workflow_api.py`
- Test: `tests/test_frontend_static.py`

- [ ] **Step 1: Write failing tests**

验证周复盘从持久化 `review_cases` 跨日期聚合，返回偏差分布、可沉淀数量和重点案例。

- [ ] **Step 2: Implement backend aggregation**

按最近 7 天或已有日期聚合复盘案例，并保留旧 `summaries` 字段兼容前端运行反馈。

- [ ] **Step 3: Implement frontend panel**

在复盘案例之后展示周复盘摘要、偏差分布和重点案例。

### Task 5: 沉淀确认可回看

**Files:**
- Modify: `api/app/repositories/sqlite.py`
- Modify: `api/app/api/endpoints/deposition.py`
- Modify: `frontend/index.html`
- Modify: `frontend/scripts/app.js`
- Test: `tests/test_deposition_api.py`
- Test: `tests/test_frontend_static.py`

- [ ] **Step 1: Write failing tests**

验证状态为“已确认”的沉淀候选可通过只读知识条目接口回看。

- [ ] **Step 2: Implement confirmed entry read model**

不生成可执行 skill 文件，只提供确认后的知识条目列表，保持投研辅助边界。

### Task 6: 验证和文档

**Files:**
- Modify: `docs/project-status.md`

- [ ] **Step 1: Run focused tests**

运行新增和受影响测试。

- [ ] **Step 2: Run full test suite**

运行完整 Python 测试和前端 JS 语法检查。

- [ ] **Step 3: Update status doc**

记录 TdxQuant 元数据能力、仍不接交易执行、可用初版功能清单和后续数据增强项。
