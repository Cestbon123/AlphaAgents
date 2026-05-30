from app.adapters.broker import MockBrokerDataProvider
from app.domain.models import HoldingAnalysisResult, HoldingPosition, StockContext
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository


class HoldingWorkflow:
    def __init__(
        self,
        data_provider: MockBrokerDataProvider | None = None,
        skills: ExpertSkillRegistry | None = None,
        repository: InMemoryAlphaAgentsRepository | None = None,
        positions: list[HoldingPosition] | None = None,
        contexts: list[StockContext] | None = None,
    ) -> None:
        self._data_provider = data_provider or MockBrokerDataProvider()
        self._skills = skills or ExpertSkillRegistry.default()
        self._repository = repository or InMemoryAlphaAgentsRepository()
        self._positions = positions
        self._contexts = contexts

    def run(self) -> list[HoldingAnalysisResult]:
        positions = (
            self._positions if self._positions is not None else self._data_provider.get_positions()
        )
        source_contexts = (
            self._contexts
            if self._contexts is not None
            else self._data_provider.get_stock_contexts([position.symbol for position in positions])
        )
        contexts = {context.symbol: context for context in source_contexts}
        results = [
            self._skills.evaluate_holding(position, contexts[position.symbol])
            for position in positions
            if position.symbol in contexts
        ]
        self._repository.save_holding_results(results)
        return results
