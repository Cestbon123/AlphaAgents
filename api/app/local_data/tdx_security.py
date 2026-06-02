from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CODE_PATTERN = re.compile(rb"([0-9]{6})")
NAME_OFFSET = 31
NAME_LENGTH = 32


def parse_tdx_security_file(file_path: str | Path, market: str) -> list[dict[str, Any]]:
    data = Path(file_path).read_bytes()
    normalized_market = market.upper()
    rows: dict[str, dict[str, Any]] = {}

    for match in CODE_PATTERN.finditer(data):
        code = match.group(1).decode("ascii")
        name_start = match.start() + NAME_OFFSET
        name_end = name_start + NAME_LENGTH
        if name_end > len(data):
            continue

        raw_name = data[name_start:name_end].split(b"\0", 1)[0].strip()
        if not raw_name:
            continue

        try:
            name = raw_name.decode("gbk").strip()
        except UnicodeDecodeError:
            continue

        if not _has_chinese(name):
            continue

        symbol = f"{code}.{normalized_market}"
        rows[symbol] = {"symbol": symbol, "name": name, "market": normalized_market}

    return list(rows.values())


def parse_tdx_security_directory(tdx_root: str | Path) -> list[dict[str, Any]]:
    cache_dir = Path(tdx_root) / "T0002" / "hq_cache"
    files = (
        (cache_dir / "shs.tnf", "SH"),
        (cache_dir / "szs.tnf", "SZ"),
        (cache_dir / "bjs.tnf", "BJ"),
    )

    rows: list[dict[str, Any]] = []
    for file_path, market in files:
        if file_path.exists():
            rows.extend(parse_tdx_security_file(file_path, market))
    return rows


def _has_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)
