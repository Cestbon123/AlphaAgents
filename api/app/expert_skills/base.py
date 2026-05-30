from abc import ABC, abstractmethod

from app.domain.models import ExpertJudgement, StockContext


class SelectionExpertSkill(ABC):
    name: str

    @abstractmethod
    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        raise NotImplementedError


class HoldingExpertSkill(ABC):
    name: str

    @abstractmethod
    def evaluate(self, stock: StockContext) -> ExpertJudgement:
        raise NotImplementedError
