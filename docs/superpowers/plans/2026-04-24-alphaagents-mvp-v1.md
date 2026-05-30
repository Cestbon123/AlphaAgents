# AlphaAgents 一期 MVP 实现计划

> **给代理工程师：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐项执行并用复选框跟踪进度。

**目标：** 从零搭建 AlphaAgents 一期 MVP 的可运行纵向切片，支持手动触发选股、持股分析、每日复盘、每周复盘，并生成待确认的知识库和 skill 沉淀候选。

**架构：** 后端采用 FastAPI + Pydantic，将领域对象、数据接入、策略、专家 skill、流程编排和 API 分层。第一期先使用内存仓库和模拟券商数据适配器跑通流程，真实券商接口在后续替换数据接入层。前端采用静态 HTML/CSS/JS 工作台，调用后端 API 展示结果。

**技术栈：** Python 3.12、FastAPI、Pydantic、pydantic-settings、pytest、httpx、Vanilla HTML/CSS/JS。

---

## 文件结构

### 后端应用
- 创建：`api/app/__init__.py`，声明后端包。
- 创建：`api/app/main.py`，创建 FastAPI 应用、注册路由、提供 `alphaagents-api` 启动入口。
- 创建：`api/app/core/config.py`，读取环境配置。
- 创建：`api/app/api/__init__.py`，声明 API 包。
- 创建：`api/app/api/router.py`，聚合 API 路由。
- 创建：`api/app/api/endpoints/__init__.py`，声明 endpoints 包。
- 创建：`api/app/api/endpoints/health.py`，提供健康检查。
- 创建：`api/app/api/endpoints/workflows.py`，提供四个手动执行入口和查询入口。

### 领域模型
- 创建：`api/app/domain/__init__.py`，声明 domain 包。
- 创建：`api/app/domain/enums.py`，定义动作标签、流程类型、沉淀状态。
- 创建：`api/app/domain/models.py`，定义股票上下文、选股结果、持股分析结果、复盘案例、沉淀候选、运行记录、日报。

### 数据接入与存储
- 创建：`api/app/adapters/__init__.py`，声明 adapters 包。
- 创建：`api/app/adapters/broker.py`，定义券商数据适配器接口和模拟实现。
- 创建：`api/app/repositories/__init__.py`，声明 repositories 包。
- 创建：`api/app/repositories/memory.py`，提供第一期内存仓库。

### 策略与专家 skill
- 创建：`api/app/strategies/__init__.py`，声明 strategies 包。
- 创建：`api/app/strategies/basic.py`，提供第一期固定套路策略示例。
- 创建：`api/app/expert_skills/__init__.py`，声明 expert skills 包。
- 创建：`api/app/expert_skills/base.py`，定义产品内专家 skill 合约。
- 创建：`api/app/expert_skills/builtins.py`，提供第一期内置专家 skill。
- 创建：`api/app/expert_skills/registry.py`，提供 skill 注册与按场景调用。

### 工作流
- 创建：`api/app/workflows/__init__.py`，声明 workflows 包。
- 创建：`api/app/workflows/selection.py`，执行选股流程。
- 创建：`api/app/workflows/holding.py`，执行持股分析流程。
- 创建：`api/app/workflows/review.py`，执行每日和每周复盘。
- 创建：`api/app/workflows/deposition.py`，处理沉淀候选的确认、编辑、重新生成和放弃。
- 创建：`api/app/workflows/service.py`，组合四类工作流，供 API 调用。

### 测试
- 创建：`tests/test_health.py`，验证健康检查。
- 创建：`tests/test_domain_models.py`，验证核心对象与动作标签。
- 创建：`tests/test_selection_workflow.py`，验证选股流程。
- 创建：`tests/test_holding_workflow.py`，验证持股流程。
- 创建：`tests/test_review_workflow.py`，验证每日和每周复盘。
- 创建：`tests/test_workflow_api.py`，验证 API 手动执行入口。

### 前端
- 创建：`frontend/index.html`，流程驱动型工作台。
- 创建：`frontend/styles/app.css`，工作台样式。
- 创建：`frontend/scripts/api.js`，封装 API 请求。
- 创建：`frontend/scripts/app.js`，绑定按钮和渲染结果。

---

## Task 1：恢复 FastAPI 基础骨架

**Files:**
- Create: `api/app/__init__.py`
- Create: `api/app/main.py`
- Create: `api/app/core/config.py`
- Create: `api/app/api/__init__.py`
- Create: `api/app/api/router.py`
- Create: `api/app/api/endpoints/__init__.py`
- Create: `api/app/api/endpoints/health.py`
- Test: `tests/test_health.py`

- [ ] **Step 1：写失败测试**

在 `tests/test_health.py` 写入：

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "AlphaAgents"}
```

- [ ] **Step 2：运行测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_health.py -v
```

Expected: FAIL，错误指向 `ModuleNotFoundError: No module named 'app'` 或 `create_app` 不存在。

- [ ] **Step 3：实现最小 FastAPI 骨架**

创建 `api/app/core/config.py`：

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AlphaAgents"
    api_v1_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    cors_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ALPHAAGENTS_",
        extra="ignore",
    )

    @property
    def resolved_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

创建 `api/app/api/endpoints/health.py`：

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def read_health() -> dict[str, str]:
    return {"status": "ok", "service": "AlphaAgents"}
```

创建 `api/app/api/router.py`：

```python
from fastapi import APIRouter

from app.api.endpoints.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
```

创建 `api/app/main.py`：

```python
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    if settings.resolved_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.resolved_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
```

创建空包文件：

```python
# api/app/__init__.py
```

```python
# api/app/api/__init__.py
```

```python
# api/app/api/endpoints/__init__.py
```

- [ ] **Step 4：验证测试通过**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_health.py -v
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add api/app tests/test_health.py
git commit -m "feat: restore fastapi application skeleton"
```

---

## Task 2：定义核心领域模型

**Files:**
- Create: `api/app/domain/__init__.py`
- Create: `api/app/domain/enums.py`
- Create: `api/app/domain/models.py`
- Test: `tests/test_domain_models.py`

- [ ] **Step 1：写失败测试**

在 `tests/test_domain_models.py` 写入：

```python
from app.domain.enums import HoldingAction, SelectionAction, WorkflowType
from app.domain.models import StockContext


def test_selection_actions_are_fixed():
    assert [action.value for action in SelectionAction] == ["买入", "待观察", "放弃"]


def test_holding_actions_are_fixed():
    assert [action.value for action in HoldingAction] == [
        "继续持有",
        "放飞",
        "止损",
        "清仓",
    ]


def test_stock_context_contains_required_fields():
    context = StockContext(
        symbol="000001",
        name="平安银行",
        board="银行",
        market_summary="缩量震荡",
        fundamental_summary="经营稳定",
        board_heat_summary="板块热度一般",
        strategy_hits=["趋势回踩"],
        profile_summary="历史上更适合低波动观察",
    )

    assert context.symbol == "000001"
    assert context.strategy_hits == ["趋势回踩"]
    assert WorkflowType.SELECTION.value == "选股"
```

- [ ] **Step 2：运行测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_domain_models.py -v
```

Expected: FAIL，错误指向 `app.domain` 不存在。

- [ ] **Step 3：实现枚举和模型**

创建 `api/app/domain/enums.py`：

```python
from enum import StrEnum


class SelectionAction(StrEnum):
    BUY = "买入"
    WATCH = "待观察"
    DROP = "放弃"


class HoldingAction(StrEnum):
    HOLD = "继续持有"
    LET_RUN = "放飞"
    STOP_LOSS = "止损"
    CLEAR = "清仓"


class WorkflowType(StrEnum):
    SELECTION = "选股"
    HOLDING = "持股分析"
    DAILY_REVIEW = "每日复盘"
    WEEKLY_REVIEW = "每周复盘"


class DepositionStatus(StrEnum):
    PENDING = "待确认"
    CONFIRMED = "已确认"
    EDITED = "已编辑"
    REGENERATED = "已重新生成"
    DISCARDED = "已放弃"
```

创建 `api/app/domain/models.py`：

```python
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.domain.enums import DepositionStatus, HoldingAction, SelectionAction, WorkflowType


class StockContext(BaseModel):
    symbol: str
    name: str
    board: str
    market_summary: str
    fundamental_summary: str
    board_heat_summary: str
    strategy_hits: list[str] = Field(default_factory=list)
    profile_summary: str = ""


class ExpertJudgement(BaseModel):
    skill_name: str
    scenario: str
    conclusion: str
    reason: str
    risks: list[str] = Field(default_factory=list)


class SelectionResult(BaseModel):
    stock: StockContext
    matched_standards: list[str]
    match_reason: str
    expert_judgements: list[ExpertJudgement]
    action: SelectionAction
    core_reason: str
    risks: list[str] = Field(default_factory=list)


class HoldingPosition(BaseModel):
    symbol: str
    name: str
    quantity: int
    cost_price: float
    current_price: float
    holding_days: int


class HoldingAnalysisResult(BaseModel):
    position: HoldingPosition
    stock: StockContext
    expert_judgements: list[ExpertJudgement]
    action: HoldingAction
    action_reason: str
    next_day_reminder: str
    risks: list[str] = Field(default_factory=list)


class ReviewCase(BaseModel):
    symbol: str
    name: str
    scenario: str
    system_conclusion: str
    user_action: str
    result_summary: str
    deviation: str
    review_conclusion: str
    key_reason: str
    worth_depositing: bool


class DepositionCandidate(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    source: str
    status: DepositionStatus = DepositionStatus.PENDING


class WorkflowRun(BaseModel):
    id: str
    workflow_type: WorkflowType
    executed_at: datetime
    input_summary: str
    output_summary: str
    status: str
    error_message: str = ""


class DailyReport(BaseModel):
    report_date: date
    market_summary: str
    selection_summary: str
    holding_summary: str
    review_summary: str
    deposition_summary: str
```

创建空包文件：

```python
# api/app/domain/__init__.py
```

- [ ] **Step 4：验证测试通过**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_domain_models.py -v
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add api/app/domain tests/test_domain_models.py
git commit -m "feat: define alphaagents domain models"
```

---

## Task 3：实现模拟数据接入和内存仓库

**Files:**
- Create: `api/app/adapters/__init__.py`
- Create: `api/app/adapters/broker.py`
- Create: `api/app/repositories/__init__.py`
- Create: `api/app/repositories/memory.py`
- Test: `tests/test_data_layer.py`

- [ ] **Step 1：写失败测试**

在 `tests/test_data_layer.py` 写入：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import WorkflowType
from app.domain.models import WorkflowRun
from app.repositories.memory import InMemoryAlphaAgentsRepository


def test_mock_broker_returns_stock_contexts():
    provider = MockBrokerDataProvider()

    contexts = provider.get_stock_contexts(["000001"])

    assert len(contexts) == 1
    assert contexts[0].symbol == "000001"
    assert contexts[0].strategy_hits


def test_memory_repository_saves_workflow_runs():
    repository = InMemoryAlphaAgentsRepository()
    run = WorkflowRun(
        id="run-1",
        workflow_type=WorkflowType.SELECTION,
        executed_at="2026-04-24T18:00:00",
        input_summary="输入 1 只候选股",
        output_summary="输出 1 条买入建议",
        status="success",
    )

    repository.save_run(run)

    assert repository.list_runs()[0].id == "run-1"
```

- [ ] **Step 2：运行测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_data_layer.py -v
```

Expected: FAIL，错误指向 `app.adapters` 或 `app.repositories` 不存在。

- [ ] **Step 3：实现模拟券商数据和内存仓库**

创建 `api/app/adapters/broker.py`：

```python
from app.domain.models import HoldingPosition, StockContext


class MockBrokerDataProvider:
    def get_candidate_symbols(self) -> list[str]:
        return ["000001", "300750", "600519"]

    def get_stock_contexts(self, symbols: list[str]) -> list[StockContext]:
        sample = {
            "000001": StockContext(
                symbol="000001",
                name="平安银行",
                board="银行",
                market_summary="缩量震荡，价格靠近短期均线",
                fundamental_summary="基本面稳定，弹性一般",
                board_heat_summary="银行板块热度偏低",
                strategy_hits=["趋势回踩"],
                profile_summary="适合作为低波动观察样本",
            ),
            "300750": StockContext(
                symbol="300750",
                name="宁德时代",
                board="新能源",
                market_summary="放量修复，板块资金回流",
                fundamental_summary="龙头基本面强，机构关注度高",
                board_heat_summary="新能源板块热度回升",
                strategy_hits=["主线回流", "龙头修复"],
                profile_summary="历史上适合观察板块回流强度",
            ),
            "600519": StockContext(
                symbol="600519",
                name="贵州茅台",
                board="白酒",
                market_summary="低波动横盘",
                fundamental_summary="基本面强，但短期催化有限",
                board_heat_summary="白酒板块热度一般",
                strategy_hits=["机构趋势"],
                profile_summary="更适合作为长期画像标的",
            ),
        }
        return [sample[symbol] for symbol in symbols if symbol in sample]

    def get_positions(self) -> list[HoldingPosition]:
        return [
            HoldingPosition(
                symbol="300750",
                name="宁德时代",
                quantity=100,
                cost_price=180.0,
                current_price=192.5,
                holding_days=5,
            )
        ]
```

创建 `api/app/repositories/memory.py`：

```python
from app.domain.models import (
    DepositionCandidate,
    HoldingAnalysisResult,
    SelectionResult,
    WorkflowRun,
)


class InMemoryAlphaAgentsRepository:
    def __init__(self) -> None:
        self._runs: list[WorkflowRun] = []
        self._selection_results: list[SelectionResult] = []
        self._holding_results: list[HoldingAnalysisResult] = []
        self._deposition_candidates: list[DepositionCandidate] = []

    def save_run(self, run: WorkflowRun) -> None:
        self._runs.append(run)

    def list_runs(self) -> list[WorkflowRun]:
        return list(self._runs)

    def save_selection_results(self, results: list[SelectionResult]) -> None:
        self._selection_results = results

    def list_selection_results(self) -> list[SelectionResult]:
        return list(self._selection_results)

    def save_holding_results(self, results: list[HoldingAnalysisResult]) -> None:
        self._holding_results = results

    def list_holding_results(self) -> list[HoldingAnalysisResult]:
        return list(self._holding_results)

    def save_deposition_candidates(self, candidates: list[DepositionCandidate]) -> None:
        self._deposition_candidates.extend(candidates)

    def list_deposition_candidates(self) -> list[DepositionCandidate]:
        return list(self._deposition_candidates)
```

创建空包文件：

```python
# api/app/adapters/__init__.py
```

```python
# api/app/repositories/__init__.py
```

- [ ] **Step 4：验证测试通过**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_data_layer.py -v
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add api/app/adapters api/app/repositories tests/test_data_layer.py
git commit -m "feat: add mock data provider and memory repository"
```

---

## Task 4：实现策略选股和专家 skill 合约

**Files:**
- Create: `api/app/strategies/__init__.py`
- Create: `api/app/strategies/basic.py`
- Create: `api/app/expert_skills/__init__.py`
- Create: `api/app/expert_skills/base.py`
- Create: `api/app/expert_skills/builtins.py`
- Create: `api/app/expert_skills/registry.py`
- Test: `tests/test_expert_skills.py`

- [ ] **Step 1：写失败测试**

在 `tests/test_expert_skills.py` 写入：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import SelectionAction
from app.expert_skills.registry import ExpertSkillRegistry
from app.strategies.basic import BasicSelectionStrategy


def test_basic_strategy_returns_candidates_with_strategy_hits():
    provider = MockBrokerDataProvider()
    strategy = BasicSelectionStrategy(provider)

    candidates = strategy.select_candidates()

    assert candidates
    assert all(candidate.strategy_hits for candidate in candidates)


def test_selection_expert_returns_structured_judgement():
    provider = MockBrokerDataProvider()
    stock = provider.get_stock_contexts(["300750"])[0]
    registry = ExpertSkillRegistry.default()

    result = registry.evaluate_selection(stock)

    assert result.action == SelectionAction.BUY
    assert result.expert_judgements[0].reason
    assert result.core_reason
```

- [ ] **Step 2：运行测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_expert_skills.py -v
```

Expected: FAIL，错误指向 `app.strategies` 或 `app.expert_skills` 不存在。

- [ ] **Step 3：实现策略和 skill 合约**

创建 `api/app/strategies/basic.py`：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.models import StockContext


class BasicSelectionStrategy:
    def __init__(self, data_provider: MockBrokerDataProvider) -> None:
        self._data_provider = data_provider

    def select_candidates(self) -> list[StockContext]:
        symbols = self._data_provider.get_candidate_symbols()
        return self._data_provider.get_stock_contexts(symbols)
```

创建 `api/app/expert_skills/base.py`：

```python
from abc import ABC, abstractmethod

from app.domain.models import ExpertJudgement, StockContext


class SelectionExpertSkill(ABC):
    name: str

    @abstractmethod
    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        raise NotImplementedError


class HoldingExpertSkill(ABC):
    name: str

    @abstractmethod
    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        raise NotImplementedError
```

创建 `api/app/expert_skills/builtins.py`：

```python
from app.domain.models import ExpertJudgement, StockContext
from app.expert_skills.base import HoldingExpertSkill, SelectionExpertSkill


class BoardHeatSelectionSkill(SelectionExpertSkill):
    name = "板块热度选股专家"

    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        if "热度回升" in stock.board_heat_summary or "主线" in " ".join(stock.strategy_hits):
            conclusion = "支持买入候选"
            reason = "策略命中主线或板块热度回升，具备第二天择机买入价值。"
            risks = ["若板块次日退潮，需要降低执行优先级。"]
        elif "热度一般" in stock.board_heat_summary:
            conclusion = "建议待观察"
            reason = "基本面或趋势有参考价值，但板块热度不足，买点需要等待确认。"
            risks = ["板块缺少资金回流时不宜主动买入。"]
        else:
            conclusion = "建议放弃"
            reason = "当前板块和策略信号不足，不适合作为次日重点候选。"
            risks = ["继续跟踪会占用注意力。"]

        return ExpertJudgement(
            skill_name=self.name,
            scenario="选股判断",
            conclusion=conclusion,
            reason=reason,
            risks=risks,
        )


class TrendHoldingSkill(HoldingExpertSkill):
    name = "趋势持股专家"

    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        if "放量修复" in stock.market_summary:
            conclusion = "继续持有"
            reason = "当日行情仍处于修复状态，暂不急于结束持仓。"
            risks = ["次日若放量冲高回落，需要考虑放飞。"]
        else:
            conclusion = "降低仓位"
            reason = "行情动能不足，持仓需要更重视风险控制。"
            risks = ["弱势延续时应考虑止损或清仓。"]

        return ExpertJudgement(
            skill_name=self.name,
            scenario="持股判断",
            conclusion=conclusion,
            reason=reason,
            risks=risks,
        )
```

创建 `api/app/expert_skills/registry.py`：

```python
from app.domain.enums import SelectionAction
from app.domain.models import SelectionResult, StockContext
from app.expert_skills.builtins import BoardHeatSelectionSkill, TrendHoldingSkill


class ExpertSkillRegistry:
    def __init__(self) -> None:
        self.selection_skills = [BoardHeatSelectionSkill()]
        self.holding_skills = [TrendHoldingSkill()]

    @classmethod
    def default(cls) -> "ExpertSkillRegistry":
        return cls()

    def evaluate_selection(self, stock: StockContext) -> SelectionResult:
        judgements = [skill.evaluate(stock) for skill in self.selection_skills]
        first = judgements[0]
        action = self._selection_action_from_conclusion(first.conclusion)
        return SelectionResult(
            stock=stock,
            matched_standards=stock.strategy_hits,
            match_reason=f"{stock.name} 命中：{'、'.join(stock.strategy_hits)}",
            expert_judgements=judgements,
            action=action,
            core_reason=first.reason,
            risks=first.risks,
        )

    def _selection_action_from_conclusion(self, conclusion: str) -> SelectionAction:
        if "买入" in conclusion:
            return SelectionAction.BUY
        if "待观察" in conclusion:
            return SelectionAction.WATCH
        return SelectionAction.DROP
```

创建空包文件：

```python
# api/app/strategies/__init__.py
```

```python
# api/app/expert_skills/__init__.py
```

- [ ] **Step 4：验证测试通过**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_expert_skills.py -v
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add api/app/strategies api/app/expert_skills tests/test_expert_skills.py
git commit -m "feat: add strategy and expert skill contracts"
```

---

## Task 5：实现选股和持股工作流

**Files:**
- Create: `api/app/workflows/__init__.py`
- Create: `api/app/workflows/selection.py`
- Create: `api/app/workflows/holding.py`
- Test: `tests/test_selection_workflow.py`
- Test: `tests/test_holding_workflow.py`

- [ ] **Step 1：写选股失败测试**

在 `tests/test_selection_workflow.py` 写入：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import SelectionAction
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.strategies.basic import BasicSelectionStrategy
from app.workflows.selection import SelectionWorkflow


def test_selection_workflow_saves_results():
    provider = MockBrokerDataProvider()
    repository = InMemoryAlphaAgentsRepository()
    workflow = SelectionWorkflow(
        strategy=BasicSelectionStrategy(provider),
        skills=ExpertSkillRegistry.default(),
        repository=repository,
    )

    results = workflow.run()

    assert results
    assert any(result.action == SelectionAction.BUY for result in results)
    assert repository.list_selection_results() == results
```

- [ ] **Step 2：写持股失败测试**

在 `tests/test_holding_workflow.py` 写入：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import HoldingAction
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.workflows.holding import HoldingWorkflow


def test_holding_workflow_returns_next_day_actions():
    provider = MockBrokerDataProvider()
    repository = InMemoryAlphaAgentsRepository()
    workflow = HoldingWorkflow(
        data_provider=provider,
        skills=ExpertSkillRegistry.default(),
        repository=repository,
    )

    results = workflow.run()

    assert results
    assert results[0].action in {
        HoldingAction.HOLD,
        HoldingAction.LET_RUN,
        HoldingAction.STOP_LOSS,
        HoldingAction.CLEAR,
    }
    assert results[0].next_day_reminder
```

- [ ] **Step 3：运行测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_selection_workflow.py tests/test_holding_workflow.py -v
```

Expected: FAIL，错误指向 `app.workflows` 不存在。

- [ ] **Step 4：实现选股工作流**

创建 `api/app/workflows/selection.py`：

```python
from app.domain.models import SelectionResult
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.strategies.basic import BasicSelectionStrategy


class SelectionWorkflow:
    def __init__(
        self,
        strategy: BasicSelectionStrategy,
        skills: ExpertSkillRegistry,
        repository: InMemoryAlphaAgentsRepository,
    ) -> None:
        self._strategy = strategy
        self._skills = skills
        self._repository = repository

    def run(self) -> list[SelectionResult]:
        candidates = self._strategy.select_candidates()
        results = [self._skills.evaluate_selection(candidate) for candidate in candidates]
        self._repository.save_selection_results(results)
        return results
```

- [ ] **Step 5：补全持股 skill 注册方法**

修改 `api/app/expert_skills/registry.py`，增加：

```python
from app.domain.enums import HoldingAction
from app.domain.models import HoldingAnalysisResult, HoldingPosition
```

并在 `ExpertSkillRegistry` 内增加：

```python
    def evaluate_holding(
        self,
        position: HoldingPosition,
        stock: StockContext,
    ) -> HoldingAnalysisResult:
        judgements = [skill.evaluate(stock) for skill in self.holding_skills]
        first = judgements[0]
        action = self._holding_action_from_conclusion(first.conclusion)
        return HoldingAnalysisResult(
            position=position,
            stock=stock,
            expert_judgements=judgements,
            action=action,
            action_reason=first.reason,
            next_day_reminder=f"{stock.name} 次日重点观察：{first.reason}",
            risks=first.risks,
        )

    def _holding_action_from_conclusion(self, conclusion: str) -> HoldingAction:
        if "继续持有" in conclusion:
            return HoldingAction.HOLD
        if "放飞" in conclusion or "降低仓位" in conclusion:
            return HoldingAction.LET_RUN
        if "止损" in conclusion:
            return HoldingAction.STOP_LOSS
        return HoldingAction.CLEAR
```

- [ ] **Step 6：实现持股工作流**

创建 `api/app/workflows/holding.py`：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.models import HoldingAnalysisResult
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository


class HoldingWorkflow:
    def __init__(
        self,
        data_provider: MockBrokerDataProvider,
        skills: ExpertSkillRegistry,
        repository: InMemoryAlphaAgentsRepository,
    ) -> None:
        self._data_provider = data_provider
        self._skills = skills
        self._repository = repository

    def run(self) -> list[HoldingAnalysisResult]:
        positions = self._data_provider.get_positions()
        contexts = {
            context.symbol: context
            for context in self._data_provider.get_stock_contexts(
                [position.symbol for position in positions]
            )
        }
        results = [
            self._skills.evaluate_holding(position, contexts[position.symbol])
            for position in positions
            if position.symbol in contexts
        ]
        self._repository.save_holding_results(results)
        return results
```

创建空包文件：

```python
# api/app/workflows/__init__.py
```

- [ ] **Step 7：验证测试通过**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_selection_workflow.py tests/test_holding_workflow.py -v
```

Expected: PASS。

- [ ] **Step 8：提交**

```powershell
git add api/app/workflows api/app/expert_skills/registry.py tests/test_selection_workflow.py tests/test_holding_workflow.py
git commit -m "feat: add selection and holding workflows"
```

---

## Task 6：实现复盘和沉淀候选

**Files:**
- Create: `api/app/workflows/review.py`
- Create: `api/app/workflows/deposition.py`
- Test: `tests/test_review_workflow.py`

- [ ] **Step 1：写失败测试**

在 `tests/test_review_workflow.py` 写入：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.strategies.basic import BasicSelectionStrategy
from app.workflows.deposition import DepositionWorkflow
from app.workflows.review import ReviewWorkflow
from app.workflows.selection import SelectionWorkflow


def test_daily_review_generates_cases_and_deposition_candidates():
    provider = MockBrokerDataProvider()
    repository = InMemoryAlphaAgentsRepository()
    SelectionWorkflow(
        strategy=BasicSelectionStrategy(provider),
        skills=ExpertSkillRegistry.default(),
        repository=repository,
    ).run()

    review = ReviewWorkflow(repository)
    deposition = DepositionWorkflow(repository)

    cases = review.run_daily_review()
    candidates = deposition.generate_from_review_cases(cases)

    assert cases
    assert any(case.worth_depositing for case in cases)
    assert candidates
    assert repository.list_deposition_candidates() == candidates
```

- [ ] **Step 2：运行测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_review_workflow.py -v
```

Expected: FAIL，错误指向 `ReviewWorkflow` 或 `DepositionWorkflow` 不存在。

- [ ] **Step 3：实现每日和每周复盘**

创建 `api/app/workflows/review.py`：

```python
from app.domain.enums import SelectionAction
from app.domain.models import ReviewCase
from app.repositories.memory import InMemoryAlphaAgentsRepository


class ReviewWorkflow:
    def __init__(self, repository: InMemoryAlphaAgentsRepository) -> None:
        self._repository = repository

    def run_daily_review(self) -> list[ReviewCase]:
        cases: list[ReviewCase] = []
        for result in self._repository.list_selection_results():
            conclusion = "成功案例" if result.action == SelectionAction.BUY else "观察案例"
            deviation = "无明显偏差" if result.action == SelectionAction.BUY else "需要次日验证"
            cases.append(
                ReviewCase(
                    symbol=result.stock.symbol,
                    name=result.stock.name,
                    scenario="候选股",
                    system_conclusion=result.action.value,
                    user_action="待用户复盘确认",
                    result_summary=result.core_reason,
                    deviation=deviation,
                    review_conclusion=conclusion,
                    key_reason=result.core_reason,
                    worth_depositing=result.action == SelectionAction.BUY,
                )
            )
        return cases

    def run_weekly_review(self) -> list[str]:
        cases = self.run_daily_review()
        return [
            f"本周可沉淀案例 {sum(1 for case in cases if case.worth_depositing)} 条",
            "专家判断有效性需要结合实际交易结果持续校验",
        ]
```

- [ ] **Step 4：实现沉淀候选生成**

创建 `api/app/workflows/deposition.py`：

```python
from uuid import uuid4

from app.domain.models import DepositionCandidate, ReviewCase
from app.repositories.memory import InMemoryAlphaAgentsRepository


class DepositionWorkflow:
    def __init__(self, repository: InMemoryAlphaAgentsRepository) -> None:
        self._repository = repository

    def generate_from_review_cases(self, cases: list[ReviewCase]) -> list[DepositionCandidate]:
        candidates = [
            DepositionCandidate(
                id=str(uuid4()),
                kind="知识库候选",
                title=f"{case.name}：{case.review_conclusion}",
                content=f"{case.key_reason}。适用场景：{case.scenario}。",
                source=f"{case.symbol} {case.name}",
            )
            for case in cases
            if case.worth_depositing
        ]
        self._repository.save_deposition_candidates(candidates)
        return candidates
```

- [ ] **Step 5：验证测试通过**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_review_workflow.py -v
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add api/app/workflows/review.py api/app/workflows/deposition.py tests/test_review_workflow.py
git commit -m "feat: add review and deposition workflows"
```

---

## Task 7：实现统一工作流服务和 API

**Files:**
- Create: `api/app/workflows/service.py`
- Create: `api/app/api/endpoints/workflows.py`
- Modify: `api/app/api/router.py`
- Test: `tests/test_workflow_api.py`

- [ ] **Step 1：写失败测试**

在 `tests/test_workflow_api.py` 写入：

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_run_selection_api_returns_results():
    client = TestClient(create_app())

    response = client.post("/api/v1/workflows/selection/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == "选股"
    assert payload["results"]


def test_dashboard_api_returns_latest_state():
    client = TestClient(create_app())
    client.post("/api/v1/workflows/selection/run")
    client.post("/api/v1/workflows/holding/run")
    client.post("/api/v1/workflows/daily-review/run")

    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_results"]
    assert payload["holding_results"]
    assert payload["deposition_candidates"]
```

- [ ] **Step 2：运行测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_workflow_api.py -v
```

Expected: FAIL，错误指向 `/workflows/selection/run` 不存在。

- [ ] **Step 3：实现统一服务**

创建 `api/app/workflows/service.py`：

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import WorkflowType
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.strategies.basic import BasicSelectionStrategy
from app.workflows.deposition import DepositionWorkflow
from app.workflows.holding import HoldingWorkflow
from app.workflows.review import ReviewWorkflow
from app.workflows.selection import SelectionWorkflow


class AlphaAgentsWorkflowService:
    def __init__(self) -> None:
        self.data_provider = MockBrokerDataProvider()
        self.repository = InMemoryAlphaAgentsRepository()
        self.skills = ExpertSkillRegistry.default()

    def run_selection(self) -> dict[str, object]:
        results = SelectionWorkflow(
            strategy=BasicSelectionStrategy(self.data_provider),
            skills=self.skills,
            repository=self.repository,
        ).run()
        return {"workflow": WorkflowType.SELECTION.value, "results": results}

    def run_holding(self) -> dict[str, object]:
        results = HoldingWorkflow(
            data_provider=self.data_provider,
            skills=self.skills,
            repository=self.repository,
        ).run()
        return {"workflow": WorkflowType.HOLDING.value, "results": results}

    def run_daily_review(self) -> dict[str, object]:
        cases = ReviewWorkflow(self.repository).run_daily_review()
        candidates = DepositionWorkflow(self.repository).generate_from_review_cases(cases)
        return {
            "workflow": WorkflowType.DAILY_REVIEW.value,
            "cases": cases,
            "deposition_candidates": candidates,
        }

    def run_weekly_review(self) -> dict[str, object]:
        summaries = ReviewWorkflow(self.repository).run_weekly_review()
        return {"workflow": WorkflowType.WEEKLY_REVIEW.value, "summaries": summaries}

    def dashboard(self) -> dict[str, object]:
        return {
            "selection_results": self.repository.list_selection_results(),
            "holding_results": self.repository.list_holding_results(),
            "deposition_candidates": self.repository.list_deposition_candidates(),
            "runs": self.repository.list_runs(),
        }
```

- [ ] **Step 4：实现 API endpoint**

创建 `api/app/api/endpoints/workflows.py`：

```python
from fastapi import APIRouter

from app.workflows.service import AlphaAgentsWorkflowService

router = APIRouter(tags=["workflows"])
service = AlphaAgentsWorkflowService()


@router.post("/workflows/selection/run")
def run_selection() -> dict[str, object]:
    return service.run_selection()


@router.post("/workflows/holding/run")
def run_holding() -> dict[str, object]:
    return service.run_holding()


@router.post("/workflows/daily-review/run")
def run_daily_review() -> dict[str, object]:
    return service.run_daily_review()


@router.post("/workflows/weekly-review/run")
def run_weekly_review() -> dict[str, object]:
    return service.run_weekly_review()


@router.get("/dashboard")
def read_dashboard() -> dict[str, object]:
    return service.dashboard()
```

修改 `api/app/api/router.py`：

```python
from fastapi import APIRouter

from app.api.endpoints.health import router as health_router
from app.api.endpoints.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(workflows_router)
```

- [ ] **Step 5：验证 API 测试通过**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_workflow_api.py -v
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add api/app/workflows/service.py api/app/api/endpoints/workflows.py api/app/api/router.py tests/test_workflow_api.py
git commit -m "feat: expose workflow api endpoints"
```

---

## Task 8：实现最小网页工作台

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/styles/app.css`
- Create: `frontend/scripts/api.js`
- Create: `frontend/scripts/app.js`

- [ ] **Step 1：创建 HTML 入口**

创建 `frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AlphaAgents 工作台</title>
    <link rel="stylesheet" href="./styles/app.css" />
  </head>
  <body>
    <main class="workspace">
      <section class="hero">
        <div>
          <p class="eyebrow">A 股盘后投研</p>
          <h1>AlphaAgents 工作台</h1>
          <p class="summary">手动执行选股、持股分析、复盘和沉淀确认。</p>
        </div>
        <div class="actions">
          <button data-run="selection">执行选股</button>
          <button data-run="holding">执行持股分析</button>
          <button data-run="daily-review">执行每日复盘</button>
          <button data-run="weekly-review">执行每周复盘</button>
        </div>
      </section>

      <section class="grid">
        <article>
          <h2>选股结果</h2>
          <div id="selection-results"></div>
        </article>
        <article>
          <h2>持股分析</h2>
          <div id="holding-results"></div>
        </article>
        <article>
          <h2>沉淀候选</h2>
          <div id="deposition-candidates"></div>
        </article>
        <article>
          <h2>运行反馈</h2>
          <pre id="run-output">尚未执行流程</pre>
        </article>
      </section>
    </main>
    <script src="./scripts/api.js"></script>
    <script src="./scripts/app.js"></script>
  </body>
</html>
```

- [ ] **Step 2：创建样式**

创建 `frontend/styles/app.css`：

```css
:root {
  color-scheme: light;
  --ink: #17202a;
  --muted: #5d6d7e;
  --line: #d9e2ec;
  --paper: #f7fafc;
  --panel: #ffffff;
  --accent: #0f766e;
  --accent-strong: #115e59;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

button {
  border: 0;
  background: var(--accent);
  color: white;
  cursor: pointer;
  font: inherit;
  padding: 10px 14px;
}

button:hover {
  background: var(--accent-strong);
}

.workspace {
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  border-bottom: 1px solid var(--line);
  padding-bottom: 24px;
}

.eyebrow {
  color: var(--accent-strong);
  font-weight: 700;
  margin: 0 0 8px;
}

h1,
h2 {
  margin: 0;
}

.summary {
  color: var(--muted);
  margin: 10px 0 0;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 24px;
}

article {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 18px;
}

.item {
  border-top: 1px solid var(--line);
  padding: 12px 0;
}

.item:first-child {
  border-top: 0;
}

.tag {
  color: var(--accent-strong);
  font-weight: 700;
}

pre {
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 760px) {
  .hero {
    align-items: stretch;
    flex-direction: column;
  }

  .actions {
    justify-content: flex-start;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3：封装 API 请求**

创建 `frontend/scripts/api.js`：

```javascript
window.AlphaAgentsApi = {
  baseUrl: "http://127.0.0.1:8000/api/v1",

  async runWorkflow(name) {
    const response = await fetch(`${this.baseUrl}/workflows/${name}/run`, {
      method: "POST"
    });
    if (!response.ok) {
      throw new Error(`流程执行失败：${response.status}`);
    }
    return response.json();
  },

  async getDashboard() {
    const response = await fetch(`${this.baseUrl}/dashboard`);
    if (!response.ok) {
      throw new Error(`仪表盘读取失败：${response.status}`);
    }
    return response.json();
  }
};
```

- [ ] **Step 4：实现页面交互**

创建 `frontend/scripts/app.js`：

```javascript
(function () {
  const output = document.querySelector("#run-output");
  const selectionEl = document.querySelector("#selection-results");
  const holdingEl = document.querySelector("#holding-results");
  const depositionEl = document.querySelector("#deposition-candidates");

  function renderSelection(items) {
    selectionEl.innerHTML = items
      .map(
        (item) => `
          <div class="item">
            <div><strong>${item.stock.name}</strong> ${item.stock.symbol}</div>
            <div class="tag">${item.action}</div>
            <div>${item.core_reason}</div>
          </div>
        `
      )
      .join("");
  }

  function renderHolding(items) {
    holdingEl.innerHTML = items
      .map(
        (item) => `
          <div class="item">
            <div><strong>${item.position.name}</strong> ${item.position.symbol}</div>
            <div class="tag">${item.action}</div>
            <div>${item.next_day_reminder}</div>
          </div>
        `
      )
      .join("");
  }

  function renderDeposition(items) {
    depositionEl.innerHTML = items
      .map(
        (item) => `
          <div class="item">
            <div><strong>${item.title}</strong></div>
            <div>${item.content}</div>
            <div class="tag">${item.status}</div>
          </div>
        `
      )
      .join("");
  }

  async function refreshDashboard() {
    const dashboard = await window.AlphaAgentsApi.getDashboard();
    renderSelection(dashboard.selection_results);
    renderHolding(dashboard.holding_results);
    renderDeposition(dashboard.deposition_candidates);
  }

  async function run(name) {
    output.textContent = "正在执行...";
    const result = await window.AlphaAgentsApi.runWorkflow(name);
    output.textContent = JSON.stringify(result, null, 2);
    await refreshDashboard();
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-run]");
    if (!button) return;
    run(button.dataset.run).catch((error) => {
      output.textContent = error.message;
    });
  });

  refreshDashboard().catch(() => {
    output.textContent = "后端启动后会显示最新结果";
  });
})();
```

- [ ] **Step 5：手动验证**

Run:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir api --reload
```

Expected: 服务运行在 `http://127.0.0.1:8000`。

打开：

```text
D:\DFW\frontend\index.html
```

Expected:
- 页面显示四个按钮。
- 点击 `执行选股` 后能看到候选股和动作标签。
- 点击 `执行持股分析` 后能看到持股动作建议。
- 点击 `执行每日复盘` 后能看到沉淀候选。

- [ ] **Step 6：提交**

```powershell
git add frontend
git commit -m "feat: add alphaagents workflow workspace"
```

---

## Task 9：全量验证与需求覆盖检查

**Files:**
- Modify: `README.md`

- [ ] **Step 1：运行全部后端测试**

Run:

```powershell
.\.venv\Scripts\python -m pytest -v
```

Expected: 所有测试 PASS。

- [ ] **Step 2：运行 Ruff**

Run:

```powershell
.\.venv\Scripts\python -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 3：更新 README 常用入口**

在 `README.md` 增加：

````markdown
## 一期 MVP 开发入口

启动后端：

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir api --reload
```

打开前端：

```text
D:\DFW\frontend\index.html
```

核心接口：
- `POST /api/v1/workflows/selection/run`
- `POST /api/v1/workflows/holding/run`
- `POST /api/v1/workflows/daily-review/run`
- `POST /api/v1/workflows/weekly-review/run`
- `GET /api/v1/dashboard`
````

- [ ] **Step 4：做需求覆盖检查**

对照 `docs/requirements/mvp-v1.md`，确认本阶段覆盖：
- 手动触发选股
- 手动触发持股分析
- 手动触发每日复盘
- 手动触发每周复盘
- 专家 skill 参与选股和持股
- 沉淀候选生成
- 网页工作台展示核心结果

- [ ] **Step 5：提交**

```powershell
git add README.md
git commit -m "docs: add mvp development entrypoints"
```

---

## 自检

### 需求覆盖
- 选股流程：Task 4、Task 5、Task 7、Task 8 覆盖。
- 持股分析流程：Task 5、Task 7、Task 8 覆盖。
- 每日复盘：Task 6、Task 7、Task 8 覆盖。
- 每周复盘：Task 6、Task 7 覆盖。
- 专家 skill：Task 4、Task 5 覆盖。
- 沉淀候选：Task 6、Task 7、Task 8 覆盖。
- 网页仪表盘：Task 8 覆盖。
- 结构化日报：本计划先通过工作流结果对象打基础，日报文件生成应作为下一轮独立计划。
- 可选摘要提醒：本计划不实施，保留为下一轮交付能力。

### 延期边界
- 真实券商接口接入不在本计划实施范围，Task 3 的模拟适配器为后续替换点。
- 策略编写中心不在本计划实施范围。
- 回测系统不在本计划实施范围。
- 自动定时执行不在本计划实施范围。
- 盘中实时盯盘不在本计划实施范围。

### 类型一致性
- 选股动作统一使用 `SelectionAction`。
- 持股动作统一使用 `HoldingAction`。
- 手动执行类型统一使用 `WorkflowType`。
- 沉淀状态统一使用 `DepositionStatus`。
