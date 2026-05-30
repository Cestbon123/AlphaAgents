from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.repositories.sqlite import SQLiteWorkflowRepository
from app.workflows.service import AlphaAgentsWorkflowService

router = APIRouter(prefix="/reports", tags=["reports"])


class DailyReportRunPayload(BaseModel):
    report_date: date | None = None


class ResearchReportRunPayload(BaseModel):
    symbol: str


def get_workflow_service(request: Request) -> AlphaAgentsWorkflowService:
    if not hasattr(request.app.state, "workflow_service"):
        request.app.state.workflow_service = AlphaAgentsWorkflowService()
    return request.app.state.workflow_service


WorkflowService = Annotated[
    AlphaAgentsWorkflowService, Depends(get_workflow_service)
]


@router.post("/daily/run")
def run_daily_report(
    service: WorkflowService,
    payload: DailyReportRunPayload | None = None,
) -> dict[str, object]:
    report_date = payload.report_date if payload else None
    return service.run_daily_report(report_date)


@router.get("/daily/latest")
def read_latest_daily_report(service: WorkflowService) -> dict[str, object | None]:
    return service.get_latest_daily_report()


@router.post("/research/run")
def run_research_report(
    service: WorkflowService,
    payload: ResearchReportRunPayload,
) -> dict[str, object]:
    return service.run_research_report(payload.symbol)


@router.get("/research/latest")
def read_latest_research_report(
    service: WorkflowService,
    symbol: str | None = None,
) -> dict[str, object | None]:
    return service.get_latest_research_report(symbol)


@router.get("/research")
def list_research_reports(
    symbol: str | None = None,
    limit: int = 50,
) -> dict[str, object]:
    settings = get_settings()
    repository = SQLiteWorkflowRepository(settings.workflow_db)
    return {"reports": repository.list_research_reports(symbol=symbol, limit=limit)}
