from app.domain.models import ResearchSupplementBundle
from app.local_data.repository import LocalMarketRepository
from app.workflows.research import ResearchWorkflow
from app.workflows.research_context import ResearchContextBuilder
from app.workflows.research_prompts import analyst_prompt, manager_prompt


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


def _context(tmp_path):
    repository = LocalMarketRepository(tmp_path / "market.db")
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
                "open": 10.0,
                "high": 10.4,
                "low": 9.8,
                "close": 10.1 + day * 0.01,
                "amount": 1000.0,
                "volume": 100,
            }
            for day in range(1, 23)
        ],
    )
    return ResearchContextBuilder(
        market_repository=repository,
        external_provider=StubExternalProvider(),
    ).build("000001.SZ")


def test_research_workflow_uses_tradingagents_style_llm_prompts(tmp_path):
    context = _context(tmp_path)

    class FakeLLM:
        is_configured = True

        def __init__(self):
            self.prompts = []

        def complete(self, prompt):
            self.prompts.append(prompt)
            if "第一行必须是" in prompt:
                return "最终结论：观察\n\n证据有价值，但仍需要验证资金和公告。"
            return (
                "核心判断：基于给定数据形成研究意见。\n\n"
                "| 观察点 | 证据 | 解释 | 风险 |\n"
                "| --- | --- | --- | --- |\n"
                "| 测试 | 数据 | 分析 | 缺口 |"
            )

    llm = FakeLLM()
    report = ResearchWorkflow(llm_client=llm).run(context)

    assert report.generation_mode == "llm_tradingagents_style"
    assert report.final_decision == "观察"
    assert len(report.analyst_reports) == 9
    assert any("TradingAgents 风格" in prompt for prompt in llm.prompts)
    assert any("多方研究员" in prompt for prompt in llm.prompts)
    assert any("空方研究员" in prompt for prompt in llm.prompts)
    assert "TradingAgents 风格多专家研究报告" in report.report_text


def test_research_prompts_are_data_bound_and_non_trading(tmp_path):
    context = _context(tmp_path)

    prompt = analyst_prompt("技术分析专家", context)
    final_prompt = manager_prompt(context, [])

    assert context.symbol in prompt
    assert "只能基于这些数据作分析" in prompt
    assert "不得使用买入、卖出、下单、仓位建议" in prompt
    assert "评级只能使用以下四个之一" in final_prompt
