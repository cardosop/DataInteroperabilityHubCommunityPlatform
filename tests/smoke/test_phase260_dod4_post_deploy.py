"""
Smoke test — Phase 260 Definition of Done #4 (260.DoD.4).

Closes the production smoke contract for Phase 260:

    "Production smoke test post-deploy: synthetic cross-tenant requests
     trigger denial counter + alert; legitimate tenant requests succeed;
     cookie mode confirmed via curl; logout-all invalidates a probe
     JWT within 1 s."

Coverage map
------------
This file pins the two sub-criteria that no other smoke covers:

* **Legitimate tenant requests succeed** — the smoke admin can call
  `GET /api/v1/auth/me/` against staging and receive 200 with their
  resolved tenant_id. Acts as a positive control: if tenant scoping
  was over-rotated by 260.A, this test goes red instead of silently
  letting cross-tenant denials become a no-op.

* **Logout-all invalidates a probe JWT within 1 s** — the strictest
  sub-bullet. Drives a real login → me-probe → logout-all → me-probe
  cycle and asserts the second probe returns 401 with a SLO of 1 s
  between the logout response and the 401.

The other two DoD.4 sub-criteria are already pinned by neighbouring
files:

* Synthetic cross-tenant requests + counter increment →
  `tests/smoke/test_phase260_cross_tenant_denial.py`
* Cookie mode shape (HttpOnly + Secure + SameSite=Strict + Domain) →
  `tests/smoke/test_cookie_mode.py`

Together the three files form the full DoD.4 acceptance.

Required env vars (provided by ``conftest.py``)
-----------------------------------------------
SMOKE_ADMIN_EMAIL / SMOKE_ADMIN_PASSWORD
    Authenticated session for the probe.

Optional env vars
-----------------
SMOKE_PHASE260_LOGOUT_ALL_SLO_MS
    SLO budget in milliseconds between the logout-all response landing
    and the second /auth/me/ probe returning 401 (default: 1000 — the
    DoD.4 contract).
"""

from __future__ import annotations

import os
import time

import requests

AUTH_LOGIN_PATH = "/api/v1/auth/login/"
AUTH_LOGOUT_PATH = "/api/v1/auth/logout/"
AUTH_ME_PATH = "/api/v1/auth/me/"

#: SLO budget per DoD.4. Must be ≤ 1 s end-to-end.
LOGOUT_ALL_SLO_MS = int(os.getenv("SMOKE_PHASE260_LOGOUT_ALL_SLO_MS", "1000"))


def _login(
    base_url: str,
    admin_credentials: dict,
    timeout: int,
) -> tuple[str, requests.Response]:
    """Issue a login request and extract the access token.

    Returns ``(access_token, response)``. The ``response`` is returned
    so the caller can inspect cookies / status without a second call.

    The deployed staging API runs cookie-mode by default
    (`USE_HTTPONLY_AUTH_COOKIES=True` per `hub/settings.py:1701-1704`),
    which means the access token may live in a cookie rather than the
    response body. We probe both surfaces.
    """
    response = requests.post(
        f"{base_url}{AUTH_LOGIN_PATH}",
        json=admin_credentials,
        timeout=timeout,
    )
    assert response.status_code == 200, (
        f"Login failed ({response.status_code}): {response.text[:500]}"
    )

    body = response.json()
    token: str | None = body.get("access_token") or body.get("access") or body.get("token")
    if not token:
        # Cookie-mode: the access token is in a cookie set by the server.
        cookie = (
            response.cookies.get("access_token")
            or response.cookies.get("__Host-access_token")
            or response.cookies.get("__Secure-access_token")
        )
        if cookie:
            token = str(cookie)
    assert token, (
        "Login response carried neither `access_token` in body nor an "
        "access cookie — cannot probe with a Bearer header."
    )
    return token, response


def _me_probe(
    base_url: str,
    access_token: str,
    timeout: int,
    *,
    expect_status: int,
) -> requests.Response:
    response = requests.get(
        f"{base_url}{AUTH_ME_PATH}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Connection": "close",
        },
        timeout=timeout,
    )
    assert response.status_code == expect_status, (
        f"GET /auth/me/ expected {expect_status}, got {response.status_code}: {response.text[:300]}"
    )
    return response


class TestPhase260DoD4LegitimateTenantRequestsSucceed:
    """260.DoD.4 — positive control: legitimate tenant requests succeed."""

    def test_authenticated_me_probe_returns_tenant_id(
        self,
        base_url: str,
        admin_credentials: dict,
        timeout: int,
    ) -> None:
        access_token, _ = _login(base_url, admin_credentials, timeout)
        response = _me_probe(base_url, access_token, timeout, expect_status=200)
        body = response.json()
        tenant_id = (
            body.get("tenant")
            or body.get("tenant_id")
            or (body.get("tenant_membership") or {}).get("tenant_id")
        )
        assert tenant_id, (
            f"Legitimate /auth/me/ response missing tenant identifier — keys: {list(body.keys())}"
        )


class TestPhase260DoD4LogoutAllInvalidatesAccessJWT:
    """260.DoD.4 — logout-all invalidates a probe JWT within 1 s."""

    def test_logout_all_invalidates_probe_jwt_within_slo(
        self,
        base_url: str,
        admin_credentials: dict,
        timeout: int,
    ) -> None:
        access_token, _ = _login(base_url, admin_credentials, timeout)

        # Sanity: the freshly-issued token works BEFORE logout-all.
        _me_probe(base_url, access_token, timeout, expect_status=200)

        # Trigger logout-all by POST /auth/logout/ with no body
        # (per `hub/apps/auth/views.py:840-846` — the no-token branch
        # revokes every refresh token AND increments authz_version,
        # invalidating outstanding access JWTs).
        logout_started = time.perf_counter()
        logout_response = requests.post(
            f"{base_url}{AUTH_LOGOUT_PATH}",
            json={},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Connection": "close",
            },
            timeout=timeout,
        )
        assert logout_response.status_code == 200, (
            f"logout-all expected 200, got {logout_response.status_code}: "
            f"{logout_response.text[:300]}"
        )

        # Probe with the same token; SLO is the time between the logout
        # response landing and the 401 probe completing. We measure
        # end-to-end so a slow logout-all itself can't hide latency.
        probe = requests.get(
            f"{base_url}{AUTH_ME_PATH}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Connection": "close",
            },
            timeout=timeout,
        )
        elapsed_ms = (time.perf_counter() - logout_started) * 1000.0

        assert probe.status_code == 401, (
            f"After logout-all, /auth/me/ with the pre-logout JWT must "
            f"return 401; got {probe.status_code}: {probe.text[:300]}"
        )
        assert elapsed_ms <= LOGOUT_ALL_SLO_MS, (
            f"logout-all → 401 SLO miss: {elapsed_ms:.0f} ms > {LOGOUT_ALL_SLO_MS} ms (DoD.4)"
        )
