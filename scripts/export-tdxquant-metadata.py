#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from typing import Any

LIST_TYPES = {
    5: "全部A股",
    51: "创业板",
    52: "科创板",
    53: "北交所",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export read-only TdxQuant stock and sector metadata to JSON."
    )
    parser.add_argument("--tdx-pyplugins", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--sector-limit",
        type=int,
        default=0,
        help="Limit sectors for smoke testing. Default 0 exports all sectors.",
    )
    args = parser.parse_args()

    pyplugins = Path(args.tdx_pyplugins)
    _install_dataframe_stubs_when_missing()
    sys.path.insert(0, str(pyplugins / "user"))
    sys.path.insert(0, str(pyplugins / "sys"))

    from tqcenter import tq  # type: ignore

    seed_file = pyplugins / "user" / "tdxdata_test.py"
    tq.initialize(str(seed_file))
    try:
        stocks = []
        seen_stocks: dict[str, dict[str, Any]] = {}
        for list_type, category in LIST_TYPES.items():
            for item in tq.get_stock_list(str(list_type), list_type=1):
                symbol = _symbol(item.get("Code"))
                if not symbol:
                    continue
                seen_stocks[symbol] = {
                    "symbol": symbol,
                    "name": str(item.get("Name") or symbol),
                    "market": symbol.rsplit(".", 1)[-1],
                    "market_category": category if list_type != 5 else _main_board_category(symbol),
                    "list_type": list_type,
                    "is_st": _is_st_name(str(item.get("Name") or "")),
                }
        stocks = list(seen_stocks.values())

        sectors = [
            {
                "code": _symbol(item.get("Code")),
                "name": str(item.get("Name") or ""),
                "type": str(item.get("BlockType") or ""),
            }
            for item in tq.get_sector_list(list_type=1)
            if item.get("Code") and item.get("Name")
        ]
        if args.sector_limit > 0:
            sectors = sectors[: args.sector_limit]

        sector_members = []
        for sector in sectors:
            for symbol in tq.get_stock_list_in_sector(sector["code"]):
                normalized = _symbol(symbol)
                if normalized:
                    sector_members.append(
                        {"sector_code": sector["code"], "symbol": normalized}
                    )

        payload = {
            "source": "tdxquant",
            "tdx_pyplugins": str(pyplugins),
            "stocks": stocks,
            "sectors": sectors,
            "sector_members": sector_members,
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "stocks": len(stocks),
                    "sectors": len(sectors),
                    "sector_members": len(sector_members),
                    "output": str(output),
                },
                ensure_ascii=False,
            )
        )
    finally:
        tq.close()
    return 0


def _install_dataframe_stubs_when_missing() -> None:
    try:
        import numpy  # noqa: F401
        import pandas  # noqa: F401
    except ModuleNotFoundError:
        numpy_stub = types.ModuleType("numpy")
        numpy_stub.nan = None
        numpy_stub.array = lambda value, *args, **kwargs: value
        numpy_stub.where = lambda condition, yes, no: yes
        sys.modules.setdefault("numpy", numpy_stub)

        pandas_stub = types.ModuleType("pandas")
        pandas_stub.DataFrame = type("DummyDataFrame", (), {})
        pandas_stub.Series = object
        pandas_stub.concat = lambda *args, **kwargs: None
        sys.modules.setdefault("pandas", pandas_stub)


def _symbol(value: object) -> str:
    return str(value or "").strip().upper()


def _is_st_name(name: str) -> bool:
    normalized = name.upper().replace(" ", "")
    return normalized.startswith(("ST", "*ST", "SST", "S*ST"))


def _main_board_category(symbol: str) -> str:
    code, _, suffix = symbol.partition(".")
    if suffix == "SH":
        return "沪市主板"
    if suffix == "SZ" and code.startswith("00"):
        return "深市主板"
    if suffix == "BJ":
        return "北交所"
    return "其他"


if __name__ == "__main__":
    raise SystemExit(main())
