from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.middleware import register_request_context_middleware
from app.api.router import api_router, public_router
from app.core import configure_logging, get_settings


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(title="Sematrix API")
    app.state.settings = settings
    register_request_context_middleware(app)
    register_exception_handlers(app)
    app.include_router(public_router)
    app.include_router(api_router)
    return app


app = create_app()
