from app.domain.models import ExpertJudgement, StockContext
from app.expert_skills.base import HoldingExpertSkill, SelectionExpertSkill


class BoardHeatSelectionSkill(SelectionExpertSkill):
    name = "板块热度选股专家"

    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        if "热度回升" in stock.board_heat_summary or "主线" in " ".join(stock.strategy_hits):
            conclusion = "支持买入候选"
            reason = "策略命中主线或板块热度回升，具备第二天择机买入价值。"
            risks = ["若板块次日退潮，需要降低执行优先级。"]
        elif "热度一般" in stock.board_heat_summary:
            conclusion = "建议待观察"
            reason = "基本面或趋势有参考价值，但板块热度不足，买点需要等待确认。"
            risks = ["板块缺少资金回流时不宜主动买入。"]
        else:
            conclusion = "建议放弃"
            reason = "当前板块和策略信号不足，不适合作为次日重点候选。"
            risks = ["继续跟踪会占用注意力。"]

        return ExpertJudgement(
            skill_name=self.name,
            scenario="选股判断",
            conclusion=conclusion,
            reason=reason,
            risks=risks,
        )


class TrendHoldingSkill(HoldingExpertSkill):
    name = "趋势持股专家"

    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        if "放量修复" in stock.market_summary:
            conclusion = "继续持有"
            reason = "当日行情仍处于修复状态，暂不急于结束持仓。"
            risks = ["次日若放量冲高回落，需要考虑放飞。"]
        else:
            conclusion = "降低仓位"
            reason = "行情动能不足，持仓需要更重视风险控制。"
            risks = ["弱势延续时应考虑止损或清仓。"]

        return ExpertJudgement(
            skill_name=self.name,
            scenario="持股判断",
            conclusion=conclusion,
            reason=reason,
            risks=risks,
        )
