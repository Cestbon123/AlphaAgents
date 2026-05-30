from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.repositories.sqlite import SQLiteWorkflowRepository

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioPositionPayload(BaseModel):
    symbol: str = Field(min_length=1)
    quantity: int
    cost_price: float
    holding_days: int


class PortfolioPositionsPayload(BaseModel):
    positions: list[PortfolioPositionPayload] = Field(default_factory=list)


def _repository() -> SQLiteWorkflowRepository:
    settings = get_settings()
    return SQLiteWorkflowRepository(settings.workflow_db)


@router.get("/positions")
def list_positions() -> dict[str, list[dict[str, object]]]:
    return {"positions": _repository().list_positions()}


@router.put("/positions")
def replace_positions(payload: PortfolioPositionsPayload) -> dict[str, list[dict[str, object]]]:
    positions = [position.model_dump() for position in payload.positions]
    return {"positions": _repository().save_positions(positions)}
