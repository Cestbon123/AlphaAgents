from app.domain.models import ResearchSupplementBundle
from app.external_data.cache import ExternalDataCache
from app.local_data.repository import LocalMarketRepository
from app.workflows.research import ResearchWorkflow
from app.workflows.research_context import ResearchContextBuilder


class StubExternalProvider:
    def supplement(self, symbol):
        return ResearchSupplementBundle(
            valuation={"pe_ttm": 12.5, "pb": 1.1, "market_cap": 1200},
            money_flow={"trade_date": "2026-05-22", "main_net_inflow": 1000},
            dragon_tiger=[{"reason": "日涨幅偏离值达7%"}],
            sectors=[{"sector_name": "银行", "sector_type": "行业"}],
            announcements=[{"title": "年度报告"}],
            news=[{"title": "经营稳健"}],
        )


def _seed_market(repository: LocalMarketRepository):
    repository.upsert_security_profiles(
        [
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "market": "SZ",
                "market_category": "主板",
                "is_st": False,
            }
        ]
    )
    repository.upsert_daily_bars(
        "000001.SZ",
        [
            {
                "trade_date": f"2026-05-{day:02d}",
                "open": 10.0 + day * 0.01,
                "high": 10.4 + day * 0.01,
                "low": 9.8 + day * 0.01,
                "close": 10.1 + day * 0.01,
                "amount": 1000.0 + day,
                "volume": 100 + day,
            }
            for day in range(1, 23)
        ],
    )


def test_research_context_builder_merges_local_and_external_data(tmp_path):
    repository = LocalMarketRepository(tmp_path / "market.db")
    _seed_market(repository)

    context = ResearchContextBuilder(
        market_repository=repository,
        external_provider=StubExternalProvider(),
    ).build("000001")

    assert context.symbol == "000001.SZ"
    assert context.name == "平安银行"
    assert context.latest_close is not None
    assert context.supplement.valuation["pe_ttm"] == 12.5
    assert context.sectors[0]["sector_name"] == "银行"
    assert "MACD" in context.technical_summary


def test_research_workflow_generates_all_roles_and_report_text(tmp_path):
    repository = LocalMarketRepository(tmp_path / "market.db")
    _seed_market(repository)
    context = ResearchContextBuilder(
        market_repository=repository,
        external_provider=StubExternalProvider(),
    ).build("000001.SZ")

    report = ResearchWorkflow().run(context)

    assert report.final_decision in {"重点跟踪", "观察", "暂不跟踪", "放弃"}
    assert [item.role for item in report.analyst_reports] == ResearchWorkflow.roles
    assert "多专家研究报告" in report.report_text
    assert "交易指令" in report.report_text
    assert "买入" not in report.final_decision


def test_research_context_records_data_gaps_when_external_data_missing(tmp_path):
    repository = LocalMarketRepository(tmp_path / "market.db")
    cache = ExternalDataCache(tmp_path / "workflow.db")

    class FailingProvider:
        def supplement(self, symbol):
            return ResearchSupplementBundle(data_gaps=["valuation: offline"])

    context = ResearchContextBuilder(
        market_repository=repository,
        external_provider=FailingProvider(),
    ).build("000001.SZ")

    assert any("本地日线数据缺失" in gap for gap in context.data_gaps)
    assert any("valuation" in gap for gap in context.data_gaps)
    assert cache.get("000001.SZ", "valuation") is None
