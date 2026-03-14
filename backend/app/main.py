from fastapi import FastAPI

from app.api.router import api_router, public_router


def create_app() -> FastAPI:
    app = FastAPI(title="Sematrix API")
    app.include_router(public_router)
    app.include_router(api_router)
    return app


app = create_app()
