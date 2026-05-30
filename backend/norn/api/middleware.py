from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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
