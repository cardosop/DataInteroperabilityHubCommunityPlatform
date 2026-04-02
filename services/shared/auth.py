"""
Internal API key authentication for FastAPI microservices.

Every intra-service call from the Django api-service to these FastAPI
services MUST include the header:
    X-Internal-Api-Key: <INTERNAL_API_KEY env var value>

Uses hmac.compare_digest to prevent timing-based key enumeration attacks.
Raises ValueError at import/startup time if INTERNAL_API_KEY is not set,
so misconfiguration is caught at container start, not on first request.

Two enforcement mechanisms are provided:

1. InternalApiKeyMiddleware (preferred):
   BaseHTTPMiddleware that checks the header BEFORE FastAPI processes the
   request body.  This guarantees 401 is returned for bad/missing keys
   regardless of whether the request body is valid or malformed — avoiding
   the FastAPI ordering issue where 422 (body validation) would otherwise
   take priority over 401 (auth) when using route-level Depends.

   Usage:
       app.add_middleware(InternalApiKeyMiddleware)

   Public paths (/health, /metrics, /ready) are whitelisted automatically.

2. require_internal_key (Depends — kept for backward-compat):
   FastAPI dependency suitable for endpoints where the request body is
   always valid when the auth test runs (e.g. simple GET routes or
   endpoints where the test payload matches the route schema exactly).

   Usage:
       @app.post("/endpoint", dependencies=[Depends(require_internal_key)])
       async def endpoint(): ...
"""
import hmac
import json
import os

from fastapi import Header, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


def _load_key_at_startup() -> str:
    """
    Read INTERNAL_API_KEY from the environment at module import time.

    Raises ValueError immediately if the variable is absent or empty so
    the service process exits before accepting any connections rather than
    silently serving 500 errors on the first authenticated request.
    """
    key = os.environ.get("INTERNAL_API_KEY", "")
    if not key:
        raise ValueError(
            "INTERNAL_API_KEY environment variable is required but not set. "
            "Set it to a long random secret shared between the api-service "
            "and this FastAPI service (generate: openssl rand -hex 32)."
        )
    return key


# Validated and cached once at module import.
# If the env var is absent the process exits here — before uvicorn binds.
_INTERNAL_API_KEY: str = _load_key_at_startup()

# Paths that must remain publicly reachable (no auth required).
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/metrics", "/ready"})


class InternalApiKeyMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware that enforces X-Internal-Api-Key on every request
    except the whitelisted public paths (/health, /metrics, /ready).

    Running auth in middleware guarantees it executes BEFORE FastAPI
    parses the request body.  This means a request with a missing or
    wrong API key always gets 401 — even when the body would fail
    schema validation — eliminating the 422-before-401 ordering problem
    that occurs with route-level Depends.

    Args:
        app: The ASGI application.
        extra_public_paths: Additional paths to allow without authentication
            (e.g. ``{"/.well-known/void", "/ontology/hub"}`` for semantic
            service endpoints that must be publicly reachable).  Combined
            with the built-in ``_PUBLIC_PATHS`` whitelist at construction
            time; defaults to an empty frozenset.
    """

    def __init__(self, app, extra_public_paths: frozenset = frozenset()):
        super().__init__(app)
        self._public_paths = _PUBLIC_PATHS | frozenset(extra_public_paths)

    async def dispatch(
        self, request: StarletteRequest, call_next
    ) -> StarletteResponse:
        if request.url.path in self._public_paths:
            return await call_next(request)

        key = request.headers.get("X-Internal-Api-Key")

        if not key:
            return StarletteResponse(
                content=json.dumps(
                    {"detail": "X-Internal-Api-Key header is required"}
                ),
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if not hmac.compare_digest(
            key.encode("utf-8"),
            _INTERNAL_API_KEY.encode("utf-8"),
        ):
            return StarletteResponse(
                content=json.dumps({"detail": "Invalid API key"}),
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        return await call_next(request)


async def require_internal_key(
    x_internal_api_key: str | None = Header(
        default=None, alias="X-Internal-Api-Key"
    ),
) -> None:
    """
    FastAPI dependency that enforces internal API key authentication.

    Uses the key cached at startup — no per-request env reads.

    NOTE: Prefer InternalApiKeyMiddleware for services with POST endpoints
    that have required request bodies.  With route-level Depends, FastAPI
    validates the request body before calling this dependency, so a missing
    body returns 422 before auth can return 401.

    Usage:
        @app.post("/endpoint", dependencies=[Depends(require_internal_key)])
        async def endpoint(): ...
    """
    if x_internal_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Internal-Api-Key header is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # hmac.compare_digest prevents timing-based key enumeration
    if not hmac.compare_digest(
        x_internal_api_key.encode("utf-8"),
        _INTERNAL_API_KEY.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
