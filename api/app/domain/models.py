from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

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
    strategy_snapshot: StrategySnapshot | None = None


class ExpertJudgement(BaseModel):
    skill_name: str
    scenario: str
    conclusion: str
    reason: str
    risks: list[str] = Field(default_factory=list)


class StrategyConditionSnapshot(BaseModel):
    label: str
    passed: bool
    actual: Any = None
    expected: str = ""


class StrategySnapshot(BaseModel):
    strategy_name: str
    latest_trade_date: str
    conditions: dict[str, StrategyConditionSnapshot] = Field(default_factory=dict)


class SelectionResult(BaseModel):
    stock: StockContext
    matched_standards: list[str]
    match_reason: str
    expert_judgements: list[ExpertJudgement]
    action: SelectionAction
    core_reason: str
    risks: list[str] = Field(default_factory=list)
    strategy_snapshot: StrategySnapshot | None = None


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


class OperationRecord(BaseModel):
    operation_date: date
    symbol: str
    name: str = ""
    source: str = "manual"
    system_conclusion: str = ""
    user_action: str
    reason: str = ""
    result_summary: str = ""


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


class StockTrackingState(BaseModel):
    symbol: str
    status: Literal["重点跟踪", "观察", "暂不跟踪", "放弃"] = "观察"
    note: str = ""
    updated_at: str = ""


class StockReviewInput(BaseModel):
    review_date: date
    scenario: str = "个股复盘"
    system_conclusion: str = ""
    user_action: str
    result_summary: str = ""
    deviation: str = "用户主动复盘"
    review_conclusion: str
    key_reason: str
    worth_depositing: bool = False


class StockDepositionInput(BaseModel):
    kind: str = "模式识别"
    title: str
    content: str
    source: str = "个股复盘"
    status: DepositionStatus = DepositionStatus.PENDING
    review_case_id: str | None = None


class StockWorkspace(BaseModel):
    symbol: str
    name: str
    latest_bar: dict[str, Any] | None = None
    selection_result: dict[str, Any] | None = None
    holding_position: dict[str, Any] | None = None
    holding_result: dict[str, Any] | None = None
    latest_research_report: dict[str, Any] | None = None
    operation_records: list[dict[str, Any]] = Field(default_factory=list)
    review_cases: list[dict[str, Any]] = Field(default_factory=list)
    deposition_candidates: list[dict[str, Any]] = Field(default_factory=list)
    tracking_state: StockTrackingState | None = None
    data_gaps: list[str] = Field(default_factory=list)


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
    report_text: str = ""


class ResearchSupplementBundle(BaseModel):
    valuation: dict[str, Any] = Field(default_factory=dict)
    money_flow: dict[str, Any] = Field(default_factory=dict)
    dragon_tiger: list[dict[str, Any]] = Field(default_factory=list)
    sectors: list[dict[str, Any]] = Field(default_factory=list)
    announcements: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class StockResearchContext(BaseModel):
    symbol: str
    name: str
    market: str
    trade_date: str = ""
    latest_close: float | None = None
    change_pct: float | None = None
    sectors: list[dict[str, Any]] = Field(default_factory=list)
    technical_summary: str = ""
    indicator_snapshot: dict[str, Any] = Field(default_factory=dict)
    supplement: ResearchSupplementBundle = Field(default_factory=ResearchSupplementBundle)
    risk_flags: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class ResearchAnalystReport(BaseModel):
    role: str
    summary: str
    report_text: str = ""
    prompt: str = ""
    evidence: list[str] = Field(default_factory=list)
    bullish_points: list[str] = Field(default_factory=list)
    bearish_points: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_gaps: list[str] = Field(default_factory=list)


ResearchDecision = Literal["重点跟踪", "观察", "暂不跟踪", "放弃"]


class StockResearchReport(BaseModel):
    symbol: str
    name: str
    generated_at: datetime
    context: StockResearchContext
    analyst_reports: list[ResearchAnalystReport]
    final_decision: ResearchDecision
    final_reason: str
    generation_mode: str = "deterministic"
    risk_flags: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    report_text: str = ""
