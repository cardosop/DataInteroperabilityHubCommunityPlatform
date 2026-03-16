"""
Internal API key authentication for FastAPI microservices.

Every intra-service call from the Django api-service to these FastAPI
services MUST include the header:
    X-Internal-Api-Key: <INTERNAL_API_KEY env var value>

Uses hmac.compare_digest to prevent timing-based key enumeration attacks.
Raises ValueError at import/startup time if INTERNAL_API_KEY is not set,
so misconfiguration is caught at container start, not on first request.
"""
import hmac
import os
from fastapi import Header, HTTPException, status


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


async def require_internal_key(
    x_internal_api_key: str | None = Header(
        default=None, alias="X-Internal-Api-Key"
    ),
) -> None:
    """
    FastAPI dependency that enforces internal API key authentication.

    Uses the key cached at startup — no per-request env reads.

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
