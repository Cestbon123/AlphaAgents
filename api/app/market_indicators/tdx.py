from __future__ import annotations

from typing import Any


def attach_default_indicators(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    macd_values = _macd(bars)
    kdj_values = _kdj(bars)
    vol_values = _vol(bars)

    attached = []
    for index, bar in enumerate(bars):
        next_bar = dict(bar)
        next_bar["indicators"] = {
            "macd": macd_values[index],
            "kdj": kdj_values[index],
            "vol": vol_values[index],
        }
        attached.append(next_bar)
    return attached


def _macd(bars: list[dict[str, Any]]) -> list[dict[str, float]]:
    values = []
    ema12 = None
    ema26 = None
    dea = None

    for bar in bars:
        close = float(bar["close"])
        ema12 = close if ema12 is None else _ema(close, 12, ema12)
        ema26 = close if ema26 is None else _ema(close, 26, ema26)
        dif = ema12 - ema26
        dea = dif if dea is None else _ema(dif, 9, dea)
        values.append(
            {
                "dif": round(dif, 4),
                "dea": round(dea, 4),
                "macd": round((dif - dea) * 2, 4),
            }
        )
    return values


def _ema(value: float, period: int, previous: float) -> float:
    return (2 * value + (period - 1) * previous) / (period + 1)


def _kdj(bars: list[dict[str, Any]]) -> list[dict[str, float]]:
    values = []
    previous_k = 50.0
    previous_d = 50.0

    for index, bar in enumerate(bars):
        if index == 0:
            k = 50.0
            d = 50.0
        else:
            window = bars[max(0, index - 8) : index + 1]
            lowest_low = min(float(item["low"]) for item in window)
            highest_high = max(float(item["high"]) for item in window)
            if highest_high == lowest_low:
                rsv = 50.0
            else:
                rsv = (float(bar["close"]) - lowest_low) / (highest_high - lowest_low) * 100
            k = _sma(rsv, 3, 1, previous_k)
            d = _sma(k, 3, 1, previous_d)

        j = 3 * k - 2 * d
        previous_k = k
        previous_d = d
        values.append({"k": round(k, 4), "d": round(d, 4), "j": round(j, 4)})
    return values


def _sma(value: float, period: int, weight: int, previous: float) -> float:
    return (weight * value + (period - weight) * previous) / period


def _vol(bars: list[dict[str, Any]]) -> list[dict[str, float | int | None]]:
    volumes = [int(bar["volume"]) for bar in bars]
    return [
        {
            "volume": volume,
            "ma5": _ma(volumes, index, 5),
            "ma10": _ma(volumes, index, 10),
        }
        for index, volume in enumerate(volumes)
    ]


def _ma(values: list[int], index: int, period: int) -> float | None:
    if index + 1 < period:
        return None
    window = values[index - period + 1 : index + 1]
    return round(sum(window) / period, 2)
