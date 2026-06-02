from __future__ import annotations

from typing import Any

EXCLUDED_MARKET_CATEGORIES = {"创业板", "科创板", "北交所"}


def should_exclude_from_strategy_by_default(
    name: str | None,
    profile: dict[str, Any] | None = None,
) -> bool:
    if profile:
        if bool(profile.get("is_st")):
            return True
        if str(profile.get("market_category", "")) in EXCLUDED_MARKET_CATEGORIES:
            return True
    return is_st_security(name)


def is_st_security(name: str | None) -> bool:
    if not name:
        return False
    normalized = name.upper().replace(" ", "")
    return normalized.startswith(("ST", "*ST", "SST", "S*ST"))
