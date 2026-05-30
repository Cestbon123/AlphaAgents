from app.domain.models import (
    DepositionCandidate,
    HoldingAnalysisResult,
    SelectionResult,
    WorkflowRun,
)


class InMemoryAlphaAgentsRepository:
    def __init__(self) -> None:
        self._runs: list[WorkflowRun] = []
        self._selection_results: list[SelectionResult] = []
        self._holding_results: list[HoldingAnalysisResult] = []
        self._deposition_candidates: list[DepositionCandidate] = []

    def save_run(self, run: WorkflowRun) -> None:
        self._runs.append(run)

    def list_runs(self) -> list[WorkflowRun]:
        return list(self._runs)

    def save_selection_results(self, results: list[SelectionResult]) -> None:
        self._selection_results = list(results)

    def list_selection_results(self) -> list[SelectionResult]:
        return list(self._selection_results)

    def save_holding_results(self, results: list[HoldingAnalysisResult]) -> None:
        self._holding_results = list(results)

    def list_holding_results(self) -> list[HoldingAnalysisResult]:
        return list(self._holding_results)

    def save_deposition_candidates(self, candidates: list[DepositionCandidate]) -> None:
        self._deposition_candidates.extend(candidates)

    def list_deposition_candidates(self) -> list[DepositionCandidate]:
        return list(self._deposition_candidates)
