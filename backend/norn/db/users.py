"""ユーザーテーブル操作（ログイン認証）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from norn.auth.passwords import hash_password, verify_password
from norn.db.models import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def count_users(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count()).select_from(User))
    return int(result or 0)


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return await session.scalar(stmt)


async def create_user(session: AsyncSession, *, username: str, password: str) -> User:
    normalized = username.strip()
    if not normalized:
        msg = "username must not be empty"
        raise ValueError(msg)
    existing = await get_user_by_username(session, normalized)
    if existing is not None:
        msg = f"user already exists: {normalized}"
        raise ValueError(msg)
    user = User(username=normalized, password_hash=hash_password(password))
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
) -> User | None:
    user = await get_user_by_username(session, username.strip())
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
