# TDX Local Daily Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local SQLite-backed daily market data source from downloaded Tongdaxin `.day` files so AlphaAgents can run selection workflows without mock broker data.

**Architecture:** Tongdaxin remains a read-only raw data source under `TDX_ROOT/vipdoc/{sh,sz,bj}/lday`. A small parser imports `.day` records into `data/alphaagents.db`, and a `LocalDataProvider` reads SQLite through a focused repository. The workflow service selects `mock` or `local` provider from settings, while the frontend only reads provider status through existing dashboard APIs.

**Tech Stack:** Python 3.12, stdlib `sqlite3`, FastAPI, Pydantic Settings, pytest, Ruff, static HTML/CSS/JS.

---

## File Structure

- Create `api/app/local_data/__init__.py`: package marker for local market data utilities.
- Create `api/app/local_data/tdx_day.py`: parse Tongdaxin `.day` files and convert file paths to standard symbols.
- Create `api/app/local_data/repository.py`: own SQLite schema, upsert daily rows, query status, and read recent bars.
- Create `api/app/local_data/importer.py`: orchestrate bootstrap and daily imports from `TDX_ROOT/vipdoc`.
- Create `api/app/adapters/local_data.py`: implement `LocalDataProvider` with the same public methods used by workflows.
- Create `scripts/import-tdx-daily.py`: command-line entrypoint for `bootstrap`, `daily`, and `status`.
- Modify `api/app/core/config.py`: add `data_provider`, `data_db`, `tdx_root`, and `stock_pool` settings.
- Modify `api/app/workflows/service.py`: select provider from settings and expose dashboard data status.
- Modify `api/app/strategies/basic.py`: type against a protocol instead of `MockBrokerDataProvider`.
- Modify `frontend/index.html`, `frontend/scripts/app.js`, `frontend/styles/app.css`: show provider status without reading SQLite directly.
- Create tests:
  - `tests/test_tdx_day_parser.py`
  - `tests/test_local_market_repository.py`
  - `tests/test_tdx_daily_importer.py`
  - `tests/test_local_data_provider.py`
  - Extend `tests/test_workflow_api.py`
  - Extend `tests/test_frontend_static.py`
- Modify docs:
  - `docs/project-context.md`
  - Optionally `README.md` if it already contains startup or data setup instructions.

---

### Task 1: TDX `.day` Parser

**Files:**
- Create: `api/app/local_data/__init__.py`
- Create: `api/app/local_data/tdx_day.py`
- Test: `tests/test_tdx_day_parser.py`

- [ ] **Step 1: Write parser tests**

Add `tests/test_tdx_day_parser.py`:

```python
import struct
from pathlib import Path

import pytest

from app.local_data.tdx_day import TdxDayRecord, path_to_symbol, read_tdx_day_file


def _write_day_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        (20260505, 1120, 1150, 1110, 1130, 1200000.0, 10000, 0),
        (20260506, 1150, 1160, 1130, 1136, 1380730880.0, 121638752, 0),
    ]
    path.write_bytes(b"".join(struct.pack("<IIIIIfII", *record) for record in records))


def test_path_to_symbol_maps_tdx_markets() -> None:
    assert path_to_symbol(Path("vipdoc/sh/lday/sh600519.day")) == "600519.SH"
    assert path_to_symbol(Path("vipdoc/sz/lday/sz300750.day")) == "300750.SZ"
    assert path_to_symbol(Path("vipdoc/bj/lday/bj920992.day")) == "920992.BJ"


def test_read_tdx_day_file_decodes_records(tmp_path: Path) -> None:
    source = tmp_path / "vipdoc" / "sz" / "lday" / "sz000001.day"
    _write_day_file(source)

    records = read_tdx_day_file(source)

    assert records == [
        TdxDayRecord(
            symbol="000001.SZ",
            trade_date="2026-05-05",
            open=11.2,
            high=11.5,
            low=11.1,
            close=11.3,
            amount=1200000.0,
            volume=10000,
        ),
        TdxDayRecord(
            symbol="000001.SZ",
            trade_date="2026-05-06",
            open=11.5,
            high=11.6,
            low=11.3,
            close=11.36,
            amount=1380730880.0,
            volume=121638752,
        ),
    ]


def test_read_tdx_day_file_rejects_corrupt_length(tmp_path: Path) -> None:
    source = tmp_path / "vipdoc" / "sh" / "lday" / "sh600519.day"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"123")

    with pytest.raises(ValueError, match="not divisible by 32"):
        read_tdx_day_file(source)
```

- [ ] **Step 2: Run parser tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_tdx_day_parser.py -v
```

Expected: collection fails or tests fail because `app.local_data.tdx_day` does not exist.

- [ ] **Step 3: Create package marker**

Create `api/app/local_data/__init__.py`:

```python
"""Local market data import and query utilities."""
```

- [ ] **Step 4: Implement parser**

Create `api/app/local_data/tdx_day.py`:

```python
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import struct

TDX_DAY_RECORD_SIZE = 32


@dataclass(frozen=True)
class TdxDayRecord:
    symbol: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    amount: float
    volume: int


def path_to_symbol(path: Path) -> str:
    stem = path.stem.lower()
    if len(stem) < 3:
        raise ValueError(f"Cannot derive symbol from path: {path}")

    prefix = stem[:2]
    code = stem[2:]
    market = {"sh": "SH", "sz": "SZ", "bj": "BJ"}.get(prefix)
    if market is None or not code.isdigit():
        raise ValueError(f"Unsupported TDX day filename: {path.name}")
    return f"{code}.{market}"


def read_tdx_day_file(path: Path) -> list[TdxDayRecord]:
    data = path.read_bytes()
    if len(data) == 0:
        return []
    if len(data) % TDX_DAY_RECORD_SIZE != 0:
        raise ValueError(f"{path} size is not divisible by 32 bytes")

    symbol = path_to_symbol(path)
    records: list[TdxDayRecord] = []
    for offset in range(0, len(data), TDX_DAY_RECORD_SIZE):
        raw_date, open_, high, low, close, amount, volume, _reserved = struct.unpack(
            "<IIIIIfII", data[offset : offset + TDX_DAY_RECORD_SIZE]
        )
        parsed_date = date(raw_date // 10000, raw_date // 100 % 100, raw_date % 100)
        records.append(
            TdxDayRecord(
                symbol=symbol,
                trade_date=parsed_date.isoformat(),
                open=open_ / 100,
                high=high / 100,
                low=low / 100,
                close=close / 100,
                amount=float(amount),
                volume=int(volume),
            )
        )
    return records
```

- [ ] **Step 5: Run parser tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_tdx_day_parser.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit parser**

```bash
git add api/app/local_data/__init__.py api/app/local_data/tdx_day.py tests/test_tdx_day_parser.py
git commit -m "feat: parse tdx daily files"
```

---

### Task 2: SQLite Market Repository

**Files:**
- Create: `api/app/local_data/repository.py`
- Test: `tests/test_local_market_repository.py`

- [ ] **Step 1: Write repository tests**

Add `tests/test_local_market_repository.py`:

```python
from pathlib import Path

from app.local_data.repository import LocalMarketRepository, MarketDailyRow


def _row(symbol: str = "000001.SZ", trade_date: str = "2026-05-06") -> MarketDailyRow:
    return MarketDailyRow(
        symbol=symbol,
        trade_date=trade_date,
        open=11.5,
        high=11.6,
        low=11.3,
        close=11.36,
        amount=1380730880.0,
        volume=121638752,
    )


def test_repository_upserts_market_daily_rows(tmp_path: Path) -> None:
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize()

    repository.upsert_market_daily([_row(), _row()])

    assert repository.count_market_daily() == 1
    latest = repository.get_recent_daily_bars("000001.SZ", limit=1)
    assert latest[0].close == 11.36


def test_repository_reports_status(tmp_path: Path) -> None:
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize()
    repository.upsert_market_daily(
        [_row("000001.SZ", "2026-05-05"), _row("300750.SZ", "2026-05-06")]
    )
    repository.record_import_run(
        mode="bootstrap",
        tdx_root="/mnt/d/new_tdx_mock",
        file_count=2,
        row_count=2,
        min_trade_date="2026-05-05",
        max_trade_date="2026-05-06",
        status="success",
        message="imported",
    )

    status = repository.get_status()

    assert status["market_daily_rows"] == 2
    assert status["symbol_count"] == 2
    assert status["latest_trade_date"] == "2026-05-06"
    assert status["last_import"]["mode"] == "bootstrap"


def test_repository_returns_latest_trade_date_for_symbol(tmp_path: Path) -> None:
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize()
    repository.upsert_market_daily(
        [_row("000001.SZ", "2026-05-05"), _row("000001.SZ", "2026-05-06")]
    )

    assert repository.get_latest_trade_date("000001.SZ") == "2026-05-06"
    assert repository.get_latest_trade_date("300750.SZ") == ""
```

- [ ] **Step 2: Run repository tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_local_market_repository.py -v
```

Expected: FAIL because `app.local_data.repository` does not exist.

- [ ] **Step 3: Implement repository**

Create `api/app/local_data/repository.py` with these public APIs:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class MarketDailyRow:
    symbol: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    amount: float
    volume: int


class LocalMarketRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
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
                    source TEXT NOT NULL DEFAULT 'tdx_day',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, trade_date)
                );

                CREATE TABLE IF NOT EXISTS stock_info (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    board TEXT NOT NULL,
                    fundamental_summary TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sector_members (
                    sector_code TEXT NOT NULL,
                    sector_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (sector_code, symbol)
                );

                CREATE TABLE IF NOT EXISTS import_runs (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    tdx_root TEXT NOT NULL,
                    db_path TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    row_count INTEGER NOT NULL,
                    min_trade_date TEXT NOT NULL,
                    max_trade_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                """
            )

    def upsert_market_daily(self, rows: list[MarketDailyRow]) -> int:
        if not rows:
            return 0
        now = datetime.now(UTC).isoformat()
        payload = [
            (
                row.symbol,
                row.trade_date,
                row.open,
                row.high,
                row.low,
                row.close,
                row.amount,
                row.volume,
                "tdx_day",
                now,
            )
            for row in rows
        ]
        with self.connect() as connection:
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
                payload,
            )
        return len(rows)

    def get_recent_daily_bars(self, symbol: str, limit: int = 20) -> list[MarketDailyRow]:
        with self.connect() as connection:
            result = connection.execute(
                """
                SELECT symbol, trade_date, open, high, low, close, amount, volume
                FROM market_daily
                WHERE symbol = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        return [
            MarketDailyRow(
                symbol=row["symbol"],
                trade_date=row["trade_date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                amount=row["amount"],
                volume=row["volume"],
            )
            for row in result
        ]

    def get_latest_trade_date(self, symbol: str) -> str:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(trade_date), '') AS latest_trade_date FROM market_daily WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        return row["latest_trade_date"]

    def list_symbols_with_latest_data(self, limit: int = 50) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT symbol, MAX(trade_date) AS latest_trade_date
                FROM market_daily
                GROUP BY symbol
                ORDER BY latest_trade_date DESC, symbol ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [row["symbol"] for row in rows]

    def count_market_daily(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM market_daily").fetchone()
        return int(row["count"])

    def record_import_run(
        self,
        *,
        mode: str,
        tdx_root: str,
        file_count: int,
        row_count: int,
        min_trade_date: str,
        max_trade_date: str,
        status: str,
        message: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO import_runs (
                    id, started_at, finished_at, mode, tdx_root, db_path, file_count,
                    row_count, min_trade_date, max_trade_date, status, message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    now,
                    now,
                    mode,
                    tdx_root,
                    str(self.db_path),
                    file_count,
                    row_count,
                    min_trade_date,
                    max_trade_date,
                    status,
                    message,
                ),
            )

    def get_status(self) -> dict[str, Any]:
        with self.connect() as connection:
            counts = connection.execute(
                """
                SELECT
                    COUNT(*) AS market_daily_rows,
                    COUNT(DISTINCT symbol) AS symbol_count,
                    COALESCE(MAX(trade_date), '') AS latest_trade_date
                FROM market_daily
                """
            ).fetchone()
            last_import = connection.execute(
                """
                SELECT mode, status, message, finished_at, row_count, max_trade_date
                FROM import_runs
                ORDER BY finished_at DESC
                LIMIT 1
                """
            ).fetchone()
        return {
            "db_path": str(self.db_path),
            "market_daily_rows": int(counts["market_daily_rows"]),
            "symbol_count": int(counts["symbol_count"]),
            "latest_trade_date": counts["latest_trade_date"],
            "last_import": dict(last_import) if last_import else None,
        }
```

- [ ] **Step 4: Run repository tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_local_market_repository.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Commit repository**

```bash
git add api/app/local_data/repository.py tests/test_local_market_repository.py
git commit -m "feat: add local market repository"
```

---

### Task 3: TDX Daily Importer and CLI

**Files:**
- Create: `api/app/local_data/importer.py`
- Create: `scripts/import-tdx-daily.py`
- Test: `tests/test_tdx_daily_importer.py`

- [ ] **Step 1: Write importer tests**

Add `tests/test_tdx_daily_importer.py`:

```python
import struct
from pathlib import Path

from app.local_data.importer import TdxDailyImporter
from app.local_data.repository import LocalMarketRepository


def _write_day(path: Path, trade_date: int, close: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = struct.pack("<IIIIIfII", trade_date, 1000, 1100, 900, close, 1000.0, 100, 0)
    path.write_bytes(payload)


def _write_days(path: Path, records: list[tuple[int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(
        struct.pack("<IIIIIfII", trade_date, 1000, 1100, 900, close, 1000.0, 100, 0)
        for trade_date, close in records
    )
    path.write_bytes(payload)


def test_bootstrap_imports_tdx_day_files(tmp_path: Path) -> None:
    tdx_root = tmp_path / "tdx"
    _write_day(tdx_root / "vipdoc" / "sz" / "lday" / "sz000001.day", 20260506, 1136)
    _write_day(tdx_root / "vipdoc" / "sh" / "lday" / "sh600519.day", 20260506, 137500)
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")

    report = TdxDailyImporter(tdx_root=tdx_root, repository=repository).bootstrap()

    assert report["status"] == "success"
    assert report["file_count"] == 2
    assert report["row_count"] == 2
    assert repository.count_market_daily() == 2


def test_importer_reports_corrupt_files_without_stopping(tmp_path: Path) -> None:
    tdx_root = tmp_path / "tdx"
    _write_day(tdx_root / "vipdoc" / "sz" / "lday" / "sz000001.day", 20260506, 1136)
    corrupt = tdx_root / "vipdoc" / "sh" / "lday" / "sh600519.day"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_bytes(b"bad")
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")

    report = TdxDailyImporter(tdx_root=tdx_root, repository=repository).bootstrap()

    assert report["status"] == "partial"
    assert report["file_count"] == 2
    assert report["row_count"] == 1
    assert report["error_count"] == 1
    assert "sh600519.day" in report["message"]


def test_daily_import_only_imports_newer_rows(tmp_path: Path) -> None:
    tdx_root = tmp_path / "tdx"
    source = tdx_root / "vipdoc" / "sz" / "lday" / "sz000001.day"
    _write_day(source, 20260505, 1130)
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    importer = TdxDailyImporter(tdx_root=tdx_root, repository=repository)
    importer.bootstrap()

    _write_days(source, [(20260505, 1130), (20260506, 1136)])
    report = importer.daily()

    assert report["status"] == "success"
    assert report["row_count"] == 1
    assert repository.count_market_daily() == 2
```

- [ ] **Step 2: Run importer tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_tdx_daily_importer.py -v
```

Expected: FAIL because `app.local_data.importer` does not exist.

- [ ] **Step 3: Implement importer orchestration**

Create `api/app/local_data/importer.py`:

```python
from pathlib import Path
from typing import Any

from app.local_data.repository import LocalMarketRepository, MarketDailyRow
from app.local_data.tdx_day import read_tdx_day_file


class TdxDailyImporter:
    def __init__(self, *, tdx_root: str | Path, repository: LocalMarketRepository) -> None:
        self.tdx_root = Path(tdx_root)
        self.repository = repository

    def bootstrap(self) -> dict[str, Any]:
        return self._import(mode="bootstrap")

    def daily(self) -> dict[str, Any]:
        return self._import(mode="daily")

    def status(self) -> dict[str, Any]:
        self.repository.initialize()
        return self.repository.get_status()

    def _iter_day_files(self) -> list[Path]:
        files: list[Path] = []
        for market in ("sh", "sz", "bj"):
            files.extend((self.tdx_root / "vipdoc" / market / "lday").glob("*.day"))
        return sorted(files)

    def _import(self, mode: str) -> dict[str, Any]:
        self.repository.initialize()
        files = self._iter_day_files()
        imported_rows: list[MarketDailyRow] = []
        errors: list[str] = []

        for path in files:
            try:
                records = read_tdx_day_file(path)
            except ValueError as error:
                errors.append(f"{path.name}: {error}")
                continue

            if mode == "daily" and records:
                latest_trade_date = self.repository.get_latest_trade_date(records[0].symbol)
                records = [
                    record
                    for record in records
                    if latest_trade_date == "" or record.trade_date > latest_trade_date
                ]

            imported_rows.extend(
                MarketDailyRow(
                    symbol=record.symbol,
                    trade_date=record.trade_date,
                    open=record.open,
                    high=record.high,
                    low=record.low,
                    close=record.close,
                    amount=record.amount,
                    volume=record.volume,
                )
                for record in records
            )

        row_count = self.repository.upsert_market_daily(imported_rows)
        dates = [row.trade_date for row in imported_rows]
        status = "partial" if errors else "success"
        message = "imported"
        if errors:
            message = "; ".join(errors[:5])

        self.repository.record_import_run(
            mode=mode,
            tdx_root=str(self.tdx_root),
            file_count=len(files),
            row_count=row_count,
            min_trade_date=min(dates) if dates else "",
            max_trade_date=max(dates) if dates else "",
            status=status,
            message=message,
        )
        return {
            "status": status,
            "file_count": len(files),
            "row_count": row_count,
            "error_count": len(errors),
            "min_trade_date": min(dates) if dates else "",
            "max_trade_date": max(dates) if dates else "",
            "message": message,
        }
```

- [ ] **Step 4: Add CLI wrapper**

Create `scripts/import-tdx-daily.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.local_data.importer import TdxDailyImporter
from app.local_data.repository import LocalMarketRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Tongdaxin .day files into AlphaAgents SQLite data store.")
    parser.add_argument("mode", choices=["bootstrap", "daily", "status"])
    parser.add_argument("--tdx-root", default="", help="Tongdaxin root path containing vipdoc")
    parser.add_argument("--db", default="data/alphaagents.db", help="SQLite database path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = LocalMarketRepository(Path(args.db))
    importer = TdxDailyImporter(tdx_root=Path(args.tdx_root or "."), repository=repository)
    if args.mode == "bootstrap":
        report = importer.bootstrap()
    elif args.mode == "daily":
        report = importer.daily()
    else:
        report = importer.status()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run importer tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_tdx_daily_importer.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Run CLI smoke on a temp fixture**

Run:

```bash
.venv/bin/python scripts/import-tdx-daily.py status --db /tmp/alphaagents-plan-smoke.db
```

Expected: JSON contains `"market_daily_rows": 0`.

- [ ] **Step 7: Commit importer**

```bash
git add api/app/local_data/importer.py scripts/import-tdx-daily.py tests/test_tdx_daily_importer.py
git commit -m "feat: add tdx daily import command"
```

---

### Task 4: Local Data Provider

**Files:**
- Create: `api/app/adapters/local_data.py`
- Modify: `api/app/strategies/basic.py`
- Test: `tests/test_local_data_provider.py`

- [ ] **Step 1: Write LocalDataProvider tests**

Add `tests/test_local_data_provider.py`:

```python
from pathlib import Path

from app.adapters.local_data import LocalDataProvider
from app.local_data.repository import LocalMarketRepository, MarketDailyRow


def _repository(tmp_path: Path) -> LocalMarketRepository:
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize()
    repository.upsert_market_daily(
        [
            MarketDailyRow("000001.SZ", "2026-05-05", 11.2, 11.5, 11.1, 11.3, 1000.0, 100),
            MarketDailyRow("000001.SZ", "2026-05-06", 11.5, 11.6, 11.3, 11.36, 2000.0, 200),
            MarketDailyRow("300750.SZ", "2026-05-06", 457.5, 465.88, 448.63, 460.0, 3000.0, 300),
        ]
    )
    return repository


def test_local_data_provider_uses_configured_stock_pool(tmp_path: Path) -> None:
    provider = LocalDataProvider(repository=_repository(tmp_path), stock_pool=["300750.SZ"])

    assert provider.get_candidate_symbols() == ["300750.SZ"]


def test_local_data_provider_builds_stock_contexts(tmp_path: Path) -> None:
    provider = LocalDataProvider(repository=_repository(tmp_path), stock_pool=["000001.SZ"])

    contexts = provider.get_stock_contexts(["000001.SZ"])

    assert len(contexts) == 1
    assert contexts[0].symbol == "000001.SZ"
    assert "收盘" in contexts[0].market_summary
    assert contexts[0].strategy_hits


def test_local_data_provider_keeps_mock_positions_out_of_tdx_account(tmp_path: Path) -> None:
    provider = LocalDataProvider(repository=_repository(tmp_path), stock_pool=["000001.SZ"])

    positions = provider.get_positions()

    assert positions
    assert positions[0].symbol == "300750"
```

- [ ] **Step 2: Run LocalDataProvider tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_local_data_provider.py -v
```

Expected: FAIL because `app.adapters.local_data` does not exist.

- [ ] **Step 3: Implement LocalDataProvider**

Create `api/app/adapters/local_data.py`:

```python
from app.adapters.broker import MockBrokerDataProvider
from app.domain.models import StockContext
from app.local_data.repository import LocalMarketRepository, MarketDailyRow


class LocalDataProvider:
    def __init__(
        self,
        *,
        repository: LocalMarketRepository,
        stock_pool: list[str] | None = None,
    ) -> None:
        self._repository = repository
        self._stock_pool = stock_pool or []
        self._fallback_positions = MockBrokerDataProvider()

    def get_candidate_symbols(self) -> list[str]:
        if self._stock_pool:
            return self._stock_pool
        return self._repository.list_symbols_with_latest_data(limit=20)

    def get_stock_contexts(self, symbols: list[str]) -> list[StockContext]:
        contexts: list[StockContext] = []
        for symbol in symbols:
            bars = self._repository.get_recent_daily_bars(symbol, limit=5)
            if not bars:
                continue
            latest = bars[0]
            contexts.append(
                StockContext(
                    symbol=symbol,
                    name=symbol,
                    board=symbol.split(".")[-1],
                    market_summary=self._market_summary(latest, bars),
                    fundamental_summary="本地日线数据源暂未导入完整基本面信息。",
                    board_heat_summary="本地日线数据源暂未导入完整板块热度信息。",
                    strategy_hits=self._strategy_hits(latest, bars),
                    profile_summary=f"{symbol} 最近交易日为 {latest.trade_date}。",
                )
            )
        return contexts

    def get_positions(self):
        return self._fallback_positions.get_positions()

    def _market_summary(self, latest: MarketDailyRow, bars: list[MarketDailyRow]) -> str:
        if len(bars) < 2:
            return f"{latest.trade_date} 收盘 {latest.close:.2f}，成交量 {latest.volume}。"
        previous = bars[1]
        change = (latest.close - previous.close) / previous.close * 100
        return (
            f"{latest.trade_date} 收盘 {latest.close:.2f}，"
            f"较前一日 {change:+.2f}%，成交量 {latest.volume}。"
        )

    def _strategy_hits(self, latest: MarketDailyRow, bars: list[MarketDailyRow]) -> list[str]:
        hits: list[str] = []
        if latest.close >= latest.open:
            hits.append("阳线收盘")
        if len(bars) >= 2 and latest.volume > bars[1].volume:
            hits.append("量能放大")
        if latest.close >= max(row.close for row in bars):
            hits.append("短线新高")
        return hits or ["本地日线样本"]
```

- [ ] **Step 4: Loosen BasicSelectionStrategy type annotation**

Modify `api/app/strategies/basic.py`:

```python
from typing import Protocol

from app.domain.models import StockContext


class StockDataProvider(Protocol):
    def get_candidate_symbols(self) -> list[str]: ...

    def get_stock_contexts(self, symbols: list[str]) -> list[StockContext]: ...


class BasicSelectionStrategy:
    def __init__(self, data_provider: StockDataProvider) -> None:
        self._data_provider = data_provider

    def select_candidates(self) -> list[StockContext]:
        symbols = self._data_provider.get_candidate_symbols()
        return self._data_provider.get_stock_contexts(symbols)
```

- [ ] **Step 5: Run provider tests and existing selection tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_local_data_provider.py tests/test_selection_workflow.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit provider**

```bash
git add api/app/adapters/local_data.py api/app/strategies/basic.py tests/test_local_data_provider.py
git commit -m "feat: add local market data provider"
```

---

### Task 5: Settings and Workflow Integration

**Files:**
- Modify: `api/app/core/config.py`
- Modify: `api/app/workflows/service.py`
- Test: `tests/test_workflow_api.py`

- [ ] **Step 1: Write workflow integration test**

Add this test to `tests/test_workflow_api.py`:

```python
import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository, MarketDailyRow
from app.main import create_app


def test_selection_workflow_can_use_local_data_provider(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize()
    repository.upsert_market_daily(
        [
            MarketDailyRow("000001.SZ", "2026-05-05", 11.2, 11.5, 11.1, 11.3, 1000.0, 100),
            MarketDailyRow("000001.SZ", "2026-05-06", 11.5, 11.6, 11.3, 11.36, 2000.0, 200),
        ]
    )
    monkeypatch.setenv("ALPHAAGENTS_DATA_PROVIDER", "local")
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_STOCK_POOL", "000001.SZ")
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())
        response = client.post("/api/v1/workflows/selection/run")
    finally:
        get_settings.cache_clear()
        os.environ.pop("ALPHAAGENTS_DATA_PROVIDER", None)
        os.environ.pop("ALPHAAGENTS_DATA_DB", None)
        os.environ.pop("ALPHAAGENTS_STOCK_POOL", None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["stock"]["symbol"] == "000001.SZ"
```

- [ ] **Step 2: Run integration test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_api.py::test_selection_workflow_can_use_local_data_provider -v
```

Expected: FAIL because settings and workflow service ignore local provider settings.

- [ ] **Step 3: Add settings**

Modify `api/app/core/config.py`:

```python
class Settings(BaseSettings):
    app_name: str = "AlphaAgents"
    api_v1_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    data_provider: str = "mock"
    data_db: str = "data/alphaagents.db"
    tdx_root: str = ""
    stock_pool: str = ""
    cors_origins: str = (
        "http://127.0.0.1:3000,"
        "http://localhost:3000,"
        "http://127.0.0.1:5500,"
        "http://localhost:5500,"
        "null"
    )

    @property
    def resolved_stock_pool(self) -> list[str]:
        return [symbol.strip() for symbol in self.stock_pool.split(",") if symbol.strip()]
```

Keep existing `resolved_cors_origins`.

- [ ] **Step 4: Select provider in workflow service**

Modify `api/app/workflows/service.py` to add imports:

```python
from app.adapters.local_data import LocalDataProvider
from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository
```

Replace `__init__` with:

```python
class AlphaAgentsWorkflowService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.data_provider = self._build_data_provider()
        self.repository = InMemoryAlphaAgentsRepository()
        self.skills = ExpertSkillRegistry.default()

    def _build_data_provider(self):
        if self.settings.data_provider == "local":
            local_repository = LocalMarketRepository(self.settings.data_db)
            local_repository.initialize()
            return LocalDataProvider(
                repository=local_repository,
                stock_pool=self.settings.resolved_stock_pool,
            )
        return MockBrokerDataProvider()
```

- [ ] **Step 5: Add dashboard data status**

Modify `dashboard()` in `api/app/workflows/service.py`:

```python
    def dashboard(self) -> dict[str, object]:
        return {
            "selection_results": self.repository.list_selection_results(),
            "holding_results": self.repository.list_holding_results(),
            "deposition_candidates": self.repository.list_deposition_candidates(),
            "runs": self.repository.list_runs(),
            "data_status": self._data_status(),
        }

    def _data_status(self) -> dict[str, object]:
        status: dict[str, object] = {"provider": self.settings.data_provider}
        if self.settings.data_provider == "local":
            local_repository = LocalMarketRepository(self.settings.data_db)
            local_repository.initialize()
            status.update(local_repository.get_status())
        return status
```

- [ ] **Step 6: Run workflow integration tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_api.py -v
```

Expected: all workflow API tests pass.

- [ ] **Step 7: Commit workflow integration**

```bash
git add api/app/core/config.py api/app/workflows/service.py tests/test_workflow_api.py
git commit -m "feat: wire local data provider into workflows"
```

---

### Task 6: Frontend Data Status

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/scripts/app.js`
- Modify: `frontend/styles/app.css`
- Test: `tests/test_frontend_static.py`

- [ ] **Step 1: Write static frontend assertions**

Extend `tests/test_frontend_static.py`:

```python
def test_frontend_displays_backend_data_status():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    script = Path("frontend/scripts/app.js").read_text(encoding="utf-8")

    assert 'id="data-provider"' in html
    assert 'id="latest-trade-date"' in html
    assert "data_status" in script
    assert "renderDataStatus" in script
```

- [ ] **Step 2: Run frontend static test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_static.py::test_frontend_displays_backend_data_status -v
```

Expected: FAIL because the status DOM ids and renderer do not exist yet.

- [ ] **Step 3: Add status markup**

Modify the status strip in `frontend/index.html` to include:

```html
<div>
  <span class="muted">数据源</span>
  <strong id="data-provider">--</strong>
</div>
<div>
  <span class="muted">最新交易日</span>
  <strong id="latest-trade-date">--</strong>
</div>
```

Keep existing market state, data state, and updated time blocks.

- [ ] **Step 4: Render dashboard data status**

Modify `frontend/scripts/app.js`:

```javascript
const dataProvider = document.querySelector("#data-provider");
const latestTradeDate = document.querySelector("#latest-trade-date");

function renderDataStatus(status = {}) {
  if (dataProvider) {
    dataProvider.textContent = status.provider || "--";
  }
  if (latestTradeDate) {
    latestTradeDate.textContent = status.latest_trade_date || "等待导入";
  }
}
```

Call it from `renderDashboardFromApi`:

```javascript
function renderDashboardFromApi(dashboard, options = {}) {
  renderMetrics(dashboard);
  renderDataStatus(dashboard.data_status || {});
  renderSelectionResults(dashboard.selection_results);
  renderHoldingResults(dashboard.holding_results);
  renderDepositionCandidates(dashboard.deposition_candidates);
  renderExperts(defaultExperts);
  renderRunOutput(dashboard, options.prefix);
}
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_static.py -v
```

Expected: all frontend static tests pass.

- [ ] **Step 6: Commit frontend status**

```bash
git add frontend/index.html frontend/scripts/app.js frontend/styles/app.css tests/test_frontend_static.py
git commit -m "feat: show local data source status"
```

---

### Task 7: Documentation and Verification

**Files:**
- Modify: `docs/project-context.md`
- Modify: `README.md`

- [ ] **Step 1: Add manual data flow docs**

Add this section to `docs/project-context.md`:

```markdown
## 本地 TDX 日线数据源

AlphaAgents 支持把通达信下载好的 `.day` 日线文件导入项目内 SQLite 数据仓。通达信目录只作为只读原始来源，后端运行时读取 `data/alphaagents.db`。

推荐手动流程：

1. 在通达信金融终端（量化模拟）里手动下载日线数据。
2. 在 WSL 项目目录运行：
   `.venv/bin/python scripts/import-tdx-daily.py daily --tdx-root "/mnt/d/new_tdx_mock" --db data/alphaagents.db`
3. 查看导入状态：
   `.venv/bin/python scripts/import-tdx-daily.py status --db data/alphaagents.db`
4. 启动后端时使用：
   `ALPHAAGENTS_DATA_PROVIDER=local ALPHAAGENTS_DATA_DB=data/alphaagents.db ALPHAAGENTS_STOCK_POOL=000001.SZ,300750.SZ,600519.SH scripts/start-backend.sh --no-reload`

本地数据源只提供投研和复盘所需行情数据，不接入账户、委托、下单、撤单等交易能力。
```

- [ ] **Step 2: Run full tests**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Ruff**

Run:

```bash
.venv/bin/python -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 4: Manual real-data import smoke**

Run only if `/mnt/d/new_tdx_mock/vipdoc` exists:

```bash
.venv/bin/python scripts/import-tdx-daily.py bootstrap --tdx-root "/mnt/d/new_tdx_mock" --db data/alphaagents.db
.venv/bin/python scripts/import-tdx-daily.py status --db data/alphaagents.db
```

Expected: JSON contains `latest_trade_date` equal to `2026-05-06`, and both `market_daily_rows` and `symbol_count` are greater than `0`. With the current `D:\new_tdx_mock\vipdoc` dataset, the actual counts should be much larger than the tiny fixture counts used in automated tests.

- [ ] **Step 5: Run local provider workflow smoke**

Run:

```bash
ALPHAAGENTS_DATA_PROVIDER=local \
ALPHAAGENTS_DATA_DB=data/alphaagents.db \
ALPHAAGENTS_STOCK_POOL=000001.SZ,300750.SZ,600519.SH \
.venv/bin/python -m pytest tests/test_workflow_api.py::test_selection_workflow_can_use_local_data_provider -v
```

Expected: PASS.

- [ ] **Step 6: Commit docs**

```bash
git add docs/project-context.md README.md
git commit -m "docs: document local tdx data workflow"
```

- [ ] **Step 7: Final verification before handoff**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
git status --short
```

Expected:
- pytest reports all tests passed.
- Ruff reports `All checks passed!`.
- `git status --short` shows no uncommitted files from this implementation, except user-approved unrelated work if present before execution.
