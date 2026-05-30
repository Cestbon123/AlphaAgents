from app.domain.enums import SelectionAction
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.workflows.selection import SelectionWorkflow


def test_selection_workflow_saves_and_returns_results():
    repository = InMemoryAlphaAgentsRepository()
    workflow = SelectionWorkflow(repository=repository)

    results = workflow.run()

    assert results
    assert any(result.action == SelectionAction.BUY for result in results)
    assert repository.list_selection_results() == results
