"""非同期 SQLAlchemy エンジン + セッションファクトリ。

テスト時は init_models(database_url=...) を呼んで初期化し、終了時に
reset_engine_cache() を呼んでキャッシュをクリアする。
本番では Alembic でマイグレーションを走らせる前提。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from norn.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _init_engine_if_needed(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    global _engine, _sessionmaker
    if _sessionmaker is None:
        url = database_url or get_settings().database_url
        _engine = create_async_engine(
            url,
            future=True,
            echo=False,
            pool_pre_ping=True,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _sessionmaker


def reset_engine_cache() -> None:
    """テストで database_url を差し替える前後に呼ぶ。"""

    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends 用の AsyncSession ジェネレータ。"""

    sm = _init_engine_if_needed()
    async with sm() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """FastAPI のリクエストスコープ外（BackgroundTasks など）で使うセッション。

    コミット/ロールバックは呼び出し側が制御する。
    """

    sm = _init_engine_if_needed()
    async with sm() as session:
        yield session


async def init_models(database_url: str | None = None) -> None:
    """開発・テスト用に create_all() でテーブルを作る。本番では Alembic を使う。"""

    from norn.db.models import Base  # 遅延 import で循環回避

    _init_engine_if_needed(database_url)
    assert _engine is not None
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
