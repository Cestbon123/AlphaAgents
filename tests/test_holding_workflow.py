from app.domain.enums import HoldingAction
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.workflows.holding import HoldingWorkflow


def test_holding_workflow_saves_and_returns_next_day_actions():
    repository = InMemoryAlphaAgentsRepository()
    workflow = HoldingWorkflow(repository=repository)

    results = workflow.run()

    assert results
    assert all(
        result.action
        in {
            HoldingAction.HOLD,
            HoldingAction.LET_RUN,
            HoldingAction.STOP_LOSS,
            HoldingAction.CLEAR,
        }
        for result in results
    )
    assert all(result.next_day_reminder for result in results)
    assert repository.list_holding_results() == results
