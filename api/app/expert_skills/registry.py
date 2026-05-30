from app.domain.enums import HoldingAction, SelectionAction
from app.domain.models import HoldingAnalysisResult, HoldingPosition, SelectionResult, StockContext
from app.expert_skills.builtins import BoardHeatSelectionSkill, TrendHoldingSkill


class ExpertSkillRegistry:
    def __init__(self) -> None:
        self.selection_skills = [BoardHeatSelectionSkill()]
        self.holding_skills = [TrendHoldingSkill()]

    @classmethod
    def default(cls) -> "ExpertSkillRegistry":
        return cls()

    def evaluate_selection(self, stock: StockContext) -> SelectionResult:
        judgements = [skill.evaluate(stock) for skill in self.selection_skills]
        first = judgements[0]
        action = self._selection_action_from_conclusion(first.conclusion)
        return SelectionResult(
            stock=stock,
            matched_standards=stock.strategy_hits,
            match_reason=f"{stock.name} 命中：{'、'.join(stock.strategy_hits)}",
            expert_judgements=judgements,
            action=action,
            core_reason=first.reason,
            risks=first.risks,
            strategy_snapshot=stock.strategy_snapshot,
        )

    def evaluate_holding(
        self, position: HoldingPosition, stock: StockContext
    ) -> HoldingAnalysisResult:
        judgements = [skill.evaluate(stock) for skill in self.holding_skills]
        first = judgements[0]
        action = self._holding_action_from_conclusion(first.conclusion)
        return HoldingAnalysisResult(
            position=position,
            stock=stock,
            expert_judgements=judgements,
            action=action,
            action_reason=first.reason,
            next_day_reminder=f"次日关注 {position.name} 的量能和关键价位变化。",
            risks=first.risks,
        )

    def _selection_action_from_conclusion(self, conclusion: str) -> SelectionAction:
        if "买入" in conclusion:
            return SelectionAction.BUY
        if "待观察" in conclusion:
            return SelectionAction.WATCH
        return SelectionAction.DROP

    def _holding_action_from_conclusion(self, conclusion: str) -> HoldingAction:
        if "继续持有" in conclusion:
            return HoldingAction.HOLD
        if "放飞" in conclusion or "降低仓位" in conclusion:
            return HoldingAction.LET_RUN
        if "止损" in conclusion:
            return HoldingAction.STOP_LOSS
        if "清仓" in conclusion:
            return HoldingAction.CLEAR
        return HoldingAction.CLEAR
