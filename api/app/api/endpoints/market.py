import sqlite3

from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.local_data.importer import bootstrap_tdx_daily
from app.local_data.repository import LocalMarketDataUnavailable, LocalMarketRepository
from app.market_indicators.tdx import attach_default_indicators

router = APIRouter(prefix="/market", tags=["market"])
INDICATOR_WARMUP_BARS = 260


@router.get("/status")
def get_market_status():
    settings = get_settings()
    return LocalMarketRepository(settings.data_db).status()


@router.get("/sectors")
def list_market_sectors(
    sector_type: str = Query("", max_length=32),
    query: str = Query("", max_length=64),
    limit: int = Query(200, ge=1, le=1000),
):
    settings = get_settings()
    repository = LocalMarketRepository(settings.data_db)
    try:
        sectors = repository.list_sectors(
            sector_type=sector_type,
            query=query,
            limit=limit,
        )
    except LocalMarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"sectors": sectors}


@router.get("/stocks")
def list_market_stocks(
    sector_code: str = Query("", max_length=64),
    limit: int = Query(10, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    settings = get_settings()
    repository = LocalMarketRepository(settings.data_db)
    try:
        stocks, total = repository.list_stock_quotes_paginated(
            sector_code=sector_code, limit=limit, offset=offset
        )
    except LocalMarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"stocks": stocks, "total": total, "limit": limit, "offset": offset}
    return {"stocks": stocks}


@router.post("/sync")
def sync_market_data():
    settings = get_settings()
    if not settings.tdx_root:
        raise HTTPException(
            status_code=400,
            detail="ALPHAAGENTS_TDX_ROOT is required before syncing local TDX data.",
        )

    try:
        summary = bootstrap_tdx_daily(tdx_root=settings.tdx_root, db_path=settings.data_db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TDX daily data sync failed: {exc}") from exc

    summary["market_status"] = LocalMarketRepository(settings.data_db).status()
    return summary


@router.get("/daily-bars")
def get_daily_bars(
    symbol: str = Query(..., min_length=1), limit: int = Query(120, ge=1, le=5000)
):
    settings = get_settings()
    repository = LocalMarketRepository(settings.data_db)
    warm_limit = limit + INDICATOR_WARMUP_BARS

    local_bars, local_error = _read_local_bars(repository, symbol, warm_limit)
    if local_bars:
        return {
            "symbol": symbol,
            "name": _security_name(repository, symbol),
            "bars": attach_default_indicators(local_bars)[-limit:],
            "source": "local",
            "message": "",
        }

    if local_error:
        return {
            "symbol": symbol,
            "bars": [],
            "source": "unavailable",
            "message": local_error,
        }

    return {
        "symbol": symbol,
        "bars": [],
        "source": "local",
        "message": f"No local daily bars for symbol: {symbol}.",
    }


def _read_local_bars(
    repository: LocalMarketRepository, symbol: str, limit: int
) -> tuple[list[dict], str]:
    if not repository.db_path.exists():
        return [], f"Local market data DB not found: {repository.db_path}"

    status = repository.status()
    if not status.get("available", True):
        return [], status.get("message") or "Local market data DB unavailable"

    try:
        return repository.get_daily_bars(symbol, limit=limit), ""
    except LocalMarketDataUnavailable as exc:
        return [], f"Local market data storage unavailable: {exc}"
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        return [], f"Local market data DB unavailable: {exc}"


def _security_name(repository: LocalMarketRepository, symbol: str) -> str:
    try:
        return repository.get_security_name(symbol) or symbol
    except LocalMarketDataUnavailable:
        return symbol
