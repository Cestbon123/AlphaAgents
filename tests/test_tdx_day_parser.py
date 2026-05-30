import struct

import pytest

from app.local_data.tdx_day import (
    TdxDayParseError,
    parse_tdx_day_bytes,
    symbol_from_tdx_day_path,
)


def _record(
    date: int = 20260506,
    open_price: int = 100,
    high: int = 200,
    low: int = 50,
    close: int = 150,
    amount: float = 123.0,
    volume: int = 456,
    reserved: int = 0,
) -> bytes:
    return struct.pack("<IIIIIfII", date, open_price, high, low, close, amount, volume, reserved)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("vipdoc/sh/lday/sh600519.day", "600519.SH"),
        ("vipdoc/sz/lday/sz300750.day", "300750.SZ"),
        ("vipdoc/bj/lday/bj920992.day", "920992.BJ"),
    ],
)
def test_symbol_from_tdx_day_path_maps_exchange_prefix(path, expected):
    assert symbol_from_tdx_day_path(path) == expected


def test_parse_tdx_day_bytes_returns_daily_bars_with_scaled_prices():
    bars = parse_tdx_day_bytes(_record())

    assert bars == [
        {
            "trade_date": "2026-05-06",
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "amount": 123.0,
            "volume": 456,
        }
    ]


def test_parse_tdx_day_bytes_rejects_corrupted_record_length():
    with pytest.raises(TdxDayParseError, match="32"):
        parse_tdx_day_bytes(_record() + b"broken")
