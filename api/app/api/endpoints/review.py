from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.repositories.sqlite import SQLiteWorkflowRepository

router = APIRouter(prefix="/review", tags=["review"])


class OperationRecordPayload(BaseModel):
    symbol: str = Field(min_length=1)
    name: str = ""
    source: str = "manual"
    system_conclusion: str = ""
    user_action: str = Field(min_length=1)
    reason: str = ""
    result_summary: str = ""


class OperationRecordsPayload(BaseModel):
    operation_date: date
    operations: list[OperationRecordPayload] = Field(default_factory=list)


def _repository() -> SQLiteWorkflowRepository:
    settings = get_settings()
    return SQLiteWorkflowRepository(settings.workflow_db)


@router.get("/operations")
def list_operation_records(
    operation_date: date | None = None,
) -> dict[str, list[dict[str, object]]]:
    return {"operations": _repository().list_operation_records(operation_date)}


@router.get("/cases")
def list_review_cases(review_date: date | None = None) -> dict[str, list[dict[str, object]]]:
    return {"cases": _repository().list_review_cases(review_date)}


@router.get("/cases/latest")
def list_latest_review_cases() -> dict[str, list[dict[str, object]]]:
    return {"cases": _repository().get_latest_review_cases()}


@router.put("/operations")
def replace_operation_records(
    payload: OperationRecordsPayload,
) -> dict[str, list[dict[str, object]]]:
    operations = [operation.model_dump() for operation in payload.operations]
    return {
        "operations": _repository().save_operation_records(
            payload.operation_date,
            operations,
        )
    }
