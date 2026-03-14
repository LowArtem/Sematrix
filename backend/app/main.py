from fastapi import FastAPI

from app.api.router import api_router, public_router
from app.core import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Sematrix API")
    app.state.settings = settings
    app.include_router(public_router)
    app.include_router(api_router)
    return app


app = create_app()
