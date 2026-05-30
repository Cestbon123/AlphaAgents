from app.domain.enums import HoldingAction, SelectionAction, WorkflowType
from app.domain.models import StockContext


def test_selection_actions_are_fixed():
    assert [action.value for action in SelectionAction] == ["买入", "待观察", "放弃"]


def test_holding_actions_are_fixed():
    assert [action.value for action in HoldingAction] == [
        "继续持有",
        "放飞",
        "止损",
        "清仓",
    ]


def test_stock_context_contains_required_fields():
    context = StockContext(
        symbol="000001",
        name="平安银行",
        board="银行",
        market_summary="缩量震荡",
        fundamental_summary="经营稳定",
        board_heat_summary="板块热度一般",
        strategy_hits=["趋势回踩"],
        profile_summary="历史上更适合低波动观察",
    )

    assert context.symbol == "000001"
    assert context.strategy_hits == ["趋势回踩"]
    assert WorkflowType.SELECTION.value == "选股"
