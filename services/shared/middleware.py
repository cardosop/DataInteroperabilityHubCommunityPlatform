"""
Shared FastAPI middleware for all internal microservices.
"""

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects requests whose body exceeds max_bytes before processing them.

    Two enforcement paths:

    1. Fast path — Content-Length present: reject immediately without
       reading the body if the declared size exceeds the limit.

    2. Stream path — Content-Length absent (chunked transfer-encoding):
       read the body in chunks up to max_bytes + 1.  If we accumulate
       more than max_bytes the request is rejected with 413 before the
       full body has been read.  The already-read bytes are re-injected
       so the downstream handler sees a complete body for normal requests.

    Default limit: 50 MiB. Configurable via constructor argument.
    """

    def __init__(self, app, max_bytes: int = 50 * 1024 * 1024) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes
        self._limit_mib = max_bytes // (1024 * 1024)

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")

        if content_length is not None:
            # Fast path: trust the declared size.
            try:
                if int(content_length) > self.max_bytes:
                    return Response(
                        content=(
                            f'{{"detail": "Request body exceeds {self._limit_mib} MiB limit"}}'
                        ),
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        media_type="application/json",
                    )
            except ValueError:
                pass  # malformed Content-Length — let the framework handle
            return await call_next(request)

        # Stream path: no Content-Length (chunked or unknown body size).
        # Read up to max_bytes + 1 to detect oversized payloads without
        # buffering the entire body first.
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > self.max_bytes:
                return Response(
                    content=(f'{{"detail": "Request body exceeds {self._limit_mib} MiB limit"}}'),
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    media_type="application/json",
                )
            chunks.append(chunk)

        # Re-inject the buffered body so downstream handlers can read it.
        body = b"".join(chunks)

        async def _receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = _receive
        return await call_next(request)
