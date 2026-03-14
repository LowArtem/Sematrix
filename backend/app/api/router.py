from fastapi import APIRouter

from app.api.routes.folders import api_folders_router
from app.api.routes.system import api_system_router, public_system_router


public_router = APIRouter()
public_router.include_router(public_system_router)

api_router = APIRouter(prefix="/api")
api_router.include_router(api_folders_router)
api_router.include_router(api_system_router)
