from app.market_indicators.tdx import attach_default_indicators


def _bar(index: int, *, high: float | None = None, low: float | None = None) -> dict:
    close = 10.0 + index
    return {
        "time": f"2026-05-{index:02d}",
        "open": close - 0.5,
        "high": high if high is not None else close + 1.0,
        "low": low if low is not None else close - 1.0,
        "close": close,
        "amount": close * 100,
        "volume": index * 100,
    }


def test_macd_first_bar_starts_from_zero():
    bars = attach_default_indicators([_bar(1)])

    assert bars[0]["indicators"]["macd"] == {"dif": 0.0, "dea": 0.0, "macd": 0.0}


def test_vol_moving_averages_wait_for_full_period():
    bars = attach_default_indicators([_bar(index) for index in range(1, 11)])

    assert bars[0]["indicators"]["vol"]["ma5"] is None
    assert bars[3]["indicators"]["vol"]["ma5"] is None
    assert bars[4]["indicators"]["vol"]["ma5"] == 300.0
    assert bars[8]["indicators"]["vol"]["ma10"] is None
    assert bars[9]["indicators"]["vol"]["ma10"] == 550.0


def test_kdj_uses_neutral_rsv_when_high_equals_low():
    bars = attach_default_indicators([_bar(index, high=10.0, low=10.0) for index in range(1, 3)])

    assert bars[0]["indicators"]["kdj"] == {"k": 50.0, "d": 50.0, "j": 50.0}
    assert bars[1]["indicators"]["kdj"]["k"] is not None
    assert bars[1]["indicators"]["kdj"]["d"] is not None
    assert bars[1]["indicators"]["kdj"]["j"] is not None


def test_attach_default_indicators_adds_all_indicator_groups_without_mutating_input():
    source = [_bar(index) for index in range(1, 4)]

    bars = attach_default_indicators(source)

    assert "indicators" not in source[0]
    assert bars[0] is not source[0]
    for bar in bars:
        assert set(bar["indicators"]) == {"macd", "kdj", "vol"}
