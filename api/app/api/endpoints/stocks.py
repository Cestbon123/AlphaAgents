from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.local_data.repository import LocalMarketDataUnavailable, LocalMarketRepository
from app.workflows.service import AlphaAgentsWorkflowService
from app.workflows.stock_workspace import StockWorkspaceService

router = APIRouter(prefix="/stocks", tags=["stocks"])


class StockOperationPayload(BaseModel):
    operation_date: date | None = None
    name: str = ""
    source: str = "manual"
    system_conclusion: str = ""
    user_action: str = Field(..., min_length=1)
    reason: str = ""
    result_summary: str = ""


class StockReviewPayload(BaseModel):
    review_date: date | None = None
    name: str = ""
    scenario: str = "个股复盘"
    system_conclusion: str = ""
    user_action: str = Field(..., min_length=1)
    result_summary: str = ""
    deviation: str = "用户主动复盘"
    review_conclusion: str = Field(..., min_length=1)
    key_reason: str = Field(..., min_length=1)
    worth_depositing: bool = False


class StockDepositionPayload(BaseModel):
    kind: str = "模式识别"
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    source: str = "个股复盘"
    status: str = "待确认"
    review_case_id: str | None = None


class StockTrackingPayload(BaseModel):
    status: Literal["重点跟踪", "观察", "暂不跟踪", "放弃"]
    note: str = ""


def get_stock_workspace_service(request: Request) -> StockWorkspaceService:
    if not hasattr(request.app.state, "stock_workspace_service"):
        request.app.state.stock_workspace_service = StockWorkspaceService()
    return request.app.state.stock_workspace_service


def get_workflow_service(request: Request) -> AlphaAgentsWorkflowService:
    if not hasattr(request.app.state, "workflow_service"):
        request.app.state.workflow_service = AlphaAgentsWorkflowService()
    return request.app.state.workflow_service


StockWorkspaceDependency = Annotated[
    StockWorkspaceService, Depends(get_stock_workspace_service)
]
WorkflowService = Annotated[AlphaAgentsWorkflowService, Depends(get_workflow_service)]


@router.get("/{symbol}/workspace")
def read_stock_workspace(
    symbol: str,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    return {"workspace": service.get_workspace(symbol)}


@router.get("/cases/list")
def list_stock_cases(
    service: StockWorkspaceDependency,
    symbol: str | None = None,
    query: str = "",
    kind: str = "",
    status: str = "",
) -> dict[str, object]:
    return {
        "cases": service.workflow_repository.list_stock_cases(
            symbol=symbol,
            query=query,
            kind=kind,
            status=status,
        )
    }


@router.post("/{symbol}/research/run")
def run_stock_research(
    symbol: str,
    workspace_service: StockWorkspaceDependency,
    workflow_service: WorkflowService,
) -> dict[str, object]:
    report_payload = workflow_service.run_research_report(symbol)
    return {
        **report_payload,
        "workspace": workspace_service.get_workspace(symbol),
    }


@router.post("/{symbol}/operations")
def append_stock_operation(
    symbol: str,
    payload: StockOperationPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    operation = service.append_operation(symbol, payload.model_dump(mode="json"))
    return {
        "operation": operation,
        "workspace": service.get_workspace(symbol),
    }


@router.post("/{symbol}/reviews")
def append_stock_review(
    symbol: str,
    payload: StockReviewPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    review_case = service.append_review(symbol, payload.model_dump(mode="json"))
    return {
        "review_case": review_case,
        "workspace": service.get_workspace(symbol),
    }


@router.post("/{symbol}/depositions")
def append_stock_deposition(
    symbol: str,
    payload: StockDepositionPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    candidate = service.append_deposition(symbol, payload.model_dump(mode="json"))
    return {
        "deposition_candidate": candidate,
        "workspace": service.get_workspace(symbol),
    }


@router.patch("/{symbol}/tracking")
def update_stock_tracking(
    symbol: str,
    payload: StockTrackingPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    tracking = service.update_tracking(symbol, payload.status, payload.note)
    return {
        "tracking_state": tracking,
        "workspace": service.get_workspace(symbol),
    }


@router.get("/{symbol}/alerts")
def read_stock_alerts(
    symbol: str,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    data = _compute_alerts(symbol)
    return {"alerts": data}


def _compute_alerts(symbol: str) -> dict[str, object]:
    settings = get_settings()
    repository = LocalMarketRepository(settings.data_db)
    try:
        bars = repository.get_daily_bars(symbol, limit=120)
    except LocalMarketDataUnavailable:
        return _empty_alerts(symbol, "本地日线数据不可用")
    if not bars:
        return _empty_alerts(symbol, "暂无日线数据")

    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]

    last_close = closes[-1]
    prev_close = closes[-2] if len(closes) > 1 else last_close
    last_high = highs[-1]
    last_low = lows[-1]

    # 短期趋势线 = EMA(EMA(C,10),10)
    ema10 = _compute_ema(closes, 10)
    short_trend = _compute_ema(ema10, 10)[-1] if ema10 else last_close

    # 知行多空线 = avg(MA14, MA28, MA57, MA114)
    ma14 = _compute_ma(closes, 14)
    ma28 = _compute_ma(closes, 28)
    ma57 = _compute_ma(closes, 57)
    ma114 = _compute_ma(closes, 114)
    if None in (ma14[-1], ma28[-1], ma57[-1], ma114[-1]):
        return _empty_alerts(symbol, "历史日线不足 114 根，暂不能计算知行多空线")
    long_short_line = (ma14[-1] + ma28[-1] + ma57[-1] + ma114[-1]) / 4

    # KDJ J 值
    kdj = _compute_kdj(bars)

    # 振幅
    amplitude = abs((last_high - last_low) / prev_close * 100) if prev_close else 0

    # 涨跌幅
    change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close else 0

    alerts: list[dict[str, str]] = []

    # 破位判断：收盘 < 知行多空线
    if last_close < long_short_line:
        alerts.append({
            "type": "danger",
            "title": "破位",
            "message": (
                f"收盘价 {last_close:.2f} < 知行多空线(黄线) {long_short_line:.2f}，"
                "跌破支撑"
            ),
        })
    elif short_trend is not None and short_trend >= long_short_line:
        alerts.append({
            "type": "ok",
            "title": "趋势保持",
            "message": (
                f"收盘价 {last_close:.2f} 在知行多空线(黄线) {long_short_line:.2f} "
                f"上方，短期趋势线(白线) {short_trend:.2f} >= 知行多空线"
            ),
        })
    else:
        alerts.append({
            "type": "warning",
            "title": "价格未破位",
            "message": (
                f"收盘价 {last_close:.2f} 在知行多空线(黄线) {long_short_line:.2f} "
                "上方，但短期趋势线已经转弱"
            ),
        })

    # 趋势转弱：短期趋势线 < 知行多空线
    if short_trend is not None and short_trend < long_short_line:
        alerts.append({
            "type": "warning",
            "title": "趋势转弱",
            "message": (
                f"短期趋势线(白线) {short_trend:.2f} "
                f"< 知行多空线(黄线) {long_short_line:.2f}"
            ),
        })

    return {
        "symbol": symbol,
        "date": bars[-1]["time"],
        "close": last_close,
        "short_trend_line": round(short_trend, 4) if short_trend else None,
        "long_short_line": round(long_short_line, 4),
        "kdj_j": round(kdj[-1]["j"], 2) if kdj else None,
        "amplitude_pct": round(amplitude, 2),
        "change_pct": round(change_pct, 2),
        "alerts": alerts,
    }


def _empty_alerts(symbol: str, message: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "date": "",
        "close": None,
        "short_trend_line": None,
        "long_short_line": None,
        "kdj_j": None,
        "amplitude_pct": None,
        "change_pct": None,
        "alerts": [{
            "type": "warning",
            "title": "数据不足",
            "message": message,
        }] if message else [],
    }


def _compute_ema(values: list[float], period: int) -> list[float]:
    result: list[float] = []
    for i, v in enumerate(values):
        if i == 0:
            result.append(v)
        else:
            result.append((2 * v + (period - 1) * result[i - 1]) / (period + 1))
    return result


def _compute_ma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < period:
            result.append(None)
        else:
            result.append(sum(values[i - period + 1 : i + 1]) / period)
    return result


def _compute_kdj(bars: list[dict[str, Any]]) -> list[dict[str, float]]:
    values: list[dict[str, float]] = []
    previous_k = 50.0
    previous_d = 50.0
    for i, bar in enumerate(bars):
        if i == 0:
            k = 50.0
            d = 50.0
        else:
            window = bars[max(0, i - 8) : i + 1]
            high = max(float(item["high"]) for item in window)
            low = min(float(item["low"]) for item in window)
            if high == low:
                rsv = 50.0
            else:
                rsv = (float(bar["close"]) - low) / (high - low) * 100
            k = (1 * rsv + (3 - 1) * previous_k) / 3
            d = (1 * k + (3 - 1) * previous_d) / 3
        j = 3 * k - 2 * d
        previous_k = k
        previous_d = d
        values.append({"k": round(k, 4), "d": round(d, 4), "j": round(j, 4)})
    return values
