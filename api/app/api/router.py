from fastapi import APIRouter

from app.agent.chat_endpoint import router as agent_router
from app.api.endpoints.data_sync import router as data_sync_router
from app.api.endpoints.deposition import router as deposition_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.market import router as market_router
from app.api.endpoints.portfolio import router as portfolio_router
from app.api.endpoints.reports import router as reports_router
from app.api.endpoints.review import router as review_router
from app.api.endpoints.stocks import router as stocks_router
from app.api.endpoints.strategies import router as strategies_router
from app.api.endpoints.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(data_sync_router)
api_router.include_router(deposition_router)
api_router.include_router(market_router)
api_router.include_router(portfolio_router)
api_router.include_router(review_router)
api_router.include_router(reports_router)
api_router.include_router(stocks_router)
api_router.include_router(strategies_router)
api_router.include_router(workflows_router)
api_router.include_router(agent_router)
