"""Agent tools — wraps existing API endpoints as LLM function-calling tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.agent.memory_repository import AgentMemoryRepository
from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository
from app.repositories.sqlite import SQLiteWorkflowRepository


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any] = field(repr=False)
    data_sources: tuple[str, ...] = ()
    is_write: bool = False
    requires_confirmation: bool = False


# ── helpers ──

def _market_repo() -> LocalMarketRepository:
    return LocalMarketRepository(get_settings().data_db)


def _workflow_repo() -> SQLiteWorkflowRepository:
    return SQLiteWorkflowRepository(get_settings().workflow_db)


def _memory_repo() -> AgentMemoryRepository:
    return AgentMemoryRepository(get_settings().data_db)


def _normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        return s
    if s.startswith(("6", "9")):
        return f"{s}.SH"
    if s.startswith(("4", "8")):
        return f"{s}.BJ"
    return f"{s}.SZ"


# ── query tools ──

def _tool_get_alerts(symbol: str) -> dict[str, Any]:
    """Get stock alerts (breakdown, trend weakening)."""
    from app.api.endpoints.stocks import _compute_alerts
    return _compute_alerts(_normalize_symbol(symbol))


def _tool_get_daily_bars(symbol: str, limit: int = 120) -> dict[str, Any]:
    """Get daily OHLCV bars with indicators for a stock."""
    repo = _market_repo()
    bars = repo.get_daily_bars(_normalize_symbol(symbol), limit=limit)
    if not bars:
        return {"bars": [], "message": "暂无本地日线数据"}
    from app.market_indicators.tdx import attach_default_indicators
    enriched = attach_default_indicators(bars)
    # trim to requested limit
    enriched = enriched[-limit:]
    name = repo.get_security_name(_normalize_symbol(symbol)) or symbol
    return {"symbol": symbol, "name": name, "bars": enriched[-5:], "total": len(enriched)}


def _tool_get_workspace(symbol: str) -> dict[str, Any]:
    """Get full stock workspace (alerts, research, operations, reviews)."""
    from app.workflows.stock_workspace import StockWorkspaceService
    svc = StockWorkspaceService()
    return svc.get_workspace(_normalize_symbol(symbol))


def _tool_get_positions() -> dict[str, Any]:
    """Get current portfolio positions."""
    repo = _workflow_repo()
    positions = repo.list_positions()
    return {"positions": positions}


def _tool_get_daily_summary() -> dict[str, Any]:
    """Get today's digest: alerts for held stocks, selection candidates, daily report."""
    repo = _workflow_repo()

    # positions
    positions = repo.list_positions() or []

    # alerts for each position
    pos_alerts = []
    for pos in positions:
        sym = pos.get("symbol", "")
        if sym:
            try:
                alerts = _tool_get_alerts(sym)
                pos_alerts.append({
                    "symbol": sym,
                    "name": pos.get("name", ""),
                    "alerts": alerts.get("alerts", []),
                })
            except Exception:
                pos_alerts.append({"symbol": sym, "error": "无法获取提醒"})

    # latest selection
    selection = repo.get_latest_selection_snapshot()

    # latest daily report
    report = repo.get_latest_daily_report()

    # latest review
    review = repo.get_latest_review_cases()

    return {
        "date": _today_str(),
        "position_alerts": pos_alerts,
        "selection_summary": {
            "candidate_count": len(selection.get("results", [])) if selection else 0,
            "strategy_name": selection.get("strategy_name", "") if selection else "",
        } if selection else None,
        "daily_report_summary": report.get("report_text", "")[:500] if report else None,
        "review_summary": f"{len(review)} cases" if review else None,
    }


def _tool_get_review_history(limit: int = 10) -> dict[str, Any]:
    """Get recent review cases."""
    repo = _workflow_repo()
    cases = repo.list_review_cases(limit=limit)
    return {"cases": cases, "count": len(cases)}


def _tool_get_daily_report(date: str | None = None) -> dict[str, Any]:
    """Get daily report for a specific date."""
    repo = _workflow_repo()
    report = repo.get_daily_report(date or _today_str())
    return {"report": report} if report else {"report": None, "message": "暂无日报"}


def _tool_search_stocks(query: str) -> dict[str, Any]:
    """Search stocks by code or name."""
    repo = _market_repo()
    normalized = query.strip().upper()
    db_path = repo.db_path
    if not db_path or not db_path.exists():
        return {"stocks": [], "message": "数据库不可用"}

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Try to find by exact code first
    symbol = _normalize_symbol(query)
    exact = conn.execute(
        """SELECT symbol, trade_date, close
           FROM market_daily
           WHERE symbol=?
           ORDER BY trade_date DESC
           LIMIT 2""",
        (symbol,),
    ).fetchall()

    if exact:
        latest = dict(exact[0])
        prev = dict(exact[1]) if len(exact) > 1 else latest
        change = (
            round((float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100, 2)
            if prev["close"]
            else 0
        )
        name = repo.get_security_name(symbol) or latest["symbol"]
        conn.close()
        return {
            "stocks": [{
                "symbol": latest["symbol"],
                "name": name,
                "close": latest["close"],
                "change_pct": change,
            }]
        }

    # Broad search: try to get all symbols and match by name
    like = f"%{normalized}%"
    # Get list of unique symbols from market_daily, search by name via repo
    symbols = conn.execute(
        "SELECT DISTINCT symbol FROM market_daily WHERE symbol LIKE ? ORDER BY symbol LIMIT 50",
        (like,),
    ).fetchall()

    results = []
    for row in symbols:
        sym = row["symbol"]
        name = repo.get_security_name(sym)
        if name and normalized.lower() in name.lower():
            bars = conn.execute(
                "SELECT close FROM market_daily WHERE symbol=? ORDER BY trade_date DESC LIMIT 2",
                (sym,),
            ).fetchall()
            latest = dict(bars[0]) if bars else None
            prev = dict(bars[1]) if len(bars) > 1 else latest
            close = float(latest["close"]) if latest else 0
            change = (
                round((close - float(prev["close"])) / float(prev["close"]) * 100, 2)
                if prev and prev["close"]
                else 0
            )
            results.append({"symbol": sym, "name": name, "close": close, "change_pct": change})
            if len(results) >= 20:
                break

    # Fallback: return symbols matching code pattern
    if not results:
        for row in symbols[:20]:
            sym = row["symbol"]
            name = repo.get_security_name(sym) or sym
            results.append({"symbol": sym, "name": name, "close": None, "change_pct": None})

    conn.close()
    return {"stocks": results}


def _tool_run_selection() -> dict[str, Any]:
    """Run the zhixing trend selection strategy."""
    from app.workflows.service import AlphaAgentsWorkflowService
    svc = AlphaAgentsWorkflowService()
    result = svc.run_selection()
    return result


# ── write tools ──

def _tool_update_tracking(symbol: str, status: str, note: str = "") -> dict[str, Any]:
    """Update tracking status for a stock."""
    from app.workflows.stock_workspace import StockWorkspaceService
    svc = StockWorkspaceService()
    return svc.update_tracking(_normalize_symbol(symbol), status, note)


def _tool_record_operation(
    symbol: str,
    user_action: str,
    reason: str = "",
    system_conclusion: str = "",
) -> dict[str, Any]:
    """Record a trading operation for a stock."""
    from datetime import UTC, datetime

    from app.workflows.stock_workspace import StockWorkspaceService
    svc = StockWorkspaceService()
    return svc.append_operation(_normalize_symbol(symbol), {
        "operation_date": datetime.now(UTC).date().isoformat(),
        "user_action": user_action,
        "reason": reason,
        "system_conclusion": system_conclusion,
        "result_summary": reason,
    })


def _tool_save_review(
    symbol: str,
    review_conclusion: str,
    key_reason: str,
    user_action: str = "",
) -> dict[str, Any]:
    """Save a review case for a stock."""
    from datetime import UTC, datetime

    from app.workflows.stock_workspace import StockWorkspaceService
    svc = StockWorkspaceService()
    return svc.append_review(_normalize_symbol(symbol), {
        "review_date": datetime.now(UTC).date().isoformat(),
        "review_conclusion": review_conclusion,
        "key_reason": key_reason,
        "user_action": user_action or "agent辅助记录",
        "result_summary": key_reason,
    })


def _tool_recall_memory(query: str = "", symbol: str = "") -> dict[str, Any]:
    """Search historical decisions and stock impressions."""
    memory = _memory_repo()
    try:
        decisions = memory.search_decisions(query or symbol, limit=5) if (query or symbol) else []
        impression = memory.get_impression(symbol) if symbol else None
        profile = memory.get_profile()
        return {
            "decisions": decisions,
            "impressions": [impression] if impression else [],
            "profile_keys": list(profile.keys()),
        }
    finally:
        memory.close()


def _tool_update_profile(key: str, value: str) -> dict[str, Any]:
    """Update user profile preference."""
    memory = _memory_repo()
    try:
        memory.update_profile(key, value, source="agent_chat")
        return {"key": key, "value": value, "status": "updated"}
    finally:
        memory.close()


def _tool_get_fundamentals(symbol: str) -> dict[str, Any]:
    """Get fundamental & external data for a stock."""
    from app.external_data.astock import AStockDataClient

    sym = _normalize_symbol(symbol)
    client = AStockDataClient(timeout=5.0)
    result = {"symbol": sym}
    gaps = []

    for name, loader in [
        ("估值", client.valuation),
        ("资金流向", client.money_flow),
        ("龙虎榜", client.dragon_tiger),
        ("板块标签", client.sectors),
        ("公告", client.announcements),
        ("新闻", client.news),
    ]:
        try:
            data = loader(sym)
            result[name] = data if data else None
            if not data:
                gaps.append(name)
        except Exception:
            gaps.append(name)

    result["data_gaps"] = gaps
    return result





def _today_str() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).date().isoformat()


# ── tool registry ──

AGENT_TOOLS: list[AgentTool] = [
    AgentTool(
        name="get_daily_summary",
        description="获取今日摘要：持仓告警、选股候选、日报摘要、最新复盘",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_tool_get_daily_summary,
        data_sources=("workflow", "local_market"),
    ),
    AgentTool(
        name="get_stock_detail",
        description="获取个股完整信息：K线指标、工作台数据、提醒状态",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码，如 000001.SH、000001 或 600519",
                },
            },
            "required": ["symbol"],
        },
        handler=lambda symbol: {
            "workspace": _tool_get_workspace(symbol),
            "alerts": _tool_get_alerts(symbol),
            "bars_summary": _tool_get_daily_bars(symbol),
        },
        data_sources=("local_market", "workflow"),
    ),
    AgentTool(
        name="search_stocks",
        description="按代码或名称搜索股票",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词：股票代码、名称、拼音",
                },
            },
            "required": ["query"],
        },
        handler=lambda query: _tool_search_stocks(query),
        data_sources=("local_market",),
    ),
    AgentTool(
        name="get_positions",
        description="获取当前持仓列表",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_tool_get_positions,
        data_sources=("workflow",),
    ),
    AgentTool(
        name="get_review_history",
        description="获取最近复盘案例",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回条数，默认10",
                },
            },
            "required": [],
        },
        handler=lambda limit=10: _tool_get_review_history(int(limit)),
        data_sources=("workflow",),
    ),
    AgentTool(
        name="get_daily_report",
        description="获取指定日期的结构化日报",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "日期，格式 YYYY-MM-DD，默认今天",
                },
            },
            "required": [],
        },
        handler=lambda date=None: _tool_get_daily_report(date),
        data_sources=("workflow",),
    ),
    AgentTool(
        name="run_selection",
        description="执行知行趋势线选股策略",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_tool_run_selection,
        data_sources=("local_market", "workflow"),
    ),
    AgentTool(
        name="recall_memory",
        description="搜索历史决策记忆和股票印象",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词",
                },
                "symbol": {
                    "type": "string",
                    "description": "股票代码，查询该股票的历史印象",
                },
            },
            "required": [],
        },
        handler=lambda query="", symbol="": _tool_recall_memory(query or "", symbol or ""),
        data_sources=("agent_memory",),
    ),
    AgentTool(
        name="update_tracking",
        description=(
            "更新某只股票的跟踪状态（重点跟踪/观察/暂不跟踪/放弃）。"
            "执行前必须获得用户确认。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码",
                },
                "status": {
                    "type": "string",
                    "enum": ["重点跟踪", "观察", "暂不跟踪", "放弃"],
                    "description": "跟踪状态",
                },
                "note": {
                    "type": "string",
                    "description": "备注",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "用户明确确认执行写入操作后才可设为 true",
                },
            },
            "required": ["symbol", "status"],
        },
        handler=lambda symbol, status, note="": _tool_update_tracking(symbol, status, note),
        is_write=True,
        requires_confirmation=True,
    ),
    AgentTool(
        name="record_operation",
        description="记录对某只股票的实际操作。执行前必须获得用户确认。",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码",
                },
                "user_action": {
                    "type": "string",
                    "description": "操作动作：买入/卖出/观望/未介入",
                },
                "reason": {
                    "type": "string",
                    "description": "操作理由",
                },
                "system_conclusion": {
                    "type": "string",
                    "description": "系统结论（选股策略给出的建议）",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "用户明确确认执行写入操作后才可设为 true",
                },
            },
            "required": ["symbol", "user_action"],
        },
        handler=lambda symbol, user_action, reason="", system_conclusion="": (
            _tool_record_operation(symbol, user_action, reason, system_conclusion)
        ),
        is_write=True,
        requires_confirmation=True,
    ),
    AgentTool(
        name="save_review",
        description="保存对某只股票的复盘。执行前必须获得用户确认。",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码",
                },
                "review_conclusion": {
                    "type": "string",
                    "description": "复盘结论",
                },
                "key_reason": {
                    "type": "string",
                    "description": "关键原因",
                },
                "user_action": {
                    "type": "string",
                    "description": "实际操作",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "用户明确确认执行写入操作后才可设为 true",
                },
            },
            "required": ["symbol", "review_conclusion", "key_reason"],
        },
        handler=lambda symbol, review_conclusion, key_reason, user_action="": (
            _tool_save_review(symbol, review_conclusion, key_reason, user_action)
        ),
        is_write=True,
        requires_confirmation=True,
    ),
    AgentTool(
        name="update_profile",
        description="更新用户投资偏好。执行前必须获得用户确认。",
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": (
                        "偏好类型：risk_preference / favorite_sectors / "
                        "strategy_preference"
                    ),
                },
                "value": {
                    "type": "string",
                    "description": "偏好内容",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "用户明确确认执行写入操作后才可设为 true",
                },
            },
            "required": ["key", "value"],
        },
        handler=lambda key, value: _tool_update_profile(key, value),
        is_write=True,
        requires_confirmation=True,
    ),
    AgentTool(
        name="get_fundamentals",
        description="获取股票基本面数据：估值、资金流向、龙虎榜、板块、公告、新闻",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代码"},
            },
            "required": ["symbol"],
        },
        handler=lambda symbol: _tool_get_fundamentals(symbol),
        data_sources=("external_cache",),
    ),
]


def build_tools_for_llm() -> list[dict[str, Any]]:
    """Convert AGENT_TOOLS to OpenAI function-calling JSON."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in AGENT_TOOLS
    ]


def find_tool(name: str) -> AgentTool | None:
    for t in AGENT_TOOLS:
        if t.name == name:
            return t
    return None
