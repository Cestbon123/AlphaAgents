from datetime import date, timedelta

from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository
from app.strategies.zhixing import ZhixingTrendSelectionStrategy, _lte
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


def test_zhixing_strategy_selects_formula_matches_and_excludes_boards(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    bars = _zhixing_match_bars()
    repository.upsert_security_metadata(
        [{"symbol": "600001.SH", "name": "测试银行", "market": "SH"}]
    )
    repository.upsert_daily_bars("600001.SH", bars)
    repository.upsert_daily_bars("300001.SZ", bars)
    repository.upsert_daily_bars("688001.SH", bars)
    repository.upsert_daily_bars("920001.BJ", bars)

    strategy = ZhixingTrendSelectionStrategy(
        repository=repository,
        stock_pool=["600001.SH", "300001.SZ", "688001.SH", "920001.BJ"],
    )

    candidates = strategy.select_candidates()

    assert [candidate.symbol for candidate in candidates] == ["600001.SH"]
    candidate = candidates[0]
    assert candidate.name == "测试银行"
    assert any("知行趋势线选股公式" in hit for hit in candidate.strategy_hits)
    assert "J=" in candidate.market_summary
    assert "振幅=" in candidate.market_summary


def test_zhixing_strategy_excludes_st_names(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    bars = _zhixing_match_bars()
    repository.upsert_security_metadata(
        [
            {"symbol": "600001.SH", "name": "测试银行", "market": "SH"},
            {"symbol": "600002.SH", "name": "ST测试", "market": "SH"},
        ]
    )
    repository.upsert_daily_bars("600001.SH", bars)
    repository.upsert_daily_bars("600002.SH", bars)

    strategy = ZhixingTrendSelectionStrategy(
        repository=repository,
        stock_pool=["600001.SH", "600002.SH"],
    )

    candidates = strategy.select_candidates()

    assert [candidate.symbol for candidate in candidates] == ["600001.SH"]


def test_zhixing_strategy_uses_tdxquant_profiles_for_default_exclusions(tmp_path):
    repository = LocalMarketRepository(tmp_path / "alphaagents.db")
    bars = _zhixing_match_bars()
    repository.upsert_security_profiles(
        [
            {
                "symbol": "600001.SH",
                "name": "测试银行",
                "market": "SH",
                "market_category": "沪市主板",
                "is_st": False,
            },
            {
                "symbol": "600002.SH",
                "name": "测试科创",
                "market": "SH",
                "market_category": "科创板",
                "is_st": False,
            },
            {
                "symbol": "600003.SH",
                "name": "测试风险",
                "market": "SH",
                "market_category": "沪市主板",
                "is_st": True,
            },
        ]
    )
    repository.upsert_sector_metadata(
        [{"sector_code": "881155.SH", "sector_name": "银行", "sector_type": "行业"}]
    )
    repository.upsert_sector_members(
        [{"sector_code": "881155.SH", "symbol": "600001.SH"}]
    )
    for symbol in ("600001.SH", "600002.SH", "600003.SH"):
        repository.upsert_daily_bars(symbol, bars)

    strategy = ZhixingTrendSelectionStrategy(
        repository=repository,
        stock_pool=["600001.SH", "600002.SH", "600003.SH"],
    )

    candidates = strategy.select_candidates()

    assert [candidate.symbol for candidate in candidates] == ["600001.SH"]
    assert candidates[0].name == "测试银行"
    assert candidates[0].board == "银行"


def test_zhixing_percent_boundary_allows_exact_four_percent_amplitude():
    value = (43.84 - 42.12) / 43.0 * 100

    assert value > 4
    assert _lte(value, 4)


def test_workflow_service_can_use_local_zhixing_selection(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.upsert_daily_bars("600001.SH", _zhixing_match_bars())
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "local")
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_STOCK_POOL", "600001.SH")
    get_settings.cache_clear()

    service = AlphaAgentsWorkflowService()
    result = service.run_selection()

    assert result["workflow"] == "选股"
    assert len(result["results"]) == 1
    assert result["results"][0].stock.symbol == "600001.SH"
    assert result["results"][0].matched_standards

    get_settings.cache_clear()
