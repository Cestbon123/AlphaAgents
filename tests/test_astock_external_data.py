import pytest

from app.domain.models import ResearchSupplementBundle
from app.external_data.astock import (
    AStockDataUnavailable,
    ExternalResearchDataProvider,
    normalize_eastmoney_money_flow,
    normalize_tencent_quote,
)
from app.external_data.cache import ExternalDataCache


def test_tencent_quote_adapter_normalizes_valuation_fields():
    fields = [""] * 48
    fields[1] = "平安银行"
    fields[3] = "11.23"
    fields[38] = "1.25"
    fields[39] = "6.8"
    fields[45] = "2180"
    fields[46] = "0.72"
    raw_text = f'v_sz000001="{"~".join(fields)}";'

    payload = normalize_tencent_quote(raw_text, "000001.SZ")

    assert payload["name"] == "平安银行"
    assert payload["price"] == 11.23
    assert payload["pe_ttm"] == 6.8
    assert payload["pb"] == 0.72
    assert payload["market_cap"] == 2180


def test_eastmoney_money_flow_adapter_normalizes_latest_kline():
    payload = {"data": {"klines": ["2026-05-22,1200,-10,0,300"]}}

    normalized = normalize_eastmoney_money_flow(payload)

    assert normalized["trade_date"] == "2026-05-22"
    assert normalized["main_net_inflow"] == 1200
    assert normalized["small_net_inflow"] == 300


def test_external_provider_prefers_cache_and_records_loader_failures(tmp_path):
    cache = ExternalDataCache(tmp_path / "workflow.db")
    cache.set("000001.SZ", "valuation", {"pe_ttm": 8.5})

    class FailingClient:
        def valuation(self, symbol):
            raise AssertionError("cached valuation should be used")

        def money_flow(self, symbol):
            raise AStockDataUnavailable("offline")

        def dragon_tiger(self, symbol):
            return []

        def sectors(self, symbol):
            return []

        def announcements(self, symbol):
            return []

        def news(self, symbol):
            return []

    supplement = ExternalResearchDataProvider(cache=cache, client=FailingClient()).supplement(
        "000001.SZ"
    )

    assert isinstance(supplement, ResearchSupplementBundle)
    assert supplement.valuation == {"pe_ttm": 8.5}
    assert any("money_flow" in gap for gap in supplement.data_gaps)


def test_money_flow_adapter_reports_empty_payload():
    with pytest.raises(AStockDataUnavailable):
        normalize_eastmoney_money_flow({"data": {"klines": []}})
