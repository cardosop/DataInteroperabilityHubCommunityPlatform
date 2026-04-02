"""
Phase 79.4 — RequestSizeLimitMiddleware tests.

Tests run against a real FastAPI app with real middleware (no mocks).
"""
import pytest
from httpx import ASGITransport, AsyncClient

from shared.tests.conftest import _build_app


# Use a tiny limit (100 bytes) so tests are fast and deterministic.
_TINY_LIMIT = 100


@pytest.fixture()
async def tiny_client(auth_headers):
    """Client with a 100-byte size limit."""
    app = _build_app(max_bytes=_TINY_LIMIT)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        yield ac, auth_headers


# ── Small request passes ────────────────────────────────────────


async def test_small_body_passes(tiny_client):
    """Body under the limit is accepted."""
    ac, hdrs = tiny_client
    r = await ac.post(
        "/echo", json={"x": 1}, headers=hdrs,
    )
    assert r.status_code == 200


# ── Large request rejected via Content-Length ───────────────────


async def test_large_body_rejected_content_length(tiny_client):
    """Body over the limit with Content-Length returns 413."""
    ac, hdrs = tiny_client
    big = b"x" * (_TINY_LIMIT + 1)
    r = await ac.post(
        "/echo",
        content=big,
        headers={**hdrs, "Content-Type": "application/json"},
    )
    assert r.status_code == 413
    assert "limit" in r.text.lower()


# ── Exact limit passes ──────────────────────────────────────────


async def test_exact_limit_passes(auth_headers):
    """Body exactly at the limit should pass (not rejected as 413)."""
    limit = 50
    app = _build_app(max_bytes=limit)

    @app.post("/raw")
    async def raw():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        body = b"x" * limit
        r = await ac.post(
            "/raw",
            content=body,
            headers={
                **auth_headers,
                "Content-Type": "application/octet-stream",
                "Content-Length": str(limit),
            },
        )
        # 50 bytes == limit → must pass the size middleware
        assert r.status_code == 200


# ── One-over rejected ───────────────────────────────────────────


async def test_one_over_rejected(auth_headers):
    """Body one byte over the limit is rejected."""
    limit = 50
    app = _build_app(max_bytes=limit)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        body = b"x" * (limit + 1)
        r = await ac.post(
            "/echo",
            content=body,
            headers={
                **auth_headers,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 413


# ── Custom max_bytes ────────────────────────────────────────────


async def test_custom_max_bytes(auth_headers):
    """Custom max_bytes (200) allows a 150-byte body but
    rejects a 250-byte body."""
    app = _build_app(max_bytes=200)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        r_ok = await ac.post(
            "/echo",
            content=b'{"data":"' + b"a" * 130 + b'"}',
            headers={
                **auth_headers,
                "Content-Type": "application/json",
            },
        )
        assert r_ok.status_code == 200

        r_big = await ac.post(
            "/echo",
            content=b"x" * 250,
            headers={
                **auth_headers,
                "Content-Type": "application/json",
            },
        )
        assert r_big.status_code == 413


# ── Malformed Content-Length ────────────────────────────────────


async def test_malformed_content_length_does_not_crash(tiny_client):
    """Malformed Content-Length (non-integer) must not crash the
    middleware — it catches ValueError and delegates to the framework."""
    ac, hdrs = tiny_client
    r = await ac.post(
        "/echo",
        content=b'{"ok": true}',
        headers={
            **hdrs,
            "Content-Type": "application/json",
            "Content-Length": "not-a-number",
        },
    )
    # Middleware must not return 500 — it should let the framework handle
    assert r.status_code != 500


# ── GET requests don't check body ──────────────────────────────


async def test_get_no_body_check(tiny_client):
    """GET /protected succeeds regardless of limit — no body."""
    ac, hdrs = tiny_client
    r = await ac.get("/protected", headers=hdrs)
    assert r.status_code == 200


# ── Default limit ───────────────────────────────────────────────


def test_default_limit_is_50_mib():
    """The default max_bytes is 50 MiB."""
    from shared.middleware import (
        RequestSizeLimitMiddleware,
    )
    from fastapi import FastAPI

    app = FastAPI()
    mw = RequestSizeLimitMiddleware(app)
    assert mw.max_bytes == 50 * 1024 * 1024


# ── Stream path (chunked / no Content-Length) ───────────────────


async def test_stream_path_small_body_passes(auth_headers):
    """Body under the limit WITHOUT Content-Length header passes
    (exercises the stream/chunked code path)."""
    limit = 200
    app = _build_app(max_bytes=limit)

    @app.post("/stream-echo")
    async def stream_echo(payload: dict):
        return payload

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        small_json = b'{"msg": "hello"}'
        r = await ac.post(
            "/stream-echo",
            content=small_json,
            headers={
                **auth_headers,
                "Content-Type": "application/json",
                "Transfer-Encoding": "chunked",
            },
        )
        # The stream path must re-inject the body so the handler sees it
        assert r.status_code == 200
        assert r.json()["msg"] == "hello"


async def test_stream_path_oversized_rejected(auth_headers):
    """Body over the limit WITHOUT Content-Length header is rejected
    (exercises the stream/chunked code path)."""
    limit = 50
    app = _build_app(max_bytes=limit)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        big = b"x" * (limit + 10)
        r = await ac.post(
            "/echo",
            content=big,
            headers={
                **auth_headers,
                "Content-Type": "application/json",
                "Transfer-Encoding": "chunked",
            },
        )
        assert r.status_code == 413
        assert "limit" in r.text.lower()
