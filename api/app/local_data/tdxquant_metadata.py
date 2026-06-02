from __future__ import annotations

from typing import Any

from app.local_data.repository import LocalMarketRepository
from app.strategies.filters import is_st_security

MARKET_CATEGORY_BY_LIST_TYPE = {
    51: "创业板",
    52: "科创板",
    53: "北交所",
}


def import_tdxquant_metadata(
    payload: dict[str, Any], repository: LocalMarketRepository
) -> dict[str, int]:
    profiles = _normalize_profiles(payload.get("stocks", []))
    sectors = _normalize_sectors(payload.get("sectors", []))
    members = _normalize_members(payload.get("sector_members", []))
    relation_sectors, relation_members = _normalize_relations(payload.get("relations", []))

    sector_count = repository.upsert_sector_metadata(_merge_sectors(sectors, relation_sectors))
    member_count = repository.upsert_sector_members([*members, *relation_members])
    profile_count = repository.upsert_security_profiles(profiles)

    return {
        "profiles": profile_count,
        "sectors": sector_count,
        "sector_members": member_count,
    }


def _normalize_profiles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = _symbol(row.get("symbol") or row.get("Code"))
        name = str(row.get("name") or row.get("Name") or symbol)
        if not symbol:
            continue
        list_type = _int_or_none(row.get("list_type", row.get("ListType")))
        market = str(row.get("market") or _market_from_symbol(symbol))
        market_category = str(
            row.get("market_category")
            or MARKET_CATEGORY_BY_LIST_TYPE.get(list_type)
            or _main_board_category(symbol)
        )
        is_st = bool(row.get("is_st") or row.get("IsSTGP") in {1, "1"})
        profiles[symbol] = {
            "symbol": symbol,
            "name": name,
            "market": market,
            "market_category": market_category,
            "is_st": is_st or is_st_security(name),
        }
    return list(profiles.values())


def _normalize_sectors(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    sectors: dict[str, dict[str, str]] = {}
    for row in rows:
        code = _symbol(row.get("sector_code") or row.get("code") or row.get("Code"))
        name = str(row.get("sector_name") or row.get("name") or row.get("Name") or "")
        if not code or not name:
            continue
        sectors[code] = {
            "sector_code": code,
            "sector_name": name,
            "sector_type": str(
                row.get("sector_type") or row.get("type") or row.get("BlockType") or ""
            ),
        }
    return list(sectors.values())


def _normalize_members(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    members: set[tuple[str, str]] = set()
    for row in rows:
        sector_code = _symbol(row.get("sector_code") or row.get("BlockCode"))
        symbol = _symbol(row.get("symbol") or row.get("Code"))
        if sector_code and symbol:
            members.add((sector_code, symbol))
    return [
        {"sector_code": sector_code, "symbol": symbol}
        for sector_code, symbol in sorted(members)
    ]


def _normalize_relations(
    rows: list[dict[str, Any]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sectors: dict[str, dict[str, str]] = {}
    members: set[tuple[str, str]] = set()
    for row in rows:
        symbol = _symbol(row.get("symbol") or row.get("Code"))
        sector_code = _symbol(row.get("sector_code") or row.get("BlockCode"))
        sector_name = str(row.get("sector_name") or row.get("BlockName") or "")
        if not symbol or not sector_code:
            continue
        members.add((sector_code, symbol))
        if sector_name:
            sectors[sector_code] = {
                "sector_code": sector_code,
                "sector_name": sector_name,
                "sector_type": str(row.get("sector_type") or row.get("BlockType") or ""),
            }
    return list(sectors.values()), [
        {"sector_code": sector_code, "symbol": symbol}
        for sector_code, symbol in sorted(members)
    ]


def _merge_sectors(
    first: list[dict[str, str]], second: list[dict[str, str]]
) -> list[dict[str, str]]:
    sectors: dict[str, dict[str, str]] = {}
    for sector in [*first, *second]:
        sectors[sector["sector_code"]] = sector
    return list(sectors.values())


def _symbol(value: object) -> str:
    return str(value or "").strip().upper()


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _market_from_symbol(symbol: str) -> str:
    if "." in symbol:
        return symbol.rsplit(".", 1)[1]
    if symbol.startswith(("4", "8", "9")):
        return "BJ"
    if symbol.startswith("6"):
        return "SH"
    return "SZ"


def _main_board_category(symbol: str) -> str:
    code, _, suffix = symbol.partition(".")
    if suffix == "SH":
        return "沪市主板"
    if suffix == "SZ" and code.startswith("00"):
        return "深市主板"
    if suffix == "BJ":
        return "北交所"
    return "其他"
