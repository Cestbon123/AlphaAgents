from uuid import uuid4

from app.domain.models import DepositionCandidate, ReviewCase
from app.repositories.memory import InMemoryAlphaAgentsRepository


class DepositionWorkflow:
    def __init__(self, repository: InMemoryAlphaAgentsRepository) -> None:
        self._repository = repository

    def generate_from_review_cases(
        self, cases: list[ReviewCase]
    ) -> list[DepositionCandidate]:
        candidates = [
            DepositionCandidate(
                id=str(uuid4()),
                kind="知识库候选",
                title=f"{case.name}：{case.review_conclusion}",
                content=f"{case.key_reason}。适用场景：{case.scenario}。",
                source=f"{case.symbol} {case.name}",
            )
            for case in cases
            if case.worth_depositing
        ]
        self._repository.save_deposition_candidates(candidates)
        return candidates
