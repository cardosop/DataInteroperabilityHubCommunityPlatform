"""
Phase 270.C.3 — INTERNAL_API_KEY rotation: dual-key middleware tests.

What this suite pins
====================
(REQ-SEC-INTERNAL-KEY-ROTATION in
``openspec/changes/preprod01/specs/marketplace-tax-compliance-deltas/spec.md``):

1.  **Dual-key acceptance during the 24h overlap window.** The
    middleware MUST accept either ``INTERNAL_API_KEY`` (current,
    just-rotated) OR ``INTERNAL_API_KEY_PREVIOUS`` (the value the
    rotation just retired). Without the overlap, a rolling deploy
    would 401 the half of pods that haven't picked up the new
    secret yet.

2.  **Constant-time on BOTH comparisons.** Each accepted-or-not
    check uses ``hmac.compare_digest`` (same constant-time
    primitive the single-key version used). An attacker MUST NOT
    be able to distinguish "matched current" from "matched
    previous" from "matched neither" via timing.

3.  **Empty/absent previous key collapses to single-key mode.**
    When ``INTERNAL_API_KEY_PREVIOUS`` is empty or absent (the
    steady state outside a rotation window), the middleware
    behaves identically to the pre-Phase-270.C.3 single-key
    version. No regression on the 99% steady-state path.

4.  **Same-key both slots → behaves like single-key.** If a
    deploy accidentally populates ``CURRENT`` and ``PREVIOUS``
    with the SAME value (e.g. the rotation Lambda fails to
    advance), the middleware still works (accepts the value).
    The ``KeyRotationOverdue`` Prometheus alert catches the
    rotation-Lambda failure separately.

5.  **Reject the empty-string in PREVIOUS as if-absent.** Empty
    string MUST NOT match any presented header (defence: an
    attacker presenting an empty ``X-Internal-Api-Key`` header
    would otherwise short-circuit through the PREVIOUS branch).

6.  **WWW-Authenticate + structured 401 body preserved.** All
    existing 401 contract surface (header, body) survives the
    dual-key refactor.

NO-MOCKS POLICY
===============
Tests run against a real FastAPI app with real middleware (no
mocks). The PREVIOUS-key value is configured via ``monkeypatch``
on the ``shared.auth._INTERNAL_API_KEY_PREVIOUS`` module-level
variable — NOT via env-var override (env-var is read at module
import time, not at request time). This is the same pattern the
existing single-key tests use: env at module-top, swap private
module state in test setup for variations.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# These imports rely on the session-scoped fixtures in
# ``services/shared/tests/conftest.py`` having already set
# ``INTERNAL_API_KEY`` BEFORE importing shared.auth. The same
# bootstrap-env-first pattern is documented at conftest.py:4-12.
from shared.auth import InternalApiKeyMiddleware

_PREV_KEY = "test-shared-services-key-PREVIOUS-rotation"
_BOGUS_KEY = "test-shared-services-key-BOGUS"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(InternalApiKeyMiddleware)

    @app.get("/protected")
    async def protected():
        return {"result": "secret"}

    return app


@pytest.fixture
async def dual_key_client(monkeypatch):
    """Yield an AsyncClient where the middleware has BOTH a
    CURRENT key (the session-level ``_INTERNAL_API_KEY``) AND a
    PREVIOUS key (``_PREV_KEY``). Mirrors the rotation overlap
    state: both keys MUST be accepted for the duration of the
    24h window."""
    import shared.auth as auth_mod

    monkeypatch.setattr(
        auth_mod,
        "_INTERNAL_API_KEY_PREVIOUS",
        _PREV_KEY,
    )
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture
async def empty_prev_client(monkeypatch):
    """Yield an AsyncClient where ``_INTERNAL_API_KEY_PREVIOUS`` is
    explicitly EMPTY (the steady-state outside a rotation window).
    Used to prove the dual-key code path doesn't regress single-
    key behaviour."""
    import shared.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_INTERNAL_API_KEY_PREVIOUS", "")
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tier 1 — Dual-key acceptance during overlap
# ---------------------------------------------------------------------------


class TestDualKeyAcceptance:
    async def test_current_key_accepted(
        self,
        dual_key_client,
        valid_api_key,
    ):
        """The CURRENT key is the freshly-rotated value. Pods that
        already picked up the new ExternalSecret sync present it."""
        r = await dual_key_client.get(
            "/protected",
            headers={"X-Internal-Api-Key": valid_api_key},
        )
        assert r.status_code == 200, r.text

    async def test_previous_key_accepted(self, dual_key_client):
        """The PREVIOUS key is the value the rotation just retired.
        Pods that haven't synced the new ExternalSecret yet present
        it — the middleware MUST accept it during the overlap."""
        r = await dual_key_client.get(
            "/protected",
            headers={"X-Internal-Api-Key": _PREV_KEY},
        )
        assert r.status_code == 200, r.text

    async def test_bogus_key_rejected(self, dual_key_client):
        """A third value (matches neither CURRENT nor PREVIOUS)
        MUST be rejected — the dual-acceptance must NOT collapse
        into "accept anything"."""
        r = await dual_key_client.get(
            "/protected",
            headers={"X-Internal-Api-Key": _BOGUS_KEY},
        )
        assert r.status_code == 401
        assert "invalid" in r.json()["detail"].lower()

    async def test_missing_header_rejected(self, dual_key_client):
        """Header-absent still 401, same body as the single-key
        version. The dual-key change must NOT affect this path."""
        r = await dual_key_client.get("/protected")
        assert r.status_code == 401
        assert "required" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tier 2 — Empty/absent PREVIOUS collapses to single-key mode
# ---------------------------------------------------------------------------


class TestEmptyPreviousCollapsesToSingleKey:
    async def test_current_key_still_works(
        self,
        empty_prev_client,
        valid_api_key,
    ):
        """No regression on the 99% steady-state path."""
        r = await empty_prev_client.get(
            "/protected",
            headers={"X-Internal-Api-Key": valid_api_key},
        )
        assert r.status_code == 200

    async def test_empty_string_in_header_does_not_match_empty_previous(
        self,
        empty_prev_client,
    ):
        """Defence: a client presenting an empty
        ``X-Internal-Api-Key`` header MUST NOT short-circuit to
        ``hmac.compare_digest("", "") == True`` via the PREVIOUS
        branch. The 401 message says "required" because empty
        falsey-check fires first."""
        r = await empty_prev_client.get(
            "/protected",
            headers={"X-Internal-Api-Key": ""},
        )
        assert r.status_code == 401
        assert "required" in r.json()["detail"].lower()

    async def test_what_would_have_been_previous_now_rejected(
        self,
        empty_prev_client,
    ):
        """With PREVIOUS empty (post-rotation-window state), the
        old key MUST now be rejected — proves the 24h overlap
        actually expires."""
        r = await empty_prev_client.get(
            "/protected",
            headers={"X-Internal-Api-Key": _PREV_KEY},
        )
        assert r.status_code == 401
        assert "invalid" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tier 3 — Constant-time + WWW-Authenticate preserved
# ---------------------------------------------------------------------------


class TestSecurityContractPreserved:
    def test_dispatch_uses_hmac_compare_digest_for_both_keys(self):
        """The dispatch method MUST use ``hmac.compare_digest``
        for BOTH the current-key and previous-key comparisons.
        Equality via ``==`` is a timing leak — same engineering
        rationale as Phase 270.C.1.AUDIT.1.
        """
        import inspect

        import shared.auth as auth_mod

        dispatch_src = inspect.getsource(
            auth_mod.InternalApiKeyMiddleware.dispatch,
        )
        # The dispatch must reference compare_digest in the key
        # comparison region. We can't trivially count occurrences
        # because of literal substring matches in comments, so
        # we anchor on the unambiguous prefix.
        assert dispatch_src.count("hmac.compare_digest") >= 2, (
            "dispatch must invoke hmac.compare_digest at least "
            "TWICE — once for CURRENT, once for PREVIOUS"
        )
        # And must NOT use bare == in dispatch for key compare.
        # (We allow == elsewhere — e.g. enforcement-flag check —
        # but the dispatch body's key comparison must be HMAC.)
        # Tighten: no `key ==` or `_INTERNAL_API_KEY ==` patterns.
        bad_patterns = ["key ==", "_INTERNAL_API_KEY =="]
        for pat in bad_patterns:
            assert pat not in dispatch_src, (
                f"dispatch must not use bare equality `{pat}` for key comparison (timing leak)"
            )

    async def test_401_includes_www_authenticate_dual_key(
        self,
        dual_key_client,
    ):
        """Even with dual-key enabled, 401 responses must carry
        the ``WWW-Authenticate: ApiKey`` header for client-side
        retry-with-different-credential semantics."""
        r = await dual_key_client.get("/protected")
        assert r.status_code == 401
        assert "apikey" in r.headers.get("www-authenticate", "").lower()

    async def test_401_body_is_valid_json_dual_key(self, dual_key_client):
        """The 401 response body must remain valid JSON."""
        r = await dual_key_client.get(
            "/protected",
            headers={"X-Internal-Api-Key": "wrong"},
        )
        assert r.status_code == 401
        body = json.loads(r.text)
        assert "detail" in body


# ---------------------------------------------------------------------------
# Tier 4 — Edge case: PREVIOUS == CURRENT (rotation Lambda failed mid-rotate)
# ---------------------------------------------------------------------------


class TestPreviousEqualsCurrentEdgeCase:
    async def test_same_value_in_both_slots_still_accepts(
        self,
        monkeypatch,
        valid_api_key,
    ):
        """If a rotation Lambda partially failed and left
        CURRENT == PREVIOUS, the middleware must still accept the
        value. The ``KeyRotationOverdue`` Prometheus alert is the
        separate signal that catches the rotation-Lambda failure.
        """
        import shared.auth as auth_mod

        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS",
            valid_api_key,
        )
        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as ac:
            r = await ac.get(
                "/protected",
                headers={"X-Internal-Api-Key": valid_api_key},
            )
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Tier 5 — Phase 270.C.3 audit-fix Gap 1 — 24h overlap window expiry
# ---------------------------------------------------------------------------


class TestOverlapWindowExpiry:
    """The rotation Lambda writes ``INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT``
    into the SM SecretString at "now + 24h". The middleware reads
    the env-var, and the dispatch path REJECTS the PREVIOUS key
    once wall-clock crosses the expiry. This enforces the spec-
    mandated "old key rejected after 24h overlap window" without
    requiring a follow-up scheduled-clear Lambda invocation."""

    async def test_previous_accepted_when_expiry_is_in_future(
        self,
        monkeypatch,
    ):
        """The happy path during the 24h overlap — the rotation
        completed within the last 24h, the EXPIRES_AT epoch is
        still in the future, PREVIOUS is accepted."""
        import time as _time

        import shared.auth as auth_mod

        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS",
            _PREV_KEY,
        )
        # 1 hour from now — well within the 24h overlap window.
        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT",
            int(_time.time()) + 3600,
        )
        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as ac:
            r = await ac.get(
                "/protected",
                headers={"X-Internal-Api-Key": _PREV_KEY},
            )
            assert r.status_code == 200, r.text

    async def test_previous_rejected_after_expiry(self, monkeypatch):
        """The spec-mandated assertion — once wall-clock crosses
        ``INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT``, the PREVIOUS key
        MUST be rejected even though it's still populated in the
        env. Simulates a pod that started during a rotation but
        is still running 24+ hours later — without restart."""
        import time as _time

        import shared.auth as auth_mod

        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS",
            _PREV_KEY,
        )
        # 1 second in the PAST — the overlap window has elapsed.
        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT",
            int(_time.time()) - 1,
        )
        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as ac:
            r = await ac.get(
                "/protected",
                headers={"X-Internal-Api-Key": _PREV_KEY},
            )
            assert r.status_code == 401, r.text
            assert "invalid" in r.json()["detail"].lower()

    async def test_current_key_still_works_after_previous_expired(
        self,
        monkeypatch,
        valid_api_key,
    ):
        """Even after the PREVIOUS slot has expired, the CURRENT
        key MUST still work. Pins that the expiry only affects
        the PREVIOUS branch — not a regression on the steady-state
        path."""
        import time as _time

        import shared.auth as auth_mod

        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS",
            _PREV_KEY,
        )
        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT",
            int(_time.time()) - 86400,  # expired 24h ago
        )
        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as ac:
            r = await ac.get(
                "/protected",
                headers={"X-Internal-Api-Key": valid_api_key},
            )
            assert r.status_code == 200, r.text

    async def test_expires_at_zero_disables_enforcement(
        self,
        monkeypatch,
    ):
        """EXPIRES_AT == 0 is the rollout-compatibility sentinel
        ("no expiry set") — the middleware accepts PREVIOUS
        indefinitely. This is the path services take BEFORE the
        rotation Lambda starts emitting the field; once the next
        rotation runs, the field is populated and enforcement
        kicks in."""
        import shared.auth as auth_mod

        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS",
            _PREV_KEY,
        )
        monkeypatch.setattr(
            auth_mod,
            "_INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT",
            0,
        )
        app = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as ac:
            r = await ac.get(
                "/protected",
                headers={"X-Internal-Api-Key": _PREV_KEY},
            )
            assert r.status_code == 200, r.text

    def test_load_previous_expires_at_handles_malformed(
        self,
        monkeypatch,
    ):
        """``_load_previous_expires_at_at_startup`` MUST treat a
        malformed env-var value as 0 (no enforcement) rather than
        raising at import time. Defence against a typo in the SM
        SecretString that would otherwise crash every service on
        startup."""
        monkeypatch.setenv(
            "INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT",
            "not-an-int",
        )
        from shared.auth import _load_previous_expires_at_at_startup

        assert _load_previous_expires_at_at_startup() == 0

    def test_load_previous_expires_at_parses_unix_epoch(
        self,
        monkeypatch,
    ):
        """Happy path — a well-formed integer string parses
        cleanly to int."""
        monkeypatch.setenv(
            "INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT",
            "1715520000",
        )
        from shared.auth import _load_previous_expires_at_at_startup

        assert _load_previous_expires_at_at_startup() == 1715520000
