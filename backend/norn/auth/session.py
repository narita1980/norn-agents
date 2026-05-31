from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Response

from norn.config import Settings

SESSION_COOKIE_NAME = "norn_session"
JWT_ALGORITHM = "HS256"


def _token_ttl(settings: Settings) -> timedelta:
    return timedelta(hours=settings.norn_auth_token_ttl_hours)


def create_session_token(settings: Settings, *, subject: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + _token_ttl(settings),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm=JWT_ALGORITHM)


def decode_session_token(settings: Settings, token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


def session_cookie_params(settings: Settings) -> dict[str, str | int | bool]:
    max_age = int(_token_ttl(settings).total_seconds())
    cross_origin = bool(settings.cors_origins)
    params: dict[str, str | int | bool] = {
        "key": SESSION_COOKIE_NAME,
        "httponly": True,
        "path": "/",
        "max_age": max_age,
        "samesite": "none" if cross_origin else "lax",
    }
    if cross_origin:
        params["secure"] = True
    return params


def set_session_cookie(response: Response, settings: Settings, *, subject: str) -> None:
    token = create_session_token(settings, subject=subject)
    response.set_cookie(value=token, **session_cookie_params(settings))


def clear_session_cookie(response: Response, settings: Settings) -> None:
    params = session_cookie_params(settings)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path=str(params.get("path", "/")),
        httponly=bool(params.get("httponly", True)),
        samesite=str(params.get("samesite", "lax")),
        secure=bool(params.get("secure", False)),
    )
