from datetime import date, timedelta

from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository
from app.workflows.service import AlphaAgentsWorkflowService


def _zhixing_match_bars() -> list[dict]:
    start = date(2026, 1, 1)
    bars = []
    for index in range(130):
        if index < 112:
            close = 10 + index * 0.09
        elif index < 121:
            close = 21.0 - (index - 112) * 0.18
        else:
            close = 19.55 - (index - 121) * 0.08

        if index == 129:
            close = 18.9

        bars.append(
            {
                "trade_date": (start + timedelta(days=index)).isoformat(),
                "open": close + 0.05,
                "high": close + 0.16,
                "low": close - 0.12,
                "close": close,
                "amount": 1_000_000 + index,
                "volume": 100_000 + index,
            }
        )
    return bars


def test_zhixing_selection_result_serializes_strategy_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    bars = _zhixing_match_bars()
    repository.upsert_security_metadata(
        [{"symbol": "600001.SH", "name": "测试银行", "market": "SH"}]
    )
    repository.upsert_daily_bars("600001.SH", bars)
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "local")
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_STOCK_POOL", "600001.SH")
    get_settings.cache_clear()

    service = AlphaAgentsWorkflowService()
    result = service.run_selection()
    payload = result["results"][0].model_dump(mode="json")

    snapshot = payload["strategy_snapshot"]
    assert snapshot["strategy_name"] == "知行趋势线"
    assert snapshot["latest_trade_date"] == bars[-1]["trade_date"]

    conditions = snapshot["conditions"]
    assert set(conditions) >= {
        "kdj_j",
        "short_trend_above_long_short",
        "amplitude_pct",
        "change_pct",
        "default_exclusions",
    }
    assert all(conditions[key]["passed"] is True for key in conditions)

    get_settings.cache_clear()
