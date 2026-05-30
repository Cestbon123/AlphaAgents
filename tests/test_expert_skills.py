from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import HoldingAction, SelectionAction
from app.domain.models import ExpertJudgement, HoldingPosition, StockContext
from app.expert_skills.registry import ExpertSkillRegistry
from app.strategies.basic import BasicSelectionStrategy


def test_basic_strategy_returns_candidates_with_strategy_hits():
    provider = MockBrokerDataProvider()
    strategy = BasicSelectionStrategy(provider)

    candidates = strategy.select_candidates()

    assert candidates
    assert all(candidate.strategy_hits for candidate in candidates)


def test_selection_expert_returns_structured_judgement():
    provider = MockBrokerDataProvider()
    stock = provider.get_stock_contexts(["300750"])[0]
    registry = ExpertSkillRegistry.default()

    result = registry.evaluate_selection(stock)

    assert result.action == SelectionAction.BUY
    assert result.expert_judgements[0].reason
    assert result.core_reason


def test_selection_expert_maps_board_heat_average_to_watch():
    provider = MockBrokerDataProvider()
    stock = provider.get_stock_contexts(["600519"])[0]
    registry = ExpertSkillRegistry.default()

    result = registry.evaluate_selection(stock)

    assert result.action == SelectionAction.WATCH


def test_selection_expert_maps_weak_candidate_to_drop():
    stock = StockContext(
        symbol="688001",
        name="Weak Sample",
        board="Other",
        market_summary="No clear momentum",
        fundamental_summary="No near-term catalyst",
        board_heat_summary="Board liquidity remains muted",
        strategy_hits=["Pullback without confirmation"],
        profile_summary="Crafted weak sample",
    )
    registry = ExpertSkillRegistry.default()

    result = registry.evaluate_selection(stock)

    assert result.action == SelectionAction.DROP


def test_holding_expert_maps_repairing_position_to_hold():
    provider = MockBrokerDataProvider()
    stock = provider.get_stock_contexts(["300750"])[0]
    position = provider.get_positions()[0]
    registry = ExpertSkillRegistry.default()

    result = registry.evaluate_holding(position, stock)

    assert result.action == HoldingAction.HOLD
    assert result.next_day_reminder
    assert result.risks


def test_holding_expert_maps_weak_position_to_let_run():
    stock = StockContext(
        symbol="000001",
        name="Weak Holding",
        board="Banking",
        market_summary="Momentum faded after weak rebound",
        fundamental_summary="Stable but lacks catalyst",
        board_heat_summary="Low board heat",
        strategy_hits=["Failed rebound"],
        profile_summary="Crafted weak holding sample",
    )
    position = HoldingPosition(
        symbol="000001",
        name="Weak Holding",
        quantity=100,
        cost_price=10.0,
        current_price=9.8,
        holding_days=4,
    )
    registry = ExpertSkillRegistry.default()

    result = registry.evaluate_holding(position, stock)

    assert result.action == HoldingAction.LET_RUN
    assert "Weak Holding" in result.next_day_reminder


def test_holding_expert_maps_unknown_conclusion_to_clear():
    class UnknownHoldingSkill:
        name = "unknown holding skill"

        def evaluate(self, stock: StockContext) -> ExpertJudgement:
            return ExpertJudgement(
                skill_name=self.name,
                scenario="holding judgement",
                conclusion="无法判断",
                reason=f"{stock.name} has insufficient signal clarity",
                risks=["Signal is ambiguous"],
            )

    stock = StockContext(
        symbol="000002",
        name="Unknown Holding",
        board="Real Estate",
        market_summary="Mixed intraday movement",
        fundamental_summary="Unclear near-term catalyst",
        board_heat_summary="Board signal unclear",
        strategy_hits=["Ambiguous signal"],
        profile_summary="Crafted unknown holding sample",
    )
    position = HoldingPosition(
        symbol="000002",
        name="Unknown Holding",
        quantity=100,
        cost_price=12.0,
        current_price=12.1,
        holding_days=2,
    )
    registry = ExpertSkillRegistry.default()
    registry.holding_skills = [UnknownHoldingSkill()]

    result = registry.evaluate_holding(position, stock)

    assert result.action == HoldingAction.CLEAR
    assert result.action_reason == "Unknown Holding has insufficient signal clarity"
