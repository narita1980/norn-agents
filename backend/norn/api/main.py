from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from norn.api.middleware import PayloadSizeLimitMiddleware, RequestIDMiddleware
from norn.api.routes import chat, github, health
from norn.config import Settings, get_settings
from norn.logging import configure_logging

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Norn", version="0.1.0")

    app.add_middleware(PayloadSizeLimitMiddleware, limit=settings.payload_size_limit_bytes)
    app.add_middleware(RequestIDMiddleware)

    app.include_router(health.router)
    app.include_router(github.router, prefix="/webhook")
    app.include_router(chat.router, prefix="/chat")

    if settings is not get_settings():
        app.dependency_overrides[get_settings] = lambda: settings

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


app = create_app()
