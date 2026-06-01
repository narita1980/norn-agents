from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from norn.auth.session import SESSION_COOKIE_NAME, decode_session_token
from norn.config import Settings, get_settings

_AUTH_REQUIRED_PREFIXES = ("/chat", "/reviews", "/dashboard", "/growth")


def _requires_auth(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _AUTH_REQUIRED_PREFIXES)


def _unauthorized_response() -> Response:
    return JSONResponse(status_code=401, content={"detail": "not authenticated"})


def _extract_bearer_token(auth_header: str) -> str | None:
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    return token or None


class SessionAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(app)
        self._settings = settings

    def _settings_for_request(self) -> Settings:
        return self._settings or get_settings()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = self._settings_for_request()
        if not _requires_auth(request.url.path):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                token = _extract_bearer_token(auth_header)

        if not token or decode_session_token(settings, token) is None:
            return _unauthorized_response()

        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    HEADER = "X-Request-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(self.HEADER) or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[self.HEADER] = request_id
        return response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limit: int) -> None:
        super().__init__(app)
        self.limit = limit

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.limit:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "payload too large"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "invalid content-length"},
                )
        return await call_next(request)
