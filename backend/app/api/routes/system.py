from fastapi import APIRouter, Depends

from app.api.dependencies import get_system_status_service
from app.domain.system import SystemStatusService


public_system_router = APIRouter()
api_system_router = APIRouter(tags=["system"])


@public_system_router.get("/")
def read_root(
    service: SystemStatusService = Depends(get_system_status_service),
) -> dict[str, str]:
    return service.read_root_payload()


@api_system_router.get("/health")
def read_health(
    service: SystemStatusService = Depends(get_system_status_service),
) -> dict[str, str]:
    return service.read_health_payload()
