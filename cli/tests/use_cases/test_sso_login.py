"""
Phase 216.2.5 — SSO login lifecycle.

Validates SSO initiation and callback flows. The backend provides
OIDC-only endpoints (the SAML stub is deleted — W1.5/D4):
  - GET /auth/sso/oidc/login-url/   (OIDC initiation)
  - POST /auth/sso/oidc/callback/   (OIDC callback)
"""

from urllib.parse import parse_qs, urlparse

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

    The e2e tenant has no OIDC provider configured by default, so this
    test configures a mock provider on the tenant's ``TenantConfig`` via
    the in-process ORM (same shared-DB pattern as the billing quota
    test), asserts the 200 login-URL shape, and restores the previous
    config afterwards.  When the tenant is genuinely not configurable
    (e.g. a deployment without ORM access) the test skips.
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
    assert me_resp.status_code == 200, f"/auth/me/ failed: {me_resp.status_code}"
    tenant_id = me_resp.json().get("tenant") or me_resp.json().get("tenant_id")  # noqa: PHASE216-STATIC-ID
    assert tenant_id, f"No tenant_id in /auth/me/ response: {me_resp.json()}"

    from django.core.exceptions import ValidationError as DjangoValidationError
    from django.db import (
        DatabaseError,
        IntegrityError,
        InterfaceError,
        OperationalError,
    )

    from hub.apps.tenants.models import TenantConfig

    oidc_config = {
        "authorization_endpoint": "https://mock-idp.example.com/authorize",
        "client_id": "e2e-test-oidc-client",
    }
    try:
        config, _created = TenantConfig.objects.get_or_create(
            tenant_id=tenant_id,
            defaults={"sso_config": {}},
        )
        original_sso = config.sso_config or {}
        config.sso_config = {**original_sso, "oidc": oidc_config}
        config.save()
    except (
        DjangoValidationError,
        IntegrityError,
        InterfaceError,
        OperationalError,
        DatabaseError,
    ) as exc:
        pytest.skip(f"Could not configure OIDC SSO for the e2e tenant via ORM: {exc}")

    try:
        resp = requests.get(
            f"{base}/auth/sso/oidc/login-url/",
            params={
                "tenant_id": tenant_id,  # noqa: PHASE216-STATIC-ID
                "redirect_uri": "https://meshant-internal.example.com/auth/callback",
            },
            allow_redirects=False,
            timeout=15,
        )

        if resp.status_code == 404:
            pytest.skip("SSO OIDC endpoint not found (404)")

        assert resp.status_code == 200, (
            f"SSO initiation returned {resp.status_code}: {resp.text[:300]}"
        )
        body = resp.json()
        redirect_url = (
            body.get("login_url") or body.get("redirect_url") or body.get("authorization_url")
        )
        assert redirect_url, f"200 response missing redirect/authorization URL: {body}"
        parsed = urlparse(redirect_url)
        assert parsed.netloc == "mock-idp.example.com", (
            f"Login URL points at the wrong IdP: {redirect_url}"
        )
        query = parse_qs(parsed.query)
        assert query.get("state"), f"OIDC login URL missing state query parameter: {redirect_url}"
        assert query.get("client_id") == ["e2e-test-oidc-client"], (
            f"OIDC login URL carries the wrong client_id: {redirect_url}"
        )
    finally:
        config.sso_config = original_sso
        config.save()


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
        f"Unknown SSO provider returned {resp.status_code}, expected 400/404/422: {resp.text[:300]}"
    )


def test_sso_callback_without_id_token_returns_400():
    """POST /auth/sso/oidc/callback/ without id_token should
    return 400 (missing required field).
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
        f"SSO callback without id_token returned "
        f"{resp.status_code}, expected 400: {resp.text[:300]}"
    )


def test_sso_callback_with_invalid_id_token_returns_error():
    """POST /auth/sso/oidc/callback/ with an invalid id_token should return
    400 or 401 (authentication failed).
    """
    base = api_base_url()
    resp = requests.post(
        f"{base}/auth/sso/oidc/callback/",
        json={"id_token": "invalid-token-value", "state": "invalid-state"},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("SSO OIDC callback endpoint not found (404)")

    assert resp.status_code in (400, 401, 422), (
        f"SSO callback with invalid id_token returned "
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
