from app.local_data.repository import LocalMarketRepository


def _bar(trade_date: str, close: float = 1.5) -> dict:
    return {
        "trade_date": trade_date,
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": close,
        "amount": 123.0,
        "volume": 456,
    }


def test_repository_initializes_schema(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")

    repository.initialize_schema()

    status = repository.status()
    assert status["bar_count"] == 0
    assert status["symbol_count"] == 0
    assert status["latest_trade_date"] is None


def test_connect_configures_busy_timeout_for_concurrent_imports(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")

    with repository._connect() as connection:
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert busy_timeout >= 30000


def test_initialize_schema_enables_wal_journal_mode(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")

    repository.initialize_schema()

    with repository._connect() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert journal_mode == "wal"


def test_get_daily_bars_returns_empty_when_db_file_is_uninitialized(tmp_path):
    db_path = tmp_path / "alphaagents.db"
    db_path.write_bytes(b"")
    repository = LocalMarketRepository(db_path)

    assert repository.get_daily_bars("300750.SZ", limit=10) == []


def test_status_returns_empty_when_db_file_is_uninitialized(tmp_path):
    db_path = tmp_path / "alphaagents.db"
    db_path.write_bytes(b"")
    repository = LocalMarketRepository(db_path)

    status = repository.status()

    assert status["bar_count"] == 0
    assert status["symbol_count"] == 0
    assert status["latest_trade_date"] is None
    assert status["latest_import_run"] is None
    assert "uninitialized" in status["message"]


def test_status_returns_empty_when_db_file_is_corrupt(tmp_path):
    db_path = tmp_path / "alphaagents.db"
    db_path.write_bytes(b"not a sqlite database")
    repository = LocalMarketRepository(db_path)

    status = repository.status()

    assert status["bar_count"] == 0
    assert status["symbol_count"] == 0
    assert status["latest_trade_date"] is None
    assert status["latest_import_run"] is None
    assert "unavailable" in status["message"]


def test_upsert_daily_bars_deduplicates_symbol_and_trade_date(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize_schema()

    repository.upsert_daily_bars("300750.SZ", [_bar("2026-05-06", close=1.5)])
    repository.upsert_daily_bars("300750.SZ", [_bar("2026-05-06", close=1.8)])

    bars = repository.get_daily_bars("300750.SZ", limit=10)
    assert len(bars) == 1
    assert bars[0]["close"] == 1.8


def test_get_daily_bars_returns_recent_rows_in_ascending_time_order(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize_schema()
    repository.upsert_daily_bars(
        "300750.SZ",
        [
            _bar("2026-05-01", close=1.1),
            _bar("2026-05-02", close=1.2),
            _bar("2026-05-03", close=1.3),
        ],
    )

    bars = repository.get_daily_bars("300750.SZ", limit=2)

    assert [bar["time"] for bar in bars] == ["2026-05-02", "2026-05-03"]
    assert [bar["close"] for bar in bars] == [1.2, 1.3]


def test_list_symbols_returns_distinct_symbols_in_order(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize_schema()
    repository.upsert_daily_bars("600519.SH", [_bar("2026-05-06")])
    repository.upsert_daily_bars("000001.SZ", [_bar("2026-05-06")])
    repository.upsert_daily_bars("600519.SH", [_bar("2026-05-07")])

    assert repository.list_symbols() == ["000001.SZ", "600519.SH"]


def test_security_metadata_can_be_saved_and_read_by_symbol(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")

    repository.upsert_security_metadata(
        [
            {"symbol": "000001.SH", "name": "上证指数", "market": "SH"},
            {"symbol": "600519.SH", "name": "贵州茅台", "market": "SH"},
        ]
    )

    assert repository.get_security_name("000001.SH") == "上证指数"
    assert repository.get_security_name("600519.SH") == "贵州茅台"
    assert repository.get_security_name("000000.SH") is None


def test_status_summarizes_market_data_and_import_runs(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize_schema()
    repository.upsert_daily_bars("300750.SZ", [_bar("2026-05-06")])
    repository.upsert_daily_bars("600519.SH", [_bar("2026-05-05")])
    repository.record_import_run(
        source="tdx",
        status="success",
        tdx_root="/mnt/d/new_tdx_mock",
        imported_files=2,
        imported_bars=2,
        message="ok",
    )

    status = repository.status()

    assert status["bar_count"] == 2
    assert status["symbol_count"] == 2
    assert status["latest_trade_date"] == "2026-05-06"
    assert status["latest_import_run"]["status"] == "success"
    assert status["latest_import_run"]["imported_files"] == 2


def test_list_stock_quotes_filters_out_index_symbols(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    repository.initialize_schema()
    repository.upsert_security_metadata(
        [
            {"symbol": "000009.SZ", "name": "中国宝安", "market": "SZ"},
            {"symbol": "000009.SH", "name": "上证380", "market": "SH"},
            {"symbol": "880471.SH", "name": "银行", "market": "SH"},
        ]
    )
    repository.upsert_daily_bars("000009.SZ", [_bar("2026-05-06", close=10.0)])
    repository.upsert_daily_bars("000009.SH", [_bar("2026-05-06", close=20.0)])
    repository.upsert_daily_bars("880471.SH", [_bar("2026-05-06", close=30.0)])
    repository.upsert_sector_metadata(
        [{"sector_code": "880001.SH", "sector_name": "测试板块", "sector_type": "概念"}]
    )
    repository.upsert_sector_members(
        [
            {"sector_code": "880001.SH", "symbol": "000009.SZ"},
            {"sector_code": "880001.SH", "symbol": "000009.SH"},
            {"sector_code": "880001.SH", "symbol": "880471.SH"},
        ]
    )

    all_quotes = repository.list_stock_quotes()
    sector_quotes = repository.list_stock_quotes(sector_code="880001.SH")

    assert [quote["symbol"] for quote in all_quotes] == ["000009.SZ"]
    assert [quote["symbol"] for quote in sector_quotes] == ["000009.SZ"]
