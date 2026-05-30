from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import SelectionAction
from app.domain.models import OperationRecord
from app.expert_skills.registry import ExpertSkillRegistry
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.strategies.basic import BasicSelectionStrategy
from app.workflows.deposition import DepositionWorkflow
from app.workflows.review import ReviewWorkflow
from app.workflows.selection import SelectionWorkflow


def test_daily_review_generates_cases_and_deposition_candidates():
    provider = MockBrokerDataProvider()
    repository = InMemoryAlphaAgentsRepository()
    SelectionWorkflow(
        strategy=BasicSelectionStrategy(provider),
        skills=ExpertSkillRegistry.default(),
        repository=repository,
    ).run()

    review = ReviewWorkflow(repository)
    deposition = DepositionWorkflow(repository)

    cases = review.run_daily_review()
    candidates = deposition.generate_from_review_cases(cases)

    assert cases
    assert any(case.worth_depositing for case in cases)
    assert candidates
    assert repository.list_deposition_candidates() == candidates


def test_daily_review_merges_user_operation_records():
    provider = MockBrokerDataProvider()
    repository = InMemoryAlphaAgentsRepository()
    results = SelectionWorkflow(
        strategy=BasicSelectionStrategy(provider),
        skills=ExpertSkillRegistry.default(),
        repository=repository,
    ).run()
    selected = next(result for result in results if result.action == SelectionAction.BUY)

    cases = ReviewWorkflow(repository).run_daily_review(
        operation_records=[
            OperationRecord(
                operation_date="2026-05-12",
                symbol=selected.stock.symbol,
                name=selected.stock.name,
                source="selection",
                system_conclusion=selected.action.value,
                user_action="未买入",
                reason="开盘波动偏大，等待确认",
                result_summary="符合知行趋势线选股",
            )
        ]
    )

    case = next(item for item in cases if item.symbol == selected.stock.symbol)
    assert case.user_action == "未买入"
    assert case.result_summary == "符合知行趋势线选股"
    assert case.key_reason == "开盘波动偏大，等待确认"
    assert case.deviation == "该买未买"
    assert case.worth_depositing is True
