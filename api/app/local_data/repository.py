from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class LocalMarketDataUnavailable(sqlite3.DatabaseError):
    """Raised when local market data storage cannot serve a read request."""


class LocalMarketRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS market_daily (
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    amount REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, trade_date)
                );

                CREATE TABLE IF NOT EXISTS import_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tdx_root TEXT,
                    imported_files INTEGER NOT NULL DEFAULT 0,
                    imported_bars INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS security_metadata (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS security_profiles (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    market_category TEXT NOT NULL,
                    is_st INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sector_metadata (
                    sector_code TEXT PRIMARY KEY,
                    sector_name TEXT NOT NULL,
                    sector_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sector_members (
                    sector_code TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (sector_code, symbol)
                );
                """
            )

    def upsert_daily_bars(
        self, symbol: str, bars: list[dict[str, Any]], source: str = "tdx"
    ) -> int:
        if not bars:
            return 0

        self.initialize_schema()
        updated_at = _utc_now()
        rows = [
            (
                symbol,
                bar["trade_date"],
                bar["open"],
                bar["high"],
                bar["low"],
                bar["close"],
                bar["amount"],
                bar["volume"],
                source,
                updated_at,
            )
            for bar in bars
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO market_daily (
                    symbol, trade_date, open, high, low, close, amount, volume, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    amount = excluded.amount,
                    volume = excluded.volume,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def get_daily_bars(self, symbol: str, limit: int = 120) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []

        safe_limit = max(1, min(limit, 5000))
        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "market_daily"):
                    return []
                rows = connection.execute(
                    """
                    SELECT trade_date, open, high, low, close, amount, volume
                    FROM (
                        SELECT trade_date, open, high, low, close, amount, volume
                        FROM market_daily
                        WHERE symbol = ?
                        ORDER BY trade_date DESC
                        LIMIT ?
                    )
                    ORDER BY trade_date ASC
                    """,
                    (symbol, safe_limit),
                ).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local daily data read failed: {exc}"
            ) from exc

        return [
            {
                "time": row["trade_date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "amount": row["amount"],
                "volume": row["volume"],
            }
            for row in rows
        ]

    def list_symbols(self) -> list[str]:
        if not self.db_path.exists():
            return []

        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "market_daily"):
                    return []
                rows = connection.execute(
                    """
                    SELECT DISTINCT symbol
                    FROM market_daily
                    ORDER BY symbol ASC
                    """
                ).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local symbol list read failed: {exc}"
            ) from exc

        return [row["symbol"] for row in rows]

    def list_sectors(
        self,
        *,
        sector_type: str = "",
        query: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []

        safe_limit = max(1, min(limit, 1000))
        filters: list[str] = []
        parameters: list[object] = []
        if sector_type:
            filters.append("metadata.sector_type = ?")
            parameters.append(sector_type)
        if query.strip():
            filters.append(
                "(metadata.sector_name LIKE ? OR metadata.sector_code LIKE ?)"
            )
            like_query = f"%{query.strip()}%"
            parameters.extend([like_query, like_query])
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "sector_metadata"):
                    return []
                has_members = self._table_exists(connection, "sector_members")
                if has_members:
                    rows = connection.execute(
                        f"""
                        SELECT
                            metadata.sector_code,
                            metadata.sector_name,
                            metadata.sector_type,
                            COUNT(members.symbol) AS member_count
                        FROM sector_metadata AS metadata
                        LEFT JOIN sector_members AS members
                            ON members.sector_code = metadata.sector_code
                        {where_clause}
                        GROUP BY
                            metadata.sector_code,
                            metadata.sector_name,
                            metadata.sector_type
                        ORDER BY member_count DESC, metadata.sector_name ASC
                        LIMIT ?
                        """,
                        (*parameters, safe_limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        f"""
                        SELECT
                            metadata.sector_code,
                            metadata.sector_name,
                            metadata.sector_type,
                            0 AS member_count
                        FROM sector_metadata AS metadata
                        {where_clause}
                        ORDER BY metadata.sector_name ASC
                        LIMIT ?
                        """,
                        (*parameters, safe_limit),
                    ).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local sector metadata read failed: {exc}"
            ) from exc

        return [
            {
                "sector_code": row["sector_code"],
                "sector_name": row["sector_name"],
                "sector_type": row["sector_type"],
                "member_count": row["member_count"],
            }
            for row in rows
        ]

    def list_stock_quotes(
        self,
        *,
        sector_code: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []

        safe_limit = max(1, min(limit, 500))
        sector_members = self.list_sector_members(sector_code) if sector_code else []
        if sector_code and not sector_members:
            return []

        filters = [_a_share_symbol_filter("symbol")]
        parameters: list[object] = []
        if sector_members:
            placeholders = ",".join("?" for _ in sector_members)
            filters.append(f"symbol IN ({placeholders})")
            parameters.extend(sector_members)
        symbol_filter = f"WHERE {' AND '.join(filters)}"

        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "market_daily"):
                    return []
                rows = connection.execute(
                    f"""
                    WITH ranked AS (
                        SELECT
                            symbol,
                            trade_date,
                            close,
                            ROW_NUMBER() OVER (
                                PARTITION BY symbol
                                ORDER BY trade_date DESC
                            ) AS rank
                        FROM market_daily
                        {symbol_filter}
                    ),
                    latest AS (
                        SELECT symbol, trade_date, close
                        FROM ranked
                        WHERE rank = 1
                    ),
                    previous AS (
                        SELECT symbol, close
                        FROM ranked
                        WHERE rank = 2
                    )
                    SELECT
                        latest.symbol,
                        COALESCE(profiles.name, metadata.name, latest.symbol) AS name,
                        latest.trade_date,
                        latest.close,
                        previous.close AS previous_close
                    FROM latest
                    LEFT JOIN previous
                        ON previous.symbol = latest.symbol
                    LEFT JOIN security_profiles AS profiles
                        ON profiles.symbol = latest.symbol
                    LEFT JOIN security_metadata AS metadata
                        ON metadata.symbol = latest.symbol
                    ORDER BY latest.trade_date DESC, latest.symbol ASC
                    LIMIT ?
                    """,
                    (*parameters, safe_limit),
                ).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local stock quote read failed: {exc}"
            ) from exc

        stocks: list[dict[str, Any]] = []
        for row in rows:
            close = float(row["close"])
            previous_close = row["previous_close"]
            change_pct = None
            if previous_close not in (None, 0):
                change_pct = round((close - float(previous_close)) / float(previous_close) * 100, 2)
            stocks.append(
                {
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "latest_trade_date": row["trade_date"],
                    "price": round(close, 4),
                    "change_pct": change_pct,
                }
            )
        return stocks

    def upsert_security_metadata(
        self, rows: list[dict[str, Any]], source: str = "tdx"
    ) -> int:
        if not rows:
            return 0

        self.initialize_schema()
        updated_at = _utc_now()
        values = [
            (row["symbol"], row["name"], row["market"], source, updated_at)
            for row in rows
            if row.get("symbol") and row.get("name") and row.get("market")
        ]
        if not values:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO security_metadata (symbol, name, market, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    market = excluded.market,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                values,
            )
        return len(values)

    def get_security_name(self, symbol: str) -> str | None:
        if not self.db_path.exists():
            return None

        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "security_metadata"):
                    return None
                row = connection.execute(
                    """
                    SELECT name
                    FROM security_metadata
                    WHERE symbol = ?
                    LIMIT 1
                    """,
                    (symbol,),
                ).fetchone()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local security metadata read failed: {exc}"
            ) from exc

        return row["name"] if row else None

    def upsert_security_profiles(
        self, rows: list[dict[str, Any]], source: str = "tdxquant"
    ) -> int:
        if not rows:
            return 0

        self.initialize_schema()
        updated_at = _utc_now()
        values = [
            (
                row["symbol"],
                row["name"],
                row["market"],
                row["market_category"],
                1 if row.get("is_st") else 0,
                source,
                updated_at,
            )
            for row in rows
            if row.get("symbol") and row.get("name") and row.get("market")
        ]
        if not values:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO security_profiles (
                    symbol, name, market, market_category, is_st, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    market = excluded.market,
                    market_category = excluded.market_category,
                    is_st = excluded.is_st,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                values,
            )
            connection.executemany(
                """
                INSERT INTO security_metadata (symbol, name, market, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    market = excluded.market,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                [
                    (symbol, name, market, source, updated_at)
                    for symbol, name, market, _, _, _, _ in values
                ],
            )
        return len(values)

    def get_security_profile(self, symbol: str) -> dict[str, Any] | None:
        if not self.db_path.exists():
            return None

        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "security_profiles"):
                    return None
                row = connection.execute(
                    """
                    SELECT symbol, name, market, market_category, is_st, source
                    FROM security_profiles
                    WHERE symbol = ?
                    LIMIT 1
                    """,
                    (symbol,),
                ).fetchone()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local security profile read failed: {exc}"
            ) from exc

        if row is None:
            return None
        return {
            "symbol": row["symbol"],
            "name": row["name"],
            "market": row["market"],
            "market_category": row["market_category"],
            "is_st": bool(row["is_st"]),
            "source": row["source"],
        }

    def upsert_sector_metadata(
        self, rows: list[dict[str, Any]], source: str = "tdxquant"
    ) -> int:
        if not rows:
            return 0

        self.initialize_schema()
        updated_at = _utc_now()
        values = [
            (
                row["sector_code"],
                row["sector_name"],
                row.get("sector_type", ""),
                source,
                updated_at,
            )
            for row in rows
            if row.get("sector_code") and row.get("sector_name")
        ]
        if not values:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO sector_metadata (
                    sector_code, sector_name, sector_type, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(sector_code) DO UPDATE SET
                    sector_name = excluded.sector_name,
                    sector_type = excluded.sector_type,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                values,
            )
        return len(values)

    def upsert_sector_members(
        self, rows: list[dict[str, Any]], source: str = "tdxquant"
    ) -> int:
        if not rows:
            return 0

        self.initialize_schema()
        updated_at = _utc_now()
        values = [
            (row["sector_code"], row["symbol"], source, updated_at)
            for row in rows
            if row.get("sector_code") and row.get("symbol")
        ]
        if not values:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO sector_members (sector_code, symbol, source, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sector_code, symbol) DO UPDATE SET
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                values,
            )
        return len(values)

    def list_sector_members(self, sector_code: str) -> list[str]:
        if not self.db_path.exists():
            return []

        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "sector_members"):
                    return []
                rows = connection.execute(
                    """
                    SELECT symbol
                    FROM sector_members
                    WHERE sector_code = ?
                    ORDER BY symbol ASC
                    """,
                    (sector_code,),
                ).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local sector members read failed: {exc}"
            ) from exc

        return [row["symbol"] for row in rows]

    def get_security_sectors(self, symbol: str) -> list[dict[str, str]]:
        if not self.db_path.exists():
            return []

        try:
            with self._connect() as connection:
                if not (
                    self._table_exists(connection, "sector_members")
                    and self._table_exists(connection, "sector_metadata")
                ):
                    return []
                rows = connection.execute(
                    """
                    SELECT
                        members.sector_code,
                        metadata.sector_name,
                        metadata.sector_type
                    FROM sector_members AS members
                    JOIN sector_metadata AS metadata
                        ON metadata.sector_code = members.sector_code
                    WHERE members.symbol = ?
                    ORDER BY
                        CASE metadata.sector_type
                            WHEN '行业' THEN 0
                            WHEN '概念' THEN 1
                            WHEN '地区' THEN 2
                            ELSE 3
                        END,
                        metadata.sector_name ASC
                    """,
                    (symbol,),
                ).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            raise LocalMarketDataUnavailable(
                f"Local security sectors read failed: {exc}"
            ) from exc

        return [
            {
                "sector_code": row["sector_code"],
                "sector_name": row["sector_name"],
                "sector_type": row["sector_type"],
            }
            for row in rows
        ]

    def record_import_run(
        self,
        *,
        source: str,
        status: str,
        tdx_root: str,
        imported_files: int,
        imported_bars: int,
        message: str,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        self.initialize_schema()
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO import_runs (
                    source, status, tdx_root, imported_files, imported_bars,
                    message, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    status,
                    tdx_root,
                    imported_files,
                    imported_bars,
                    message,
                    started_at or now,
                    finished_at or now,
                ),
            )

    def status(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return self._empty_status(f"Local market data DB not found: {self.db_path}")

        try:
            with self._connect() as connection:
                if not self._table_exists(connection, "market_daily"):
                    return self._empty_status(
                        "Local market data DB unavailable: "
                        "uninitialized, missing market_daily table"
                    )
                has_import_runs = self._table_exists(connection, "import_runs")
                latest_run = None
                if has_import_runs:
                    latest_run = connection.execute(
                        """
                        SELECT source, status, tdx_root, imported_files, imported_bars,
                               message, started_at, finished_at
                        FROM import_runs
                        ORDER BY id DESC
                        LIMIT 1
                        """
                    ).fetchone()

                market_status = connection.execute(
                    """
                    SELECT
                        COUNT(*) AS bar_count,
                        COUNT(DISTINCT symbol) AS symbol_count,
                        MAX(trade_date) AS latest_trade_date
                    FROM market_daily
                    """
                ).fetchone()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
            return self._empty_status(f"Local market data DB unavailable: {exc}")

        return {
            "bar_count": market_status["bar_count"],
            "symbol_count": market_status["symbol_count"],
            "latest_trade_date": market_status["latest_trade_date"],
            "latest_import_run": dict(latest_run) if latest_run else None,
            "available": True,
            "message": "",
        }

    def _empty_status(self, message: str) -> dict[str, Any]:
        return {
            "bar_count": 0,
            "symbol_count": 0,
            "latest_trade_date": None,
            "latest_import_run": None,
            "available": False,
            "message": message,
        }

    def _table_exists(self, connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.row_factory = sqlite3.Row
        return connection


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _a_share_symbol_filter(column: str) -> str:
    prefixes = (
        "000",
        "001",
        "002",
        "003",
        "300",
        "301",
        "600",
        "601",
        "603",
        "605",
        "688",
        "689",
    )
    conditions = [f"{column} LIKE '{prefix}%.SZ'" for prefix in prefixes[:6]]
    conditions.extend(f"{column} LIKE '{prefix}%.SH'" for prefix in prefixes[6:])
    conditions.extend(
        [
            f"{column} LIKE '4%.BJ'",
            f"{column} LIKE '8%.BJ'",
            f"{column} LIKE '9%.BJ'",
        ]
    )
    return f"({' OR '.join(conditions)})"
