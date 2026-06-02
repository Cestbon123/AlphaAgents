from __future__ import annotations

from pathlib import Path
from typing import Any

from app.local_data.repository import LocalMarketRepository

MARKET_SUFFIXES = {
    "0": "SZ",
    "1": "SH",
    "2": "BJ",
}


def import_tdx_local_metadata(
    tdx_root: str | Path, repository: LocalMarketRepository
) -> dict[str, int]:
    root = Path(tdx_root)
    hq_cache = root / "T0002" / "hq_cache"

    sector_metadata, industry_key_map = parse_tdx_sector_metadata(hq_cache)
    industry_members = parse_tdx_industry_members(hq_cache, industry_key_map)
    concept_metadata, concept_members = parse_tdx_infoharbor_blocks(hq_cache)

    sector_count = repository.upsert_sector_metadata(
        [*sector_metadata, *concept_metadata], source="tdx_local"
    )
    member_count = repository.upsert_sector_members(
        [*industry_members, *concept_members], source="tdx_local"
    )

    return {
        "profiles": 0,
        "sectors": sector_count,
        "sector_members": member_count,
    }


def parse_tdx_sector_metadata(
    hq_cache: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    file_path = Path(hq_cache) / "tdxzs3.cfg"
    if not file_path.exists():
        file_path = Path(hq_cache) / "tdxzs.cfg"
    if not file_path.exists():
        return [], {}

    rows: dict[str, dict[str, Any]] = {}
    industry_key_map: dict[str, str] = {}
    for line in _read_gbk_lines(file_path):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 6:
            continue
        name, code, category, _, _, key = parts[:6]
        if not name or not code or not code.isdigit():
            continue

        sector_code = _sector_code(code)
        sector_type = _sector_type(name, category, key)
        rows[sector_code] = {
            "sector_code": sector_code,
            "sector_name": name,
            "sector_type": sector_type,
        }
        if key.startswith(("T", "X")):
            industry_key_map[key] = sector_code

    return list(rows.values()), industry_key_map


def parse_tdx_industry_members(
    hq_cache: str | Path, industry_key_map: dict[str, str]
) -> list[dict[str, str]]:
    file_path = Path(hq_cache) / "tdxhy.cfg"
    if not file_path.exists():
        return []

    members: dict[tuple[str, str], dict[str, str]] = {}
    for line in _read_gbk_lines(file_path):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        symbol = _stock_symbol(parts[0], parts[1])
        if not symbol:
            continue
        for key in parts[2:]:
            sector_code = industry_key_map.get(key)
            if sector_code:
                members[(sector_code, symbol)] = {
                    "sector_code": sector_code,
                    "symbol": symbol,
                }

    return list(members.values())


def parse_tdx_infoharbor_blocks(
    hq_cache: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    file_path = Path(hq_cache) / "infoharbor_block.dat"
    if not file_path.exists():
        return [], []

    metadata: dict[str, dict[str, Any]] = {}
    members: dict[tuple[str, str], dict[str, str]] = {}
    current_sector_code = ""

    for line in _read_gbk_lines(file_path):
        if not line:
            continue
        if line.startswith("#"):
            current_sector_code = _parse_infoharbor_header(line, metadata)
            continue
        if not current_sector_code:
            continue
        for token in line.split(","):
            token = token.strip()
            if not token:
                continue
            symbol = _stock_symbol_from_infoharbor(token)
            if symbol:
                members[(current_sector_code, symbol)] = {
                    "sector_code": current_sector_code,
                    "symbol": symbol,
                }

    return list(metadata.values()), list(members.values())


def _parse_infoharbor_header(
    line: str, metadata: dict[str, dict[str, Any]]
) -> str:
    fields = [field.strip() for field in line.split(",")]
    if len(fields) < 3:
        return ""
    raw_name = fields[0].lstrip("#")
    name = raw_name.removeprefix("GN_") or raw_name
    code = fields[2]
    if not code.isdigit():
        return ""
    sector_code = _sector_code(code)
    metadata[sector_code] = {
        "sector_code": sector_code,
        "sector_name": name,
        "sector_type": "概念",
    }
    return sector_code


def _stock_symbol_from_infoharbor(value: str) -> str:
    if "#" not in value:
        return ""
    market_flag, code = value.split("#", 1)
    return _stock_symbol(market_flag, code)


def _stock_symbol(market_flag: str, code: str) -> str:
    suffix = MARKET_SUFFIXES.get(market_flag)
    if not suffix or not code.isdigit() or len(code) != 6:
        return ""
    return f"{code}.{suffix}"


def _sector_code(code: str) -> str:
    return f"{code}.SH"


def _sector_type(name: str, category: str, key: str) -> str:
    if key.startswith(("T", "X")):
        return "行业"
    if category == "3" or name.endswith("板块"):
        return "地区"
    if category == "4" or "概念" in name:
        return "概念"
    return "板块"


def _read_gbk_lines(file_path: Path) -> list[str]:
    return [
        line.strip()
        for line in file_path.read_text(encoding="gbk", errors="ignore").splitlines()
        if line.strip()
    ]
