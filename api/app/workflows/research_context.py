from __future__ import annotations

from typing import Any

from app.domain.models import StockResearchContext
from app.external_data.astock import ExternalResearchDataProvider
from app.local_data.repository import LocalMarketDataUnavailable, LocalMarketRepository
from app.market_indicators.tdx import attach_default_indicators
from app.strategies.zhixing import evaluate_zhixing_signal

RESEARCH_BAR_LIMIT = 160


class ResearchContextBuilder:
    def __init__(
        self,
        *,
        market_repository: LocalMarketRepository,
        external_provider: ExternalResearchDataProvider,
    ) -> None:
        self.market_repository = market_repository
        self.external_provider = external_provider

    def build(self, symbol: str) -> StockResearchContext:
        normalized_symbol = _normalize_symbol(symbol)
        gaps: list[str] = []
        risk_flags: list[str] = []

        profile = self._security_profile(normalized_symbol)
        local_sectors = self._security_sectors(normalized_symbol, gaps)
        bars = self._daily_bars(normalized_symbol, gaps)
        supplement = self.external_provider.supplement(normalized_symbol)
        all_sectors = _merge_sectors(local_sectors, supplement.sectors)

        name = _security_name(normalized_symbol, profile, self.market_repository)
        if profile and profile.get("is_st"):
            risk_flags.append("ST 标记")

        latest_bar = bars[-1] if bars else {}
        indicator_bars = attach_default_indicators(bars) if bars else []
        indicator_snapshot = (
            indicator_bars[-1].get("indicators", {}) if indicator_bars else {}
        )
        technical_summary = _technical_summary(normalized_symbol, bars, indicator_snapshot)
        gaps.extend(supplement.data_gaps)
        if not bars:
            gaps.append("local_daily_bars: 本地日线数据缺失")
        if not all_sectors:
            gaps.append("sectors: 行业/概念数据缺失")

        return StockResearchContext(
            symbol=normalized_symbol,
            name=name,
            market=_market_from_symbol(normalized_symbol),
            trade_date=str(latest_bar.get("time", "")),
            latest_close=_to_float(latest_bar.get("close")),
            change_pct=_change_pct(bars),
            sectors=all_sectors,
            technical_summary=technical_summary,
            indicator_snapshot=indicator_snapshot,
            supplement=supplement,
            risk_flags=risk_flags,
            data_gaps=_unique(gaps),
        )

    def _daily_bars(self, symbol: str, gaps: list[str]) -> list[dict[str, Any]]:
        try:
            return self.market_repository.get_daily_bars(symbol, limit=RESEARCH_BAR_LIMIT)
        except LocalMarketDataUnavailable as exc:
            gaps.append(f"local_daily_bars: {exc}")
            return []

    def _security_profile(self, symbol: str) -> dict[str, Any] | None:
        try:
            return self.market_repository.get_security_profile(symbol)
        except LocalMarketDataUnavailable:
            return None

    def _security_sectors(self, symbol: str, gaps: list[str]) -> list[dict[str, Any]]:
        try:
            return self.market_repository.get_security_sectors(symbol)
        except LocalMarketDataUnavailable as exc:
            gaps.append(f"local_sectors: {exc}")
            return []


def _technical_summary(
    symbol: str, bars: list[dict[str, Any]], indicators: dict[str, Any]
) -> str:
    if not bars:
        return "本地日线数据不足，暂无法生成技术摘要。"

    latest = bars[-1]
    zhixing_signal = evaluate_zhixing_signal(symbol, bars)
    macd = indicators.get("macd", {})
    kdj = indicators.get("kdj", {})
    pieces = [
        f"{latest.get('time')} 收盘 {float(latest.get('close', 0)):.2f}",
        f"MACD={macd.get('macd', '--')}",
        f"KDJ-J={kdj.get('j', '--')}",
    ]
    if zhixing_signal:
        pieces.append("命中知行趋势线候选条件")
    else:
        pieces.append("未命中知行趋势线候选条件")
    return "，".join(pieces)


def _security_name(
    symbol: str, profile: dict[str, Any] | None, repository: LocalMarketRepository
) -> str:
    if profile and profile.get("name"):
        return str(profile["name"])
    try:
        return repository.get_security_name(symbol) or symbol
    except LocalMarketDataUnavailable:
        return symbol


def _merge_sectors(
    local_sectors: list[dict[str, Any]], external_sectors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for sector in [*local_sectors, *external_sectors]:
        name = str(sector.get("sector_name") or sector.get("name") or "")
        if name:
            merged[name] = dict(sector)
    return list(merged.values())


def _change_pct(bars: list[dict[str, Any]]) -> float | None:
    if len(bars) < 2:
        return None
    previous_close = _to_float(bars[-2].get("close"))
    latest_close = _to_float(bars[-1].get("close"))
    if previous_close in (None, 0) or latest_close is None:
        return None
    return round((latest_close - previous_close) / previous_close * 100, 2)


def _to_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if "." in value:
        return value
    if value.startswith(("SH", "SZ", "BJ")):
        return f"{value[2:]}.{value[:2]}"
    if value.startswith(("6", "9")):
        return f"{value}.SH"
    if value.startswith(("4", "8")):
        return f"{value}.BJ"
    return f"{value}.SZ"


def _market_from_symbol(symbol: str) -> str:
    return symbol.split(".", 1)[1] if "." in symbol else ""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
