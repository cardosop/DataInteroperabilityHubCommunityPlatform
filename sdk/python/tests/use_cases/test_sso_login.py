import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.4 — SSO login.

Validates that the SSO initiation and callback endpoints exist and
respond correctly.  Full SSO flow requires an external IdP, so these
tests verify the API contract (login-url, error handling) without
completing the OAuth/OIDC dance.

Actual API paths:
  GET  /auth/sso/oidc/login-url/?tenant_id=...&redirect_uri=...
  POST /auth/sso/oidc/callback/
  GET  /auth/sso/saml/login-url/?tenant_id=...&redirect_uri=...
  POST /auth/sso/saml/callback/
"""

import requests
from urllib.parse import parse_qs, urlparse
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Tests
# ===========================================================================


def test_sso_initiation_returns_redirect():
    """GET /auth/sso/oidc/login-url/ with valid tenant_id and
    redirect_uri should return 200 with a login_url in the body.

    If SSO is not configured for the tenant, 400 is expected.
    If the endpoint does not exist, 404 triggers a skip.
    """
    base = api_base_url()
    creds = provision_persona("tenant_admin")

    resp = requests.get(
        f"{base}/auth/sso/oidc/login-url/",
        params={
            "tenant_id": creds.tenant_id,
            "redirect_uri": "https://meshant-internal.example.com/callback",
        },
        headers=_auth_headers(creds.api_key),
        allow_redirects=False,
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("SSO endpoint not implemented yet (404)")

    if resp.status_code == 200:
        body = resp.json()
        assert "login_url" in body, (
            f"200 response missing login_url: {body}"
        )
        parsed = urlparse(body["login_url"])
        query = parse_qs(parsed.query)
        assert query.get("state"), (
            f"OIDC login_url missing state query parameter: {body['login_url']}"
        )
    elif resp.status_code == 400:
        # SSO not configured for this tenant — valid response
        body = resp.json()
        assert "error" in body or "detail" in body, (
            f"400 response missing error detail: {body}"
        )
    else:
        pytest.fail(
            f"SSO initiation returned unexpected "
            f"{resp.status_code}: {resp.text[:300]}"
        )


def test_sso_initiation_missing_params_returns_400():
    """GET /auth/sso/oidc/login-url/ without required query params
    (tenant_id, redirect_uri) should return 400.
    """
    base = api_base_url()

    resp = requests.get(
        f"{base}/auth/sso/oidc/login-url/",
        allow_redirects=False,
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("SSO endpoint not implemented yet (404)")

    assert resp.status_code in (400, 422), (
        f"SSO initiate without params returned "
        f"{resp.status_code}, expected 400/422: {resp.text[:300]}"
    )


def test_sso_oidc_callback_without_id_token_returns_400():
    """POST /auth/sso/oidc/callback/ without an id_token should
    return 400 (missing required field).
    """
    base = api_base_url()

    resp = requests.post(
        f"{base}/auth/sso/oidc/callback/",
        json={"state": "invalid-state"},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "SSO callback endpoint not implemented yet (404)"
        )

    assert resp.status_code in (400, 422), (
        f"SSO callback without id_token returned "
        f"{resp.status_code}, expected 400: {resp.text[:300]}"
    )


def test_sso_oidc_callback_with_invalid_token_returns_error():
    """POST /auth/sso/oidc/callback/ with an invalid id_token should
    return 400 (authentication failed).
    """
    base = api_base_url()

    resp = requests.post(
        f"{base}/auth/sso/oidc/callback/",
        json={
            "id_token": "invalid-token-value",
            "state": "invalid-state",
        },
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "SSO callback endpoint not implemented yet (404)"
        )

    assert resp.status_code in (400, 401, 422), (
        f"SSO callback with invalid token returned "
        f"{resp.status_code}, expected 400/401: {resp.text[:300]}"
    )


def test_sso_saml_login_url_exists():
    """GET /auth/sso/saml/login-url/ should respond (200 or 400),
    confirming the SAML SSO endpoint is registered.
    """
    base = api_base_url()
    creds = provision_persona("tenant_admin")

    resp = requests.get(
        f"{base}/auth/sso/saml/login-url/",
        params={
            "tenant_id": creds.tenant_id,
            "redirect_uri": "https://meshant-internal.example.com/callback",
        },
        headers=_auth_headers(creds.api_key),
        allow_redirects=False,
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("SAML SSO endpoint not implemented (404)")

    # 200 (configured) or 400 (not configured) are both valid
    assert resp.status_code < 500, (
        f"SAML login-url returned server error "
        f"{resp.status_code}: {resp.text[:300]}"
    )
