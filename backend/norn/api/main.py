from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from norn.api.middleware import (
    PayloadSizeLimitMiddleware,
    RequestIDMiddleware,
    SessionAuthMiddleware,
)
from norn.api.routes import auth, chat, dashboard, github, health, reviews
from norn.brand import PRODUCT_NAME
from norn.config import Settings, get_settings
from norn.db import init_models
from norn.logging import configure_logging

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # SQLite では Alembic を走らせていない開発環境でも動くよう create_all を呼ぶ。
        # Postgres を本番運用するときは `alembic upgrade head` を必須にする。
        if settings.database_url.startswith("sqlite"):
            await init_models(database_url=settings.database_url)
        yield

    app = FastAPI(title=PRODUCT_NAME, version="0.1.0", lifespan=lifespan)

    app.add_middleware(PayloadSizeLimitMiddleware, limit=settings.payload_size_limit_bytes)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SessionAuthMiddleware, settings=settings)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth")
    app.include_router(github.router, prefix="/webhook")
    app.include_router(chat.router, prefix="/chat")
    app.include_router(reviews.router, prefix="/reviews")
    app.include_router(dashboard.router, prefix="/dashboard")

    if settings is not get_settings():
        app.dependency_overrides[get_settings] = lambda: settings

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


app = create_app()
