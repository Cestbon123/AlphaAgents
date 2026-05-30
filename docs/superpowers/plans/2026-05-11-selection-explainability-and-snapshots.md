# Selection Explainability and Snapshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AlphaAgents 的选股结果从“能跑出候选”升级为“能解释、能保存、能回看”，支持查看每只股票命中/排除条件和每次选股运行快照。

**Architecture:** 后端在策略层输出结构化条件明细，工作流服务在每次执行选股时生成 Selection Run Snapshot，并用独立 SQLite 状态库持久化。前端在候选股列表旁展示详情面板，并从后端读取最近一次或历史运行结果，点击候选股时同步切换 K 线和详情。

**Tech Stack:** Python 3.12, FastAPI, Pydantic, sqlite3, pytest, Vanilla HTML/CSS/JS, KLineCharts.

---

## 文件结构

- Modify `api/app/core/config.py`: 新增 `workflow_db` 配置，默认 `data/alphaagents-workflow.db`。
- Modify `api/app/domain/models.py`: 新增选股条件明细、策略快照、选股运行快照模型。
- Modify `api/app/strategies/zhixing.py`: 返回每只股票的公式条件明细和排除原因。
- Create `api/app/repositories/sqlite.py`: 持久化选股运行快照，不与行情库耦合。
- Modify `api/app/workflows/service.py`: 执行选股后保存快照，Dashboard 优先读取最近快照。
- Modify `api/app/api/endpoints/workflows.py`: 新增选股运行历史和详情 API。
- Modify `frontend/index.html`: 增加候选股详情面板、历史运行选择区域。
- Modify `frontend/scripts/api.js`: 增加 selection runs API 客户端。
- Modify `frontend/scripts/app.js`: 渲染详情面板、历史快照、候选点击联动。
- Modify `frontend/styles/app.css`: 增加详情面板和历史选择样式。
- Add/extend tests:
  - `tests/test_selection_explainability.py`
  - `tests/test_workflow_sqlite_repository.py`
  - `tests/test_workflow_api.py`
  - `tests/test_frontend_static.py`

---

### Task 1: 策略输出结构化条件明细

**Files:**
- Modify: `api/app/domain/models.py`
- Modify: `api/app/strategies/zhixing.py`
- Test: `tests/test_selection_explainability.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_selection_explainability.py`，验证知行策略命中结果里包含条件明细：

```python
from datetime import date, timedelta

from app.local_data.repository import LocalMarketRepository
from app.strategies.zhixing import ZhixingTrendSelectionStrategy


def _match_bars() -> list[dict]:
    start = date(2026, 1, 1)
    bars = []
    for index in range(130):
        close = 10 + index * 0.08
        if index > 115:
            close = 21 - (index - 115) * 0.15
        bars.append(
            {
                "trade_date": (start + timedelta(days=index)).isoformat(),
                "open": close,
                "high": close + 0.1,
                "low": close - 0.1,
                "close": close,
                "amount": 1_000_000,
                "volume": 100_000,
            }
        )
    return bars


def test_zhixing_result_contains_condition_details(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.upsert_security_metadata(
        [{"symbol": "600001.SH", "name": "测试银行", "market": "SH"}]
    )
    repository.upsert_daily_bars("600001.SH", _match_bars())

    result = ZhixingTrendSelectionStrategy(
        repository=repository,
        stock_pool=["600001.SH"],
    ).select_candidates()[0]

    snapshot = result.strategy_snapshot
    assert snapshot.strategy_name == "知行趋势线"
    assert snapshot.latest_trade_date
    assert {item.key for item in snapshot.conditions} >= {
        "kdj_j",
        "short_trend_above_long_short",
        "amplitude_pct",
        "change_pct",
        "default_exclusions",
    }
    assert all(item.passed for item in snapshot.conditions)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_selection_explainability.py -q
```

Expected: FAIL，`SelectionResult` 或 `StockContext` 尚无 `strategy_snapshot`。

- [ ] **Step 3: 新增领域模型**

在 `api/app/domain/models.py` 中新增：

```python
class StrategyConditionDetail(BaseModel):
    key: str
    label: str
    actual: str
    expected: str
    passed: bool


class StrategySnapshot(BaseModel):
    strategy_name: str
    latest_trade_date: str
    conditions: list[StrategyConditionDetail] = Field(default_factory=list)
    exclusions: list[StrategyConditionDetail] = Field(default_factory=list)
```

并给 `SelectionResult` 增加字段：

```python
strategy_snapshot: StrategySnapshot | None = None
```

- [ ] **Step 4: 知行策略填充条件明细**

在 `api/app/strategies/zhixing.py` 中让 `_stock_context_from_signal` 或策略结果构建流程生成 `StrategySnapshot`。条件至少包含：

```python
StrategyConditionDetail(
    key="kdj_j",
    label="KDJ J 值",
    actual=f"{signal.j:.2f}",
    expected="<= 13",
    passed=True,
)
StrategyConditionDetail(
    key="amplitude_pct",
    label="振幅",
    actual=f"{signal.amplitude_pct:.2f}%",
    expected="<= 4%",
    passed=True,
)
```

若当前实现仍由 `ExpertSkillRegistry.evaluate_selection()` 创建 `SelectionResult`，则把 `strategy_snapshot` 暂存到 `StockContext`，并在 registry 中透传到 `SelectionResult`。

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
.venv/bin/python -m pytest tests/test_selection_explainability.py tests/test_zhixing_selection_strategy.py -q
```

Expected: PASS。

---

### Task 2: 持久化选股运行快照

**Files:**
- Modify: `api/app/core/config.py`
- Modify: `api/app/domain/models.py`
- Create: `api/app/repositories/sqlite.py`
- Modify: `api/app/workflows/service.py`
- Test: `tests/test_workflow_sqlite_repository.py`

- [ ] **Step 1: 写 SQLite 仓库失败测试**

创建 `tests/test_workflow_sqlite_repository.py`：

```python
from datetime import UTC, datetime

from app.domain.enums import WorkflowType
from app.domain.models import WorkflowRun
from app.repositories.sqlite import WorkflowSQLiteRepository


def test_sqlite_repository_saves_and_loads_selection_snapshot(tmp_path):
    repository = WorkflowSQLiteRepository(tmp_path / "workflow.db")
    run = WorkflowRun(
        id="run-1",
        workflow_type=WorkflowType.SELECTION,
        executed_at=datetime(2026, 5, 11, 15, 0, tzinfo=UTC),
        input_summary="local zhixing",
        output_summary="results=2",
        status="success",
    )
    payload = {
        "strategy_name": "知行趋势线",
        "candidate_count": 2,
        "results": [{"stock": {"symbol": "603655.SH", "name": "朗博科技"}}],
    }

    repository.save_selection_snapshot(run, payload)

    latest = repository.get_latest_selection_snapshot()
    assert latest["run"]["id"] == "run-1"
    assert latest["snapshot"]["candidate_count"] == 2
    assert latest["snapshot"]["results"][0]["stock"]["symbol"] == "603655.SH"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_sqlite_repository.py -q
```

Expected: FAIL，`app.repositories.sqlite` 不存在。

- [ ] **Step 3: 添加配置**

在 `api/app/core/config.py` 增加：

```python
workflow_db: str = "data/alphaagents-workflow.db"
```

- [ ] **Step 4: 实现 SQLite 仓库**

创建 `api/app/repositories/sqlite.py`：

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.domain.models import WorkflowRun


class WorkflowSQLiteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS selection_snapshots (
                    run_id TEXT PRIMARY KEY,
                    executed_at TEXT NOT NULL,
                    workflow_type TEXT NOT NULL,
                    input_summary TEXT NOT NULL,
                    output_summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )

    def save_selection_snapshot(self, run: WorkflowRun, snapshot: dict[str, Any]) -> None:
        self.initialize_schema()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO selection_snapshots (
                    run_id, executed_at, workflow_type, input_summary,
                    output_summary, status, snapshot_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    executed_at = excluded.executed_at,
                    workflow_type = excluded.workflow_type,
                    input_summary = excluded.input_summary,
                    output_summary = excluded.output_summary,
                    status = excluded.status,
                    snapshot_json = excluded.snapshot_json
                """,
                (
                    run.id,
                    run.executed_at.isoformat(),
                    run.workflow_type.value,
                    run.input_summary,
                    run.output_summary,
                    run.status,
                    json.dumps(snapshot, ensure_ascii=False),
                ),
            )

    def get_latest_selection_snapshot(self) -> dict[str, Any] | None:
        if not self.db_path.exists():
            return None
        self.initialize_schema()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM selection_snapshots
                ORDER BY executed_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return {
            "run": {
                "id": row["run_id"],
                "executed_at": row["executed_at"],
                "workflow_type": row["workflow_type"],
                "input_summary": row["input_summary"],
                "output_summary": row["output_summary"],
                "status": row["status"],
            },
            "snapshot": json.loads(row["snapshot_json"]),
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
```

- [ ] **Step 5: 工作流保存快照**

在 `api/app/workflows/service.py` 中：

- 初始化 `WorkflowSQLiteRepository(self.settings.workflow_db)`。
- `run_selection()` 中生成 `WorkflowRun` 后同时保存：

```python
snapshot = {
    "strategy_name": "知行趋势线",
    "candidate_count": len(results),
    "results": [result.model_dump(mode="json") for result in results],
}
self.workflow_repository.save_selection_snapshot(run, snapshot)
```

注意 `_record_run()` 目前只保存内存 run；可改为返回 `WorkflowRun`，避免重复构造。

- [ ] **Step 6: 运行测试确认通过**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_sqlite_repository.py tests/test_workflow_api.py -q
```

Expected: PASS。

---

### Task 3: Selection Runs API

**Files:**
- Modify: `api/app/api/endpoints/workflows.py`
- Modify: `api/app/workflows/service.py`
- Test: `tests/test_workflow_api.py`

- [ ] **Step 1: 写 API 失败测试**

扩展 `tests/test_workflow_api.py`：

```python
def test_latest_selection_snapshot_api_returns_persisted_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(tmp_path / "workflow.db"))
    get_settings.cache_clear()
    client = TestClient(create_app())
    client.post("/api/v1/workflows/selection/run")

    response = client.get("/api/v1/workflows/selection/runs/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["candidate_count"] >= 0
    assert "results" in payload["snapshot"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_api.py::test_latest_selection_snapshot_api_returns_persisted_run -q
```

Expected: FAIL，路由不存在。

- [ ] **Step 3: 增加 service 方法**

在 `AlphaAgentsWorkflowService` 中增加：

```python
def latest_selection_run(self) -> dict[str, object]:
    latest = self.workflow_repository.get_latest_selection_snapshot()
    return latest or {"run": None, "snapshot": None}
```

- [ ] **Step 4: 增加 API endpoint**

在 `api/app/api/endpoints/workflows.py` 增加：

```python
@router.get("/workflows/selection/runs/latest")
def latest_selection_run(service: WorkflowService) -> dict[str, object]:
    return service.latest_selection_run()
```

- [ ] **Step 5: 运行 API 测试确认通过**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_api.py -q
```

Expected: PASS。

---

### Task 4: 前端候选股详情面板

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/scripts/app.js`
- Modify: `frontend/styles/app.css`
- Test: `tests/test_frontend_static.py`

- [ ] **Step 1: 写前端静态失败测试**

扩展 `tests/test_frontend_static.py`：

```python
def test_frontend_has_selection_detail_panel():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/scripts/app.js").read_text(encoding="utf-8")

    assert 'id="selection-detail"' in html
    assert 'id="selection-detail-conditions"' in html
    assert "renderSelectionDetail" in script
    assert "strategy_snapshot" in script
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_static.py::test_frontend_has_selection_detail_panel -q
```

Expected: FAIL。

- [ ] **Step 3: 增加 HTML 面板**

在选股结果 panel 后新增：

```html
<section class="panel panel-selection-detail" aria-labelledby="selection-detail-title">
  <div class="section-heading">
    <h2 id="selection-detail-title">候选详情</h2>
    <span id="selection-detail-symbol">等待选择</span>
  </div>
  <div id="selection-detail" class="selection-detail">
    <p class="empty-state">点击候选股查看公式条件、风险提示和专家判断。</p>
  </div>
  <ul id="selection-detail-conditions" class="condition-list"></ul>
</section>
```

- [ ] **Step 4: 渲染详情**

在 `frontend/scripts/app.js` 增加：

```javascript
const selectionDetail = document.querySelector("#selection-detail");
const selectionDetailConditions = document.querySelector("#selection-detail-conditions");
const selectionDetailSymbol = document.querySelector("#selection-detail-symbol");
let latestSelectedResult = null;

function renderSelectionDetail(result) {
  latestSelectedResult = result;
  const stock = result?.stock || {};
  if (selectionDetailSymbol) {
    selectionDetailSymbol.textContent = stock.symbol ? `${stock.name} ${stock.symbol}` : "等待选择";
  }
  clear(selectionDetail);
  clear(selectionDetailConditions);
  if (!result) {
    selectionDetail.append(createEmptyState("点击候选股查看公式条件、风险提示和专家判断。"));
    return;
  }
  const reason = document.createElement("p");
  reason.textContent = text(result.core_reason || result.match_reason);
  selectionDetail.append(reason);
  asList(result.strategy_snapshot?.conditions).forEach((condition) => {
    const item = document.createElement("li");
    item.textContent = `${condition.label}: ${condition.actual} / ${condition.expected}`;
    item.className = condition.passed ? "condition-pass" : "condition-fail";
    selectionDetailConditions.append(item);
  });
}
```

在候选股行点击逻辑中，除了切换 K 线，还调用：

```javascript
const resultIndex = Number(chartTarget?.dataset.resultIndex);
if (Number.isInteger(resultIndex)) {
  renderSelectionDetail(latestSelectionResults[resultIndex]);
}
```

渲染行时设置：

```javascript
row.dataset.resultIndex = String(start + index);
```

- [ ] **Step 5: 增加样式**

在 `frontend/styles/app.css` 增加：

```css
.selection-detail {
  display: grid;
  gap: 10px;
  color: #dce7ec;
  font-size: 13px;
}

.condition-list {
  display: grid;
  gap: 6px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.condition-list li {
  border-top: 1px solid var(--line);
  padding-top: 6px;
  color: var(--muted);
}

.condition-pass {
  color: #8ef3dc;
}

.condition-fail {
  color: #ff9b92;
}
```

- [ ] **Step 6: 运行前端静态测试**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_static.py -q
```

Expected: PASS。

---

### Task 5: 前端读取最近一次持久化选股结果

**Files:**
- Modify: `frontend/scripts/api.js`
- Modify: `frontend/scripts/app.js`
- Test: `tests/test_frontend_static.py`

- [ ] **Step 1: 写失败测试**

扩展 `tests/test_frontend_static.py`：

```python
def test_frontend_fetches_latest_selection_snapshot():
    api_script = Path("frontend/scripts/api.js").read_text(encoding="utf-8")
    app_script = Path("frontend/scripts/app.js").read_text(encoding="utf-8")

    assert "getLatestSelectionRun" in api_script
    assert "/workflows/selection/runs/latest" in api_script
    assert "getLatestSelectionRun" in app_script
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_static.py::test_frontend_fetches_latest_selection_snapshot -q
```

Expected: FAIL。

- [ ] **Step 3: 增加 API client**

在 `frontend/scripts/api.js` 增加：

```javascript
async getLatestSelectionRun() {
  return request("/workflows/selection/runs/latest");
}
```

- [ ] **Step 4: Dashboard 刷新时合并最新快照**

在 `refreshDashboard()` 中，读取 dashboard 后再读取 latest selection run：

```javascript
const dashboard = await window.AlphaAgentsApi.getDashboard();
const latestSelection = await window.AlphaAgentsApi.getLatestSelectionRun();
if (latestSelection?.snapshot?.results?.length) {
  dashboard.selection_results = latestSelection.snapshot.results;
}
```

保留现有 fallback 行为；如果 latest API 失败，不影响 dashboard 基础展示。

- [ ] **Step 5: 运行前端静态测试**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_static.py -q
```

Expected: PASS。

---

## 验证清单

- [ ] `pytest tests/test_selection_explainability.py -q`
- [ ] `pytest tests/test_workflow_sqlite_repository.py -q`
- [ ] `pytest tests/test_workflow_api.py -q`
- [ ] `pytest tests/test_frontend_static.py -q`
- [ ] `pytest -q`
- [ ] 手动执行一次选股 API，确认 `/api/v1/workflows/selection/runs/latest` 返回最近快照。
- [ ] 刷新前端，确认候选列表可分页、点击候选股后 K 线和详情同步切换。

## 暂不纳入本计划

- 策略参数编辑器。
- 多策略组合和策略中心。
- 完整通达信 `INBLOCK` 板块数据解析。
- 持股手动维护和真实复盘录入。
- 自动定时任务、实时盯盘、交易执行。

## 自检结果

- 覆盖需求：本计划覆盖“选股结果可解释”“运行快照持久化”“前端详情查看”“历史最近结果读取”。
- 占位扫描：无 TBD/TODO/以后补充类占位。
- 边界说明：所有输出仅用于投研、复盘、分析和决策辅助，不生成交易指令。
