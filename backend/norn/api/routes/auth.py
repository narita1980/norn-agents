from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from norn.auth.session import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    decode_session_token,
    set_session_cookie,
)
from norn.config import Settings, get_settings
from norn.db import get_session
from norn.db.users import authenticate_user

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class SessionResponse(BaseModel):
    authenticated: bool


def _extract_token(request: Request) -> str | None:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie:
        return cookie

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip() or None
    return None


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    user = await authenticate_user(db, username=body.username, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )
    set_session_cookie(response, settings, subject=user.username)
    return {"ok": True}


@router.post("/logout")
async def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    clear_session_cookie(response, settings)
    return {"ok": True}


@router.get("/session", response_model=SessionResponse)
async def session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    payload = decode_session_token(settings, token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    return SessionResponse(authenticated=True)
