from types import SimpleNamespace

from app.api.endpoints import stocks


class _ShortHistoryRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def get_daily_bars(self, symbol, limit=120):
        return [
            {
                "time": f"2026-05-{day:02d}",
                "close": 10 + day / 10,
                "high": 10.5 + day / 10,
                "low": 9.5 + day / 10,
            }
            for day in range(1, 21)
        ]


def test_stock_alerts_handles_short_history(monkeypatch):
    monkeypatch.setattr(stocks, "LocalMarketRepository", _ShortHistoryRepository)
    monkeypatch.setattr(stocks, "get_settings", lambda: SimpleNamespace(data_db=":memory:"))

    result = stocks._compute_alerts("000001.SZ")

    assert result["long_short_line"] is None
    assert result["alerts"][0]["type"] == "warning"
    assert "114" in result["alerts"][0]["message"]
