"""ユーザーテーブル操作（ログイン認証）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from norn.agents.user_levels import TEST_LOGIN_USERS, UserLevel
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


async def get_user_by_level(session: AsyncSession, user_level: UserLevel) -> User | None:
    stmt = select(User).where(User.user_level == user_level)
    return await session.scalar(stmt)


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    user_level: UserLevel | None = None,
) -> User:
    normalized = username.strip()
    if not normalized:
        msg = "username must not be empty"
        raise ValueError(msg)
    existing = await get_user_by_username(session, normalized)
    if existing is not None:
        msg = f"user already exists: {normalized}"
        raise ValueError(msg)
    if user_level is not None:
        level_owner = await get_user_by_level(session, user_level)
        if level_owner is not None:
            msg = f"user_level already assigned: {user_level}"
            raise ValueError(msg)
    user = User(
        username=normalized,
        password_hash=hash_password(password),
        user_level=user_level,
    )
    session.add(user)
    await session.flush()
    return user


async def seed_test_users(session: AsyncSession, *, password: str) -> list[str]:
    """テスト用ログインユーザを冪等に作成。既存ユーザの user_level / パスワードも同期。"""
    lines: list[str] = []
    for level, username in TEST_LOGIN_USERS.items():
        existing = await get_user_by_username(session, username)
        if existing is not None:
            changed = False
            if existing.user_level != level:
                existing.user_level = level
                changed = True
            if not verify_password(password, existing.password_hash):
                existing.password_hash = hash_password(password)
                changed = True
            if changed:
                lines.append(f"updated: {username} ({level})")
            else:
                lines.append(f"skipped (exists): {username} ({level})")
            continue
        level_owner = await get_user_by_level(session, level)
        if level_owner is not None:
            lines.append(f"skipped (level taken): {level} -> {level_owner.username}")
            continue
        await create_user(session, username=username, password=password, user_level=level)
        lines.append(f"created: {username} ({level})")
    return lines


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
