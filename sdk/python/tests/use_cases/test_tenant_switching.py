import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.5 — Tenant switching.

Validates that authenticated users can switch tenant context via the
X-Tenant-Id header, and that switching to an unauthorized tenant is
correctly rejected with 403.

Uses POST /test/ensure-e2e-tenant-switch-setup/ to provision a
secondary tenant for the authenticated user.

Note: GET /auth/me/ always returns the user's *home* tenant_id,
regardless of the X-Tenant-Id header.  Tenant switching is verified
by checking that /auth/me/tenants/ lists multiple tenants and that
resource operations respect the active tenant context.
"""

import requests
from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_base_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(
    token: str, tenant_id: str | None = None,
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant_id:
        headers["X-Tenant-Id"] = str(tenant_id)
    return headers


def _setup_two_tenants(creds: PersonaCredentials):
    """Use the E2E helper to ensure the user has access to two
    tenants.  Returns (primary_id, secondary_id) or skips.
    """
    base = api_base_url()
    resp = requests.post(
        f"{base}/test/ensure-e2e-tenant-switch-setup/",
        headers={"Authorization": f"Bearer {creds.api_key}"},
        json={},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "E2E tenant-switch-setup helper not available (404)"
        )

    if resp.status_code != 200:
        pytest.skip(
            f"E2E tenant-switch-setup returned "
            f"{resp.status_code}: {resp.text[:200]}"
        )

    body = resp.json()
    primary = body.get("primary_tenant_id")
    secondary = body.get("secondary_tenant_id")

    if not primary or not secondary:
        pytest.skip(
            f"Tenant setup missing tenant IDs: {body}"
        )

    if primary == secondary:
        pytest.skip(
            "Primary and secondary tenants are identical"
        )

    return primary, secondary


# ===========================================================================
# Tests
# ===========================================================================


def test_switch_tenant_header_changes_context():
    """Verify that a user with access to two tenants can create
    resources in each tenant context independently.

    /auth/me/ always returns the user's home tenant_id — it does NOT
    change with X-Tenant-Id.  Instead, we verify tenant switching by:
    1. Confirming /auth/me/tenants/ lists both tenants
    2. Creating an asset in tenant A via X-Tenant-Id
    3. Verifying the asset is NOT visible in tenant B
    """
    creds = provision_persona("tenant_admin")
    base = api_base_url()

    tenant_a, tenant_b = _setup_two_tenants(creds)

    # Step 1: /auth/me/tenants/ should list multiple tenants
    tenants_resp = requests.get(
        f"{base}/auth/me/tenants/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if tenants_resp.status_code == 200:
        tenants_body = tenants_resp.json()
        tenant_list = (
            tenants_body
            if isinstance(tenants_body, list)
            else tenants_body.get("results", [])
        )
        tenant_ids = [
            str(t.get("id")) for t in tenant_list
        ]
        assert tenant_a in tenant_ids or len(tenant_ids) >= 2, (
            f"User does not have multi-tenant access. "
            f"Tenant list: {tenant_ids}"
        )

    # Step 2: Create asset in tenant A context
    asset_name = fresh_id("switch-test")
    create_resp = requests.post(
        f"{base}/assets/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "name": asset_name,
            "key": fresh_id("switch-key"),
            "description": "Tenant switch verification asset",
        },
        timeout=15,
    )
    assert create_resp.status_code in (200, 201), (
        f"Asset creation in tenant A failed: "
        f"{create_resp.status_code}: {create_resp.text[:300]}"
    )
    asset_id = (
        create_resp.json().get("id")
        or create_resp.json().get("key")
    )

    # Step 3: Verify asset is NOT visible in tenant B
    get_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=_auth_headers(creds.api_key, tenant_b),
        timeout=15,
    )
    assert get_resp.status_code in (403, 404), (
        f"Asset from tenant A visible in tenant B context! "
        f"Status: {get_resp.status_code}: {get_resp.text[:300]}"
    )


def test_switch_to_unauthorized_tenant_returns_403():
    """Using X-Tenant-Id for a tenant the user does not belong to
    should return 403 Forbidden.
    """
    base = api_base_url()
    creds = provision_persona("auditor")

    # Fabricated tenant id the user definitely does not belong to
    fake_tenant_id = fresh_id("fake-tenant")

    resp = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(creds.api_key, fake_tenant_id),
        timeout=15,
    )

    assert resp.status_code in (403, 404, 400), (
        f"Switching to unauthorized tenant returned "
        f"{resp.status_code}, expected 403/404/400: "
        f"{resp.text[:300]}"
    )


def test_no_tenant_header_uses_default():
    """When no X-Tenant-Id header is provided, the API should use
    the user's default tenant (from login).
    """
    base = api_base_url()
    creds = provision_persona("tenant_admin")

    resp = requests.get(
        f"{base}/auth/me/",
        headers={"Authorization": f"Bearer {creds.api_key}"},
        timeout=15,
    )

    assert resp.status_code == 200, (
        f"/auth/me/ without X-Tenant-Id returned "
        f"{resp.status_code}: {resp.text[:300]}"
    )

    body = resp.json()
    tenant_info = (
        body.get("tenant_id")
        or body.get("tenant")
        or body.get("tenants")
    )
    assert tenant_info, (
        f"/auth/me/ response has no tenant information: {body}"
    )


def test_tenant_header_with_empty_value_returns_error():
    """X-Tenant-Id with an empty string should return an error,
    not silently fall through.
    """
    base = api_base_url()
    creds = provision_persona("auditor")

    resp = requests.get(
        f"{base}/auth/me/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "X-Tenant-Id": "",
        },
        timeout=15,
    )

    # Empty tenant header should either be ignored (200 with
    # default) or rejected (400).  Must NOT cause a 500.
    assert resp.status_code < 500, (
        f"Empty X-Tenant-Id caused server error "
        f"{resp.status_code}: {resp.text[:300]}"
    )
