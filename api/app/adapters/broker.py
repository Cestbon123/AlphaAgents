from app.domain.models import HoldingPosition, StockContext


class MockBrokerDataProvider:
    def get_candidate_symbols(self) -> list[str]:
        return ["000001", "300750", "600519"]

    def get_stock_contexts(self, symbols: list[str]) -> list[StockContext]:
        sample = {
            "000001": StockContext(
                symbol="000001",
                name="平安银行",
                board="银行",
                market_summary="缩量震荡，价格靠近短期均线",
                fundamental_summary="基本面稳定，弹性一般",
                board_heat_summary="银行板块热度偏低",
                strategy_hits=["趋势回踩"],
                profile_summary="适合作为低波动观察样本",
            ),
            "300750": StockContext(
                symbol="300750",
                name="宁德时代",
                board="新能源",
                market_summary="放量修复，板块资金回流",
                fundamental_summary="龙头基本面强，机构关注度高",
                board_heat_summary="新能源板块热度回升",
                strategy_hits=["主线回流", "龙头修复"],
                profile_summary="历史上适合观察板块回流强度",
            ),
            "600519": StockContext(
                symbol="600519",
                name="贵州茅台",
                board="白酒",
                market_summary="低波动横盘",
                fundamental_summary="基本面强，但短期催化有限",
                board_heat_summary="白酒板块热度一般",
                strategy_hits=["机构趋势"],
                profile_summary="更适合作为长期画像标的",
            ),
        }
        return [sample[symbol] for symbol in symbols if symbol in sample]

    def get_positions(self) -> list[HoldingPosition]:
        return [
            HoldingPosition(
                symbol="300750",
                name="宁德时代",
                quantity=100,
                cost_price=180.0,
                current_price=192.5,
                holding_days=5,
            )
        ]
