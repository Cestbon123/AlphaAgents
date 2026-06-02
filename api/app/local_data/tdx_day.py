import struct
from pathlib import Path
from typing import Any

TDX_DAY_RECORD_SIZE = 32
TDX_DAY_STRUCT = struct.Struct("<IIIIIfII")


class TdxDayParseError(ValueError):
    """Raised when a TDX .day file cannot be parsed safely."""


def symbol_from_tdx_day_path(path: str | Path) -> str:
    file_name = Path(path).name.lower()
    prefix = file_name[:2]
    code = file_name[2:-4]
    suffix_by_prefix = {"sh": "SH", "sz": "SZ", "bj": "BJ"}
    suffix = suffix_by_prefix.get(prefix)
    if suffix is None or not file_name.endswith(".day") or not code:
        raise TdxDayParseError(f"Unsupported TDX day file name: {path}")
    return f"{code}.{suffix}"


def parse_tdx_day_bytes(content: bytes) -> list[dict[str, Any]]:
    if len(content) % TDX_DAY_RECORD_SIZE != 0:
        raise TdxDayParseError(
            f"TDX .day content length must be a multiple of {TDX_DAY_RECORD_SIZE} bytes"
        )

    bars: list[dict[str, Any]] = []
    for offset in range(0, len(content), TDX_DAY_RECORD_SIZE):
        date, open_price, high, low, close, amount, volume, _reserved = TDX_DAY_STRUCT.unpack_from(
            content, offset
        )
        date_text = str(date)
        if len(date_text) != 8:
            raise TdxDayParseError(f"Invalid TDX trade date: {date}")
        bars.append(
            {
                "trade_date": f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:]}",
                "open": open_price / 100,
                "high": high / 100,
                "low": low / 100,
                "close": close / 100,
                "amount": float(amount),
                "volume": volume,
            }
        )
    return bars


def parse_tdx_day_file(path: str | Path) -> list[dict[str, Any]]:
    return parse_tdx_day_bytes(Path(path).read_bytes())
