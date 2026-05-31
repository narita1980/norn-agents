import base64
import binascii
import secrets
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_BASIC_AUTH_REALM = 'Basic realm="Norn"'


def _is_public_path(path: str) -> bool:
    return path in ("/healthz", "/readyz") or path.startswith("/webhook")


def _unauthorized_response() -> Response:
    return Response(status_code=401, headers={"WWW-Authenticate": _BASIC_AUTH_REALM})


class BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        username: str,
        password: str,
        enabled: bool,
    ) -> None:
        super().__init__(app)
        self.username = username
        self.password = password
        self.enabled = enabled

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self.enabled or _is_public_path(request.url.path):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return _unauthorized_response()

        try:
            decoded = base64.b64decode(auth_header[6:], validate=True).decode("utf-8")
            user, sep, pwd = decoded.partition(":")
            if not sep:
                return _unauthorized_response()
        except (binascii.Error, UnicodeDecodeError):
            return _unauthorized_response()

        if not (
            secrets.compare_digest(user, self.username)
            and secrets.compare_digest(pwd, self.password)
        ):
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
