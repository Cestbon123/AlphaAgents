from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.domain.enums import DepositionStatus
from app.repositories.sqlite import SQLiteWorkflowRepository

router = APIRouter(prefix="/deposition", tags=["deposition"])


class DepositionCandidateUpdatePayload(BaseModel):
    title: str | None = None
    content: str | None = None
    status: DepositionStatus | None = None


def _repository() -> SQLiteWorkflowRepository:
    settings = get_settings()
    return SQLiteWorkflowRepository(settings.workflow_db)


@router.get("/candidates")
def list_deposition_candidates() -> dict[str, list[dict[str, object]]]:
    return {"candidates": _repository().list_deposition_candidates()}


@router.get("/knowledge-entries")
def list_confirmed_deposition_entries() -> dict[str, list[dict[str, object]]]:
    return {"entries": _repository().list_confirmed_deposition_entries()}


@router.patch("/candidates/{candidate_id}")
def update_deposition_candidate(
    candidate_id: str,
    payload: DepositionCandidateUpdatePayload,
) -> dict[str, dict[str, object]]:
    updates = payload.model_dump(exclude_unset=True, mode="json")
    candidate = _repository().update_deposition_candidate(candidate_id, updates)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Deposition candidate not found")
    return {"candidate": candidate}
