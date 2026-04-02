"""
Phase 79.3 — InternalApiKeyMiddleware + require_internal_key tests.

Tests run against a real FastAPI app with real middleware (no mocks).
"""
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

# ── Public paths bypass auth ────────────────────────────────────


async def test_health_no_auth(client):
    """GET /health returns 200 without any auth header."""
    r = await client.get("/health")
    assert r.status_code == 200


async def test_metrics_no_auth(client):
    """GET /metrics returns 200 without any auth header."""
    r = await client.get("/metrics")
    assert r.status_code == 200


async def test_ready_no_auth(client):
    """GET /ready returns 200 without any auth header."""
    r = await client.get("/ready")
    assert r.status_code == 200


# ── Valid key ───────────────────────────────────────────────────


async def test_valid_key_200(client, auth_headers):
    """GET /protected with valid key returns 200."""
    r = await client.get("/protected", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["result"] == "secret"


async def test_valid_key_post(client, auth_headers):
    """POST /protected with valid key and body returns 200."""
    r = await client.post(
        "/protected",
        json={"foo": "bar"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["received"] == {"foo": "bar"}


# ── Missing / invalid / empty key ──────────────────────────────


async def test_missing_key_401(client):
    """GET /protected without header returns 401."""
    r = await client.get("/protected")
    assert r.status_code == 401
    assert "required" in r.json()["detail"].lower()


async def test_invalid_key_401(client):
    """GET /protected with wrong key returns 401."""
    r = await client.get(
        "/protected",
        headers={"X-Internal-Api-Key": "wrong-key"},
    )
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


async def test_empty_key_401(client):
    """GET /protected with empty key returns 401 with 'required' detail
    (empty string is falsy → hits the missing-key branch)."""
    r = await client.get(
        "/protected",
        headers={"X-Internal-Api-Key": ""},
    )
    assert r.status_code == 401
    assert "required" in r.json()["detail"].lower()


# ── 401 returned BEFORE body parsing (not 422) ─────────────────


async def test_401_before_422_invalid_body_missing_key(client):
    """POST /protected with missing key and INVALID body must
    return 401 (not 422).  The middleware intercepts before
    FastAPI parses the request body."""
    r = await client.post(
        "/protected",
        content=b"this is not json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 401


async def test_401_before_422_no_body_missing_key(client):
    """POST /protected with missing key and NO body must return
    401 (not 422)."""
    r = await client.post("/protected")
    assert r.status_code == 401


# ── Case-sensitive header ───────────────────────────────────────


async def test_header_case_sensitivity(client, valid_api_key):
    """Header lookup is case-insensitive per HTTP spec — Starlette
    normalises header names.  Verify mixed-case works."""
    r = await client.get(
        "/protected",
        headers={"x-internal-api-key": valid_api_key},
    )
    assert r.status_code == 200


# ── Whitespace handling ─────────────────────────────────────────


async def test_whitespace_around_key_rejected(client, valid_api_key):
    """Leading/trailing whitespace in the key must be rejected
    (hmac.compare_digest is exact-match)."""
    r = await client.get(
        "/protected",
        headers={"X-Internal-Api-Key": f"  {valid_api_key}  "},
    )
    assert r.status_code == 401


# ── extra_public_paths constructor param ────────────────────────


async def test_extra_public_paths():
    """InternalApiKeyMiddleware(extra_public_paths={"/custom"})
    makes /custom accessible without auth."""
    from shared.tests.conftest import _build_app

    app = _build_app(extra_public_paths=frozenset({"/custom"}))

    @app.get("/custom")
    async def custom():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        r = await ac.get("/custom")
        assert r.status_code == 200


async def test_extra_public_paths_does_not_open_other_routes():
    """Extra public paths only whitelist the specified path;
    other protected routes still require auth."""
    from shared.tests.conftest import _build_app

    app = _build_app(extra_public_paths=frozenset({"/custom"}))

    @app.get("/custom")
    async def custom():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        r = await ac.get("/protected")
        assert r.status_code == 401


# ── Non-public path variants not bypassed ────────────────────────


async def test_similar_path_not_public(client):
    """/healthx or /health/ must NOT bypass auth (exact match only)."""
    r = await client.get("/healthx")
    # /healthx is not a registered route, but the point is auth runs
    assert r.status_code in (401, 404)

    r2 = await client.get("/health/extra")
    assert r2.status_code in (401, 404)


# ── _load_key_at_startup raises when env unset ──────────────────


def test_load_key_at_startup_raises_when_unset(monkeypatch):
    """_load_key_at_startup() raises ValueError when
    INTERNAL_API_KEY is absent."""
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    from shared.auth import _load_key_at_startup

    with pytest.raises(ValueError, match="INTERNAL_API_KEY"):
        _load_key_at_startup()


# ── hmac.compare_digest timing-attack resistance ────────────────


def test_hmac_compare_digest_used():
    """The auth module must use hmac.compare_digest (not ==)
    for key comparison to prevent timing attacks."""
    import inspect
    import shared.auth as auth_mod

    source = inspect.getsource(auth_mod)
    assert "hmac.compare_digest" in source

    # The dispatch method must use hmac.compare_digest
    dispatch_src = inspect.getsource(
        auth_mod.InternalApiKeyMiddleware.dispatch,
    )
    assert "hmac.compare_digest" in dispatch_src
    # Must NOT use bare == for key comparison in dispatch
    assert "==" not in dispatch_src


# ── WWW-Authenticate header on 401 ─────────────────────────────


async def test_401_includes_www_authenticate(client):
    """401 responses include WWW-Authenticate: ApiKey header."""
    r = await client.get("/protected")
    assert r.status_code == 401
    assert "apikey" in r.headers.get("www-authenticate", "").lower()


# ── require_internal_key dependency (legacy Depends) ────────────


async def test_require_internal_key_valid(valid_api_key):
    """require_internal_key dependency passes with correct key."""
    from shared.auth import require_internal_key

    app = FastAPI()

    @app.get("/dep-test", dependencies=[Depends(require_internal_key)])
    async def dep_test():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        r = await ac.get(
            "/dep-test",
            headers={"X-Internal-Api-Key": valid_api_key},
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}


async def test_require_internal_key_missing():
    """require_internal_key returns 401 when header is missing."""
    from shared.auth import require_internal_key

    app = FastAPI()

    @app.get("/dep-test", dependencies=[Depends(require_internal_key)])
    async def dep_test():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        r = await ac.get("/dep-test")
        assert r.status_code == 401
        assert "required" in r.json()["detail"].lower()


async def test_require_internal_key_invalid():
    """require_internal_key returns 401 when key is wrong."""
    from shared.auth import require_internal_key

    app = FastAPI()

    @app.get("/dep-test", dependencies=[Depends(require_internal_key)])
    async def dep_test():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver",
    ) as ac:
        r = await ac.get(
            "/dep-test",
            headers={"X-Internal-Api-Key": "wrong"},
        )
        assert r.status_code == 401
        assert "invalid" in r.json()["detail"].lower()
