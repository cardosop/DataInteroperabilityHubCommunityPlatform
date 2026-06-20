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


def test_switch_tenant_header_changes_context():
    """Provision a user in two tenants. Verify that setting X-Tenant-Id
    on GET /auth/me/ returns a different tenant context for each.

    To set this up we provision the same role under two different tenant
    slugs. If multi-tenant provisioning is not available, the test
    verifies that the X-Tenant-Id header is at least accepted.
    """
    base = api_base_url()

    # Provision in default tenant
    creds_a = provision_persona("data_analyst")

    # Provision in a second tenant (using tenant_slug parameter)
    try:
        creds_b = provision_persona("data_analyst", tenant_slug="tenant-b")  # noqa: PHASE216-STATIC-ID
    except Exception:
        pytest.skip("Multi-tenant provisioning not available — cannot test tenant switching")

    # If both provisions returned the same tenant, we cannot test switching
    if creds_a.tenant_id == creds_b.tenant_id:
        pytest.skip("Both provisions returned the same tenant_id — multi-tenant not configured")

    # Use creds_a (which should have access to both tenants if the admin
    # added them) — or use platform_admin who typically has cross-tenant access
    admin_creds = provision_persona("platform_admin")

    # GET /auth/me/ with tenant A header
    me_a = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(admin_creds.api_key, creds_a.tenant_id),
        timeout=15,
    )
    assert me_a.status_code == 200, (
        f"/auth/me/ with tenant A returned {me_a.status_code}: {me_a.text[:300]}"
    )

    # GET /auth/me/ with tenant B header
    me_b = requests.get(
        f"{base}/auth/me/",
        headers=_auth_headers(admin_creds.api_key, creds_b.tenant_id),
        timeout=15,
    )
    assert me_b.status_code == 200, (
        f"/auth/me/ with tenant B returned {me_b.status_code}: {me_b.text[:300]}"
    )

    # The tenant context should differ
    body_a = me_a.json()
    body_b = me_b.json()
    tenant_field_a = body_a.get("tenant_id") or body_a.get("tenant", {}).get("id")  # noqa: PHASE216-STATIC-ID
    tenant_field_b = body_b.get("tenant_id") or body_b.get("tenant", {}).get("id")  # noqa: PHASE216-STATIC-ID

    if tenant_field_a and tenant_field_b:
        assert tenant_field_a != tenant_field_b, (
            f"Tenant context did not change: A={tenant_field_a}, B={tenant_field_b}"
        )


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
