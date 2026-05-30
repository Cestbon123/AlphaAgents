from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class TdxQuantUnavailable(RuntimeError):
    pass


class TdxQuantDailyBarProvider:
    def __init__(self, settings: Any):
        self.pyplugins = Path(settings.tdxquant_pyplugins) if settings.tdxquant_pyplugins else None
        self.seed_file = Path(settings.tdxquant_seed_file) if settings.tdxquant_seed_file else None

    def get_daily_bars(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        if self.pyplugins is None:
            raise TdxQuantUnavailable("ALPHAAGENTS_TDXQUANT_PYPLUGINS is not configured")
        if not self.pyplugins.exists():
            raise TdxQuantUnavailable(f"TdxQuant pyplugins path does not exist: {self.pyplugins}")

        tq = self._load_tq()
        seed_file = self.seed_file or self.pyplugins / "user" / "tdxdata_test.py"
        try:
            tq.initialize(str(seed_file))
            raw = tq.get_market_data(
                field_list=["Open", "High", "Low", "Close", "Amount", "Volume"],
                stock_list=[symbol],
                period="1d",
                count=max(1, min(limit, 5000)),
                dividend_type="front",
            )
            return _normalize_market_data(raw)
        finally:
            close = getattr(tq, "close", None)
            if callable(close):
                close()

    def _load_tq(self):
        if sys.platform != "win32":
            raise TdxQuantUnavailable(
                "TdxQuant requires the Windows Tongdaxin DLL runtime; "
                "run it from Windows or expose it to WSL through a bridge service."
            )
        for subdir in ("user", "sys"):
            path = str(self.pyplugins / subdir)
            if path not in sys.path:
                sys.path.insert(0, path)
        try:
            from tqcenter import tq  # type: ignore
        except Exception as exc:
            raise TdxQuantUnavailable(f"TdxQuant import failed: {exc}") from exc
        return tq


def _normalize_market_data(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []

    rows: Iterable[Any]
    if hasattr(raw, "to_dict"):
        rows = raw.to_dict("records")
    elif isinstance(raw, dict):
        rows = _rows_from_dict(raw)
    else:
        rows = raw

    normalized = [_normalize_row(row) for row in rows]
    return sorted([row for row in normalized if row], key=lambda row: row["time"])


def _rows_from_dict(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if "data" in raw and isinstance(raw["data"], list):
        return raw["data"]
    if all(isinstance(value, list) for value in raw.values()):
        keys = list(raw)
        return [
            dict(zip(keys, values, strict=False))
            for values in zip(*raw.values(), strict=False)
        ]
    return [raw]


def _normalize_row(row: Any) -> dict[str, Any] | None:
    if hasattr(row, "to_dict"):
        row = row.to_dict()
    if not isinstance(row, dict):
        return None

    trade_date = _date_value(
        row.get("time")
        or row.get("trade_date")
        or row.get("date")
        or row.get("Date")
        or row.get("datetime")
        or row.get("Datetime")
    )
    if not trade_date:
        return None

    return {
        "time": trade_date,
        "open": _number(row.get("open", row.get("Open"))),
        "high": _number(row.get("high", row.get("High"))),
        "low": _number(row.get("low", row.get("Low"))),
        "close": _number(row.get("close", row.get("Close"))),
        "amount": _number(row.get("amount", row.get("Amount"))),
        "volume": _number(row.get("volume", row.get("Volume"))),
    }


def _date_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    digits = "".join(char for char in text if char.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
