from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.models import StockContext, StrategyConditionSnapshot, StrategySnapshot
from app.local_data.repository import LocalMarketRepository
from app.strategies.config import DEFAULT_ZHIXING_PARAMS, normalize_zhixing_params
from app.strategies.filters import should_exclude_from_strategy_by_default

ZHIXING_LOOKBACK = 140
MIN_REQUIRED_BARS = 115
EPSILON = 1e-9


@dataclass(frozen=True)
class ZhixingStrategyParams:
    j_max: float = DEFAULT_ZHIXING_PARAMS["j_max"]
    amplitude_max_pct: float = DEFAULT_ZHIXING_PARAMS["amplitude_max_pct"]
    change_min_pct: float = DEFAULT_ZHIXING_PARAMS["change_min_pct"]
    change_max_pct: float = DEFAULT_ZHIXING_PARAMS["change_max_pct"]

    @classmethod
    def from_mapping(cls, params: dict[str, Any] | None) -> ZhixingStrategyParams:
        normalized = normalize_zhixing_params(dict(params or {}))
        return cls(
            j_max=normalized["j_max"],
            amplitude_max_pct=normalized["amplitude_max_pct"],
            change_min_pct=normalized["change_min_pct"],
            change_max_pct=normalized["change_max_pct"],
        )


@dataclass(frozen=True)
class ZhixingSignal:
    symbol: str
    trade_date: str
    close: float
    j: float
    short_trend: float
    long_short_line: float
    amplitude_pct: float
    change_pct: float


class ZhixingTrendSelectionStrategy:
    """Select candidates with the user supplied Zhixing trend formula."""

    def __init__(
        self,
        repository: LocalMarketRepository,
        stock_pool: list[str],
        limit: int = ZHIXING_LOOKBACK,
        params: ZhixingStrategyParams | None = None,
    ) -> None:
        self._repository = repository
        self._stock_pool = [_normalize_symbol(symbol) for symbol in stock_pool]
        self._limit = limit
        self._params = params or ZhixingStrategyParams()

    def select_candidates(self) -> list[StockContext]:
        candidates: list[StockContext] = []
        symbols = self._stock_pool or self._repository.list_symbols()
        for symbol in symbols:
            normalized_symbol = _normalize_symbol(symbol)
            if _is_excluded_board(normalized_symbol) or not _is_common_stock_candidate(
                normalized_symbol
            ):
                continue

            security_profile = self._repository.get_security_profile(normalized_symbol)
            security_name = (
                security_profile["name"]
                if security_profile
                else self._repository.get_security_name(normalized_symbol)
            )
            if should_exclude_from_strategy_by_default(security_name, profile=security_profile):
                continue

            bars = self._repository.get_daily_bars(normalized_symbol, limit=self._limit)
            signal = evaluate_zhixing_signal(normalized_symbol, bars, params=self._params)
            if signal is None:
                continue

            sectors = self._repository.get_security_sectors(normalized_symbol)
            candidates.append(_stock_context_from_signal(signal, security_name, sectors))
        return candidates


def evaluate_zhixing_signal(
    symbol: str,
    bars: list[dict[str, Any]],
    *,
    params: ZhixingStrategyParams | None = None,
) -> ZhixingSignal | None:
    if len(bars) < MIN_REQUIRED_BARS:
        return None
    strategy_params = params or ZhixingStrategyParams()

    closes = [float(bar["close"]) for bar in bars]
    highs = [float(bar["high"]) for bar in bars]
    lows = [float(bar["low"]) for bar in bars]

    kdj_values = _kdj_values(closes=closes, highs=highs, lows=lows)
    short_trend_values = _ema_series(_ema_series(closes, 10), 10)
    ma14 = _ma(closes, len(closes) - 1, 14)
    ma28 = _ma(closes, len(closes) - 1, 28)
    ma57 = _ma(closes, len(closes) - 1, 57)
    ma114 = _ma(closes, len(closes) - 1, 114)

    if None in (ma14, ma28, ma57, ma114):
        return None

    latest = bars[-1]
    previous_close = closes[-2]
    if previous_close == 0:
        return None

    short_trend = short_trend_values[-1]
    long_short_line = (ma14 + ma28 + ma57 + ma114) / 4
    amplitude_pct = (float(latest["high"]) - float(latest["low"])) / previous_close * 100
    change_pct = (float(latest["close"]) - previous_close) / previous_close * 100
    j = kdj_values[-1]["j"]

    if not (
        _lte(j, strategy_params.j_max)
        and short_trend > long_short_line
        and _lte(amplitude_pct, strategy_params.amplitude_max_pct)
        and _gte(change_pct, strategy_params.change_min_pct)
        and _lte(change_pct, strategy_params.change_max_pct)
    ):
        return None

    return ZhixingSignal(
        symbol=symbol,
        trade_date=str(latest["time"]),
        close=round(float(latest["close"]), 4),
        j=round(j, 4),
        short_trend=round(short_trend, 4),
        long_short_line=round(long_short_line, 4),
        amplitude_pct=round(amplitude_pct, 2),
        change_pct=round(change_pct, 2),
    )


def _stock_context_from_signal(
    signal: ZhixingSignal,
    security_name: str | None = None,
    sectors: list[dict[str, str]] | None = None,
) -> StockContext:
    summary = (
        f"{signal.trade_date} 收盘 {signal.close:.2f}，"
        f"J={signal.j:.2f}，短期趋势线={signal.short_trend:.2f}，"
        f"知行多空线={signal.long_short_line:.2f}，"
        f"振幅={signal.amplitude_pct:.2f}% ，涨跌幅={signal.change_pct:.2f}%"
    )
    return StockContext(
        symbol=signal.symbol,
        name=security_name or signal.symbol,
        board=_board_from_symbol(signal.symbol, sectors),
        market_summary=summary,
        fundamental_summary="本地日线公式选股未接入基本面评分。",
        board_heat_summary="知行趋势策略热度回升",
        strategy_hits=[
            "知行趋势线选股公式",
            "J<=13",
            "短期趋势线>知行多空线",
            "振幅<=4%",
            "涨跌幅[-2%,1.8%]",
        ],
        profile_summary="由本地通达信日线数据生成的投研候选，仅用于复盘和决策辅助。",
        strategy_snapshot=_strategy_snapshot_from_signal(signal),
    )


def _strategy_snapshot_from_signal(signal: ZhixingSignal) -> StrategySnapshot:
    return StrategySnapshot(
        strategy_name="知行趋势线",
        latest_trade_date=signal.trade_date,
        conditions={
            "kdj_j": StrategyConditionSnapshot(
                label="KDJ J值",
                passed=True,
                actual=signal.j,
                expected="<= 13",
            ),
            "short_trend_above_long_short": StrategyConditionSnapshot(
                label="短期趋势线高于知行多空线",
                passed=True,
                actual={
                    "short_trend": signal.short_trend,
                    "long_short_line": signal.long_short_line,
                },
                expected="short_trend > long_short_line",
            ),
            "amplitude_pct": StrategyConditionSnapshot(
                label="当日振幅",
                passed=True,
                actual=signal.amplitude_pct,
                expected="<= 4%",
            ),
            "change_pct": StrategyConditionSnapshot(
                label="当日涨跌幅",
                passed=True,
                actual=signal.change_pct,
                expected="[-2%, 1.8%]",
            ),
            "default_exclusions": StrategyConditionSnapshot(
                label="默认排除项",
                passed=True,
                actual="未命中创业板、科创板、北交所、ST 等默认排除条件",
                expected="仅保留普通主板非 ST 候选",
            ),
        },
    )


def _kdj_values(
    *, closes: list[float], highs: list[float], lows: list[float]
) -> list[dict[str, float]]:
    values: list[dict[str, float]] = []
    previous_k = 50.0
    previous_d = 50.0

    for index, close in enumerate(closes):
        window_start = max(0, index - 8)
        lowest_low = min(lows[window_start : index + 1])
        highest_high = max(highs[window_start : index + 1])
        rsv = 50.0
        if highest_high != lowest_low:
            rsv = (close - lowest_low) / (highest_high - lowest_low) * 100

        k = _sma(rsv, 3, 1, previous_k)
        d = _sma(k, 3, 1, previous_d)
        j = 3 * k - 2 * d
        previous_k = k
        previous_d = d
        values.append({"k": k, "d": d, "j": j})

    return values


def _sma(value: float, period: int, weight: int, previous: float) -> float:
    return (weight * value + (period - weight) * previous) / period


def _ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []

    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append((2 * value + (period - 1) * ema_values[-1]) / (period + 1))
    return ema_values


def _ma(values: list[float], index: int, period: int) -> float | None:
    if index + 1 < period:
        return None
    window = values[index - period + 1 : index + 1]
    return sum(window) / period


def _lte(value: float, expected: float) -> bool:
    return value <= expected + EPSILON


def _gte(value: float, expected: float) -> bool:
    return value >= expected - EPSILON


def _normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if "." in value:
        return value
    if value.startswith(("4", "8", "9")):
        return f"{value}.BJ"
    if value.startswith("6"):
        return f"{value}.SH"
    return f"{value}.SZ"


def _is_excluded_board(symbol: str) -> bool:
    code, _, suffix = symbol.partition(".")
    return (
        code.startswith(("300", "301"))
        or code.startswith(("688", "689"))
        or suffix == "BJ"
    )


def _is_common_stock_candidate(symbol: str) -> bool:
    code, _, suffix = symbol.partition(".")
    if suffix == "SH":
        return code.startswith(("600", "601", "603", "605"))
    if suffix == "SZ":
        return code.startswith(("000", "001", "002", "003"))
    return False


def _board_from_symbol(symbol: str, sectors: list[dict[str, str]] | None = None) -> str:
    if sectors:
        return sectors[0]["sector_name"]

    code, _, suffix = symbol.partition(".")
    if suffix == "SH":
        return "沪市主板"
    if suffix == "SZ" and code.startswith("00"):
        return "深市主板"
    return "其他主板"
