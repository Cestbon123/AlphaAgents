from app.adapters.broker import MockBrokerDataProvider
from app.domain.models import SelectionResult, StockContext
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.strategies.basic import BasicSelectionStrategy


class SelectionStrategy:
    def select_candidates(self) -> list[StockContext]:
        raise NotImplementedError


class SelectionWorkflow:
    def __init__(
        self,
        strategy: SelectionStrategy | None = None,
        skills: ExpertSkillRegistry | None = None,
        repository: InMemoryAlphaAgentsRepository | None = None,
    ) -> None:
        self._strategy = strategy or BasicSelectionStrategy(MockBrokerDataProvider())
        self._skills = skills or ExpertSkillRegistry.default()
        self._repository = repository or InMemoryAlphaAgentsRepository()

    def run(self) -> list[SelectionResult]:
        candidates = self._strategy.select_candidates()
        results = [self._skills.evaluate_selection(candidate) for candidate in candidates]
        self._repository.save_selection_results(results)
        return results
