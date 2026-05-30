from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.workflows.service import AlphaAgentsWorkflowService
from app.workflows.stock_workspace import StockWorkspaceService

router = APIRouter(prefix="/stocks", tags=["stocks"])


class StockOperationPayload(BaseModel):
    operation_date: date | None = None
    name: str = ""
    source: str = "manual"
    system_conclusion: str = ""
    user_action: str = Field(..., min_length=1)
    reason: str = ""
    result_summary: str = ""


class StockReviewPayload(BaseModel):
    review_date: date | None = None
    name: str = ""
    scenario: str = "个股复盘"
    system_conclusion: str = ""
    user_action: str = Field(..., min_length=1)
    result_summary: str = ""
    deviation: str = "用户主动复盘"
    review_conclusion: str = Field(..., min_length=1)
    key_reason: str = Field(..., min_length=1)
    worth_depositing: bool = False


class StockDepositionPayload(BaseModel):
    kind: str = "模式识别"
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    source: str = "个股复盘"
    status: str = "待确认"
    review_case_id: str | None = None


class StockTrackingPayload(BaseModel):
    status: Literal["重点跟踪", "观察", "暂不跟踪", "放弃"]
    note: str = ""


def get_stock_workspace_service(request: Request) -> StockWorkspaceService:
    if not hasattr(request.app.state, "stock_workspace_service"):
        request.app.state.stock_workspace_service = StockWorkspaceService()
    return request.app.state.stock_workspace_service


def get_workflow_service(request: Request) -> AlphaAgentsWorkflowService:
    if not hasattr(request.app.state, "workflow_service"):
        request.app.state.workflow_service = AlphaAgentsWorkflowService()
    return request.app.state.workflow_service


StockWorkspaceDependency = Annotated[
    StockWorkspaceService, Depends(get_stock_workspace_service)
]
WorkflowService = Annotated[AlphaAgentsWorkflowService, Depends(get_workflow_service)]


@router.get("/{symbol}/workspace")
def read_stock_workspace(
    symbol: str,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    return {"workspace": service.get_workspace(symbol)}


@router.get("/cases/list")
def list_stock_cases(
    service: StockWorkspaceDependency,
    symbol: str | None = None,
    query: str = "",
    kind: str = "",
    status: str = "",
) -> dict[str, object]:
    return {
        "cases": service.workflow_repository.list_stock_cases(
            symbol=symbol,
            query=query,
            kind=kind,
            status=status,
        )
    }


@router.post("/{symbol}/research/run")
def run_stock_research(
    symbol: str,
    workspace_service: StockWorkspaceDependency,
    workflow_service: WorkflowService,
) -> dict[str, object]:
    report_payload = workflow_service.run_research_report(symbol)
    return {
        **report_payload,
        "workspace": workspace_service.get_workspace(symbol),
    }


@router.post("/{symbol}/operations")
def append_stock_operation(
    symbol: str,
    payload: StockOperationPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    operation = service.append_operation(symbol, payload.model_dump(mode="json"))
    return {
        "operation": operation,
        "workspace": service.get_workspace(symbol),
    }


@router.post("/{symbol}/reviews")
def append_stock_review(
    symbol: str,
    payload: StockReviewPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    review_case = service.append_review(symbol, payload.model_dump(mode="json"))
    return {
        "review_case": review_case,
        "workspace": service.get_workspace(symbol),
    }


@router.post("/{symbol}/depositions")
def append_stock_deposition(
    symbol: str,
    payload: StockDepositionPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    candidate = service.append_deposition(symbol, payload.model_dump(mode="json"))
    return {
        "deposition_candidate": candidate,
        "workspace": service.get_workspace(symbol),
    }


@router.patch("/{symbol}/tracking")
def update_stock_tracking(
    symbol: str,
    payload: StockTrackingPayload,
    service: StockWorkspaceDependency,
) -> dict[str, object]:
    tracking = service.update_tracking(symbol, payload.status, payload.note)
    return {
        "tracking_state": tracking,
        "workspace": service.get_workspace(symbol),
    }
