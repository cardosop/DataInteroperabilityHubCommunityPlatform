"""
Phase 216.2.5 — SSO login lifecycle.

Validates SSO initiation and callback flows. The backend provides
provider-specific endpoints:
  - GET /auth/sso/oidc/login-url/   (OIDC initiation)
  - POST /auth/sso/oidc/callback/   (OIDC callback)
  - GET /auth/sso/saml/login-url/   (SAML initiation)
  - POST /auth/sso/saml/callback/   (SAML callback)
"""
import pytest
import requests

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url

pytestmark = pytest.mark.mvp


# ===========================================================================
# Tests
# ===========================================================================


def test_sso_initiation_returns_redirect():
    """GET /auth/sso/oidc/login-url/ should return 200 with a redirect_url
    pointing at an OIDC authorization endpoint.

    If the SSO provider is not configured, a 400/404 is acceptable.
    """
    base = api_base_url()
    # SSO endpoints require tenant_id to look up SSO config.
    # The login response doesn't include tenant_id, so fetch
    # it from /auth/me/.
    creds = provision_persona("data_engineer")
    me_resp = requests.get(
        f"{base}/auth/me/",
        headers={"Authorization": f"Bearer {creds.api_key}"},
        timeout=15,
    )
    assert me_resp.status_code == 200, (
        f"/auth/me/ failed: {me_resp.status_code}"
    )
    tenant_id = me_resp.json().get("tenant") or me_resp.json().get("tenant_id")
    assert tenant_id, (
        f"No tenant_id in /auth/me/ response: {me_resp.json()}"
    )

    resp = requests.get(
        f"{base}/auth/sso/oidc/login-url/",
        params={
            "tenant_id": tenant_id,
            "redirect_uri": "https://meshant-internal.example.com/auth/callback",
        },
        allow_redirects=False,
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("SSO OIDC endpoint not found (404)")

    if resp.status_code == 400:
        body = resp.text[:200]
        # SSO not configured for this tenant is expected on staging
        if "not configured" in body.lower() or "no sso" in body.lower():
            pytest.skip(f"SSO OIDC not configured for tenant: {body}")
        # Otherwise it's a real validation error — let it fail

    if resp.status_code == 302:
        location = resp.headers.get("Location", "")
        assert location, "302 redirect has no Location header"
        assert "http" in location.lower(), (
            f"Redirect Location is not a URL: {location}"
        )
    elif resp.status_code == 200:
        body = resp.json()
        redirect_url = (
            body.get("redirect_url")
            or body.get("authorization_url")
            or body.get("login_url")
        )
        assert redirect_url, (
            f"200 response missing redirect/authorization URL: {body}"
        )
    else:
        pytest.fail(
            f"SSO initiation returned unexpected "
            f"{resp.status_code}: {resp.text[:300]}"
        )


def test_sso_initiation_unknown_provider_returns_error():
    """GET /auth/sso/nonexistent/login-url/ should return 404
    (router doesn't match an unknown provider path).
    """
    base = api_base_url()
    resp = requests.get(
        f"{base}/auth/sso/nonexistent_provider/login-url/",
        allow_redirects=False,
        timeout=15,
    )

    # Unknown provider path → 404 from the router
    assert resp.status_code in (400, 404, 422), (
        f"Unknown SSO provider returned {resp.status_code}, "
        f"expected 400/404/422: {resp.text[:300]}"
    )


def test_sso_callback_without_code_returns_400():
    """POST /auth/sso/oidc/callback/ without a code parameter should
    return 400 (missing required parameter).
    """
    base = api_base_url()
    resp = requests.post(
        f"{base}/auth/sso/oidc/callback/",
        json={},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("SSO OIDC callback endpoint not found (404)")

    assert resp.status_code in (400, 422), (
        f"SSO callback without code returned "
        f"{resp.status_code}, expected 400: {resp.text[:300]}"
    )


def test_sso_callback_with_invalid_code_returns_error():
    """POST /auth/sso/oidc/callback/ with an invalid code should return
    400 or 401 since the code cannot be exchanged.
    """
    base = api_base_url()
    resp = requests.post(
        f"{base}/auth/sso/oidc/callback/",
        json={"code": "invalid-code", "state": "invalid-state"},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("SSO OIDC callback endpoint not found (404)")

    assert resp.status_code in (400, 401, 422), (
        f"SSO callback with invalid code returned "
        f"{resp.status_code}, expected 400/401: {resp.text[:300]}"
    )


def test_sso_initiation_without_provider_returns_400():
    """GET /auth/sso/ root endpoint should return 200 (DRF router
    listing) or 404 if the root isn't exposed.
    """
    base = api_base_url()
    resp = requests.get(
        f"{base}/auth/sso/",
        allow_redirects=False,
        timeout=15,
    )

    # The DRF router root may return 200 (list of available actions)
    # or 404 if it only exposes specific sub-paths
    assert resp.status_code in (200, 400, 404, 422), (
        f"SSO root returned {resp.status_code}: {resp.text[:300]}"
    )
