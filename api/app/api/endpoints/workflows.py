from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.workflows.service import AlphaAgentsWorkflowService

router = APIRouter(tags=["workflows"])


def get_workflow_service(request: Request) -> AlphaAgentsWorkflowService:
    if not hasattr(request.app.state, "workflow_service"):
        request.app.state.workflow_service = AlphaAgentsWorkflowService()
    return request.app.state.workflow_service


WorkflowService = Annotated[
    AlphaAgentsWorkflowService, Depends(get_workflow_service)
]


@router.post("/workflows/selection/run")
def run_selection(service: WorkflowService) -> dict[str, object]:
    return service.run_selection()


@router.get("/workflows/selection/runs/latest")
def read_latest_selection_run(service: WorkflowService) -> dict[str, object]:
    return service.get_latest_selection_run()


@router.post("/workflows/holding/run")
def run_holding(service: WorkflowService) -> dict[str, object]:
    return service.run_holding()


@router.post("/workflows/daily-review/run")
def run_daily_review(service: WorkflowService) -> dict[str, object]:
    return service.run_daily_review()


@router.post("/workflows/weekly-review/run")
def run_weekly_review(service: WorkflowService) -> dict[str, object]:
    return service.run_weekly_review()


@router.get("/dashboard")
def read_dashboard(service: WorkflowService) -> dict[str, object]:
    return service.dashboard()
