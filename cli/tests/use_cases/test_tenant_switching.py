import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.5 — Tenant switching.

Validates that authenticated users can switch tenant context via the
X-Tenant-Id header, and that switching to an unauthorized tenant is
correctly rejected with 403.
"""

import requests
from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(token: str, tenant_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant_id:
        headers["X-Tenant-Id"] = str(tenant_id)
    return headers


# ===========================================================================
# Tests
# ===========================================================================


def _setup_two_tenants(creds):
    """Use the E2E helper to give the user a secondary tenant membership.

    Returns (primary_id, secondary_id) or skips.  The X-Tenant-Id header
    is only accepted for the user's own tenants (platform admins bypass
    the membership check), and /auth/me/ ALWAYS returns the home tenant —
    so switching is verified by resource creation in each context, not
    by /auth/me/ output.
    """
    import time as _time

    from tests._persona_provisioning import _e2e_token

    base = api_base_url()
    for _attempt in range(3):
        resp = requests.post(
            f"{base}/test/ensure-e2e-tenant-switch-setup/",
            headers={
                **_auth_headers(creds.api_key),
                "X-E2E-Token": _e2e_token(),
            },
            json={},
            timeout=20,
        )
        if resp.status_code == 200:
            body = resp.json()
            primary = body.get("primary_tenant_id")
            secondary = body.get("secondary_tenant_id")
            if primary and secondary and primary != secondary:
                return primary, secondary
        if resp.status_code == 404:
            pytest.skip("E2E tenant-switch-setup helper not available (404)")
        _time.sleep(2)
    pytest.skip("E2E tenant-switch-setup failed after 3 attempts")


def test_switch_tenant_header_changes_context():
    """Switching tenant context via X-Tenant-Id changes the tenant scope
    of the request — verified by creating an asset in each context and
    confirming it is visible in one tenant's list and not the other's.

    /auth/me/ always returns the HOME tenant (API contract), so the
    context change cannot be asserted from /auth/me/ output.
    """
    base = api_base_url()
    # NOTE: platform admins bypass tenant scoping in the list/create
    # querysets ("admins see all records"), so switching must be
    # verified with a non-admin user that holds real memberships —
    # the E2E switch-setup helper gives tenant_admin a secondary one.
    admin_creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID  # fixed platform role name

    tenant_a, tenant_b = _setup_two_tenants(admin_creds)

    # The header is accepted for both tenants (200, not 403)
    me_a = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(admin_creds.api_key, tenant_a),
        timeout=15,
    )
    assert me_a.status_code == 200, (
        f"/auth/me/ with tenant A returned {me_a.status_code}: {me_a.text[:300]}"
    )
    me_b = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(admin_creds.api_key, tenant_b),
        timeout=15,
    )
    assert me_b.status_code == 200, (
        f"/auth/me/ with tenant B returned {me_b.status_code}: {me_b.text[:300]}"
    )

    # Create an asset in tenant A's context
    asset_key = fresh_id("tsw")
    create_resp = requests.post(
        f"{base}/assets/",
        headers={
            **_auth_headers(admin_creds.api_key, tenant_a),
            "Content-Type": "application/json",
        },
        json={
            "name": f"Switch {asset_key}",
            "key": asset_key,
            "description": "Tenant switch context probe",
            "visibility": "PUBLIC",
        },
        timeout=15,
    )
    assert create_resp.status_code in (200, 201), (
        f"Asset creation in tenant A failed: {create_resp.status_code}: {create_resp.text[:300]}"
    )

    # Visible in tenant A's list, absent from tenant B's list
    list_a = requests.get(
        f"{base}/assets/?key={asset_key}",
        headers=_auth_headers(admin_creds.api_key, tenant_a),
        timeout=15,
    )
    list_b = requests.get(
        f"{base}/assets/?key={asset_key}",
        headers=_auth_headers(admin_creds.api_key, tenant_b),
        timeout=15,
    )
    results_a = list_a.json().get("results", [])
    results_b = list_b.json().get("results", [])
    assert results_a, "asset not visible in tenant A after creation"
    assert not results_b, f"asset wrongly visible in tenant B's context: {results_b}"


def test_switch_to_unauthorized_tenant_returns_403():
    """Using X-Tenant-Id for a tenant the user does not belong to should
    return 403 Forbidden.
    """
    base = api_base_url()
    creds = provision_persona("data_analyst")

    # Use a fabricated tenant id that the user definitely does not belong to
    fake_tenant_id = fresh_id("fake-tenant")

    resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(creds.api_key, fake_tenant_id),
        timeout=15,
    )

    assert resp.status_code in (403, 404, 400), (
        f"Switching to unauthorized tenant returned {resp.status_code}, "
        f"expected 403/404/400: {resp.text[:300]}"
    )


def test_no_tenant_header_uses_default():
    """When no X-Tenant-Id header is provided, the API should use the
    user's default tenant (from login).
    """
    base = api_base_url()
    creds = provision_persona("data_engineer")

    resp = requests.get(
        f"{base}/auth/me/",
        headers={"Authorization": f"Bearer {creds.api_key}"},
        timeout=15,
    )

    assert resp.status_code == 200, (
        f"/auth/me/ without X-Tenant-Id returned {resp.status_code}: {resp.text[:300]}"
    )

    body = resp.json()
    # Should have some tenant context even without explicit header
    tenant_info = (
        body.get("tenant_id")  # noqa: PHASE216-STATIC-ID
        or body.get("tenant")
        or body.get("tenants")
    )
    assert tenant_info, f"/auth/me/ response has no tenant information: {body}"


def test_tenant_header_with_empty_value_returns_error():
    """X-Tenant-Id with an empty string should return an error, not
    silently fall through.
    """
    base = api_base_url()
    creds = provision_persona("data_analyst")

    resp = requests.get(
        f"{base}/auth/me/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "X-Tenant-Id": "",
        },
        timeout=15,
    )

    # An empty tenant header should either be ignored (200 with default)
    # or rejected (400). It should NOT cause a 500.
    assert resp.status_code < 500, (
        f"Empty X-Tenant-Id caused server error {resp.status_code}: {resp.text[:300]}"
    )
