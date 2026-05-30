from fastapi import APIRouter

from app.core.config import get_settings
from app.local_data.data_sync import DataSyncService

router = APIRouter(prefix="/data-sync", tags=["data-sync"])


@router.get("/status")
def get_data_sync_status():
    settings = get_settings()
    return _service(settings).status()


@router.post("/run")
def run_data_sync():
    settings = get_settings()
    return _service(settings).sync_all()


def _service(settings) -> DataSyncService:
    return DataSyncService(
        data_db=settings.data_db,
        tdx_root=settings.tdx_root,
    )
