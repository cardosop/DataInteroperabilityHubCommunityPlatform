"""
Shared services test fixtures (Phase 79).

IMPORTANT: INTERNAL_API_KEY must be set BEFORE importing
shared.auth because _load_key_at_startup() runs at
module import time and raises ValueError if the env var is absent.
"""

import os

# ── Bootstrap env BEFORE any shared imports ─────────────────────
_TEST_KEY = "test-shared-services-key-phase79"
os.environ["INTERNAL_API_KEY"] = _TEST_KEY

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from shared.auth import InternalApiKeyMiddleware
from shared.middleware import (
    RequestSizeLimitMiddleware,
)


@pytest.fixture(scope="session")
def valid_api_key() -> str:
    """The test API key injected into the environment."""
    return _TEST_KEY


@pytest.fixture(scope="session")
def auth_headers(valid_api_key: str) -> dict:
    """Headers dict with the valid X-Internal-Api-Key."""
    return {"X-Internal-Api-Key": valid_api_key}


def _build_app(
    max_bytes: int = 50 * 1024 * 1024,
    extra_public_paths: frozenset = frozenset(),
) -> FastAPI:
    """Build a minimal FastAPI app wired with both middlewares."""
    app = FastAPI()

    # Order matters: size limit runs first (outermost), auth second
    app.add_middleware(
        InternalApiKeyMiddleware,
        extra_public_paths=extra_public_paths,
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=max_bytes,
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected_get():
        return {"result": "secret"}

    @app.post("/protected")
    async def protected_post(payload: dict):
        return {"received": payload}

    @app.post("/echo")
    async def echo(payload: dict):
        return payload

    return app


@pytest.fixture(scope="session")
def test_app() -> FastAPI:
    """FastAPI app with auth + size-limit middlewares."""
    return _build_app()


@pytest.fixture()
async def client(test_app: FastAPI):
    """Async httpx test client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
