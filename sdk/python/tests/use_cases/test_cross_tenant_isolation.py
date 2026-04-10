import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.6 — Cross-tenant data isolation.

Validates that resources created in one tenant are completely invisible
when the same user switches to a different tenant context.  This is a
critical security property: assets, contracts, and compliance runs must
never leak across tenant boundaries.

Uses the E2E helper POST /test/ensure-e2e-tenant-switch-setup/ to
provision a secondary tenant for the authenticated user, then tests
isolation via X-Tenant-Id header switching.
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
    """Use the E2E helper to ensure the user has access to two tenants.

    Returns (primary_tenant_id, secondary_tenant_id) or calls
    pytest.skip if multi-tenant setup is not available.
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
            f"Tenant setup did not return two tenant IDs: {body}"
        )

    if primary == secondary:
        pytest.skip(
            "Primary and secondary tenants are the same "
            "-- isolation test not possible"
        )

    return primary, secondary


# ===========================================================================
# Tests
# ===========================================================================


def test_asset_invisible_across_tenants():
    """Create an asset in tenant A, then try to GET it from tenant B.
    Tenant B should receive 404 (or an empty result).
    """
    creds = provision_persona("tenant_admin")
    tenant_a, tenant_b = _setup_two_tenants(creds)
    base = api_base_url()

    # Create asset in tenant A
    asset_name = fresh_id("iso-asset")
    create_resp = requests.post(
        f"{base}/assets/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "name": asset_name,
            "key": fresh_id("iso-key"),
            "description": "Cross-tenant isolation test asset",
        },
        timeout=15,
    )
    assert create_resp.status_code in (200, 201), (
        f"Asset creation in tenant A failed: "
        f"{create_resp.status_code}: {create_resp.text[:300]}"
    )
    asset_body = create_resp.json()
    asset_id = asset_body.get("id") or asset_body.get("key")
    assert asset_id, (
        f"Asset creation response missing id: {asset_body}"
    )

    # Try to read the asset from tenant B context
    get_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=_auth_headers(creds.api_key, tenant_b),
        timeout=15,
    )

    assert get_resp.status_code in (403, 404), (
        f"Asset from tenant A was visible in tenant B! "
        f"GET returned {get_resp.status_code}: "
        f"{get_resp.text[:300]}"
    )


def test_asset_list_does_not_leak_across_tenants():
    """List assets from tenant B and verify that an asset created in
    tenant A does not appear in the listing.
    """
    creds = provision_persona("tenant_admin")
    tenant_a, tenant_b = _setup_two_tenants(creds)
    base = api_base_url()

    # Create a uniquely-named asset in tenant A
    unique_name = fresh_id("leak-test")
    create_resp = requests.post(
        f"{base}/assets/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "name": unique_name,
            "key": fresh_id("leak-key"),
            "description": "Cross-tenant leak test",
        },
        timeout=15,
    )
    assert create_resp.status_code in (200, 201)

    # List assets in tenant B
    list_resp = requests.get(
        f"{base}/assets/",
        headers=_auth_headers(creds.api_key, tenant_b),
        timeout=15,
    )
    assert list_resp.status_code == 200, (
        f"Asset listing in tenant B returned "
        f"{list_resp.status_code}"
    )

    list_body = list_resp.json()
    results = (
        list_body
        if isinstance(list_body, list)
        else list_body.get("results", [])
    )
    leaked_names = [
        a.get("name") for a in results
        if a.get("name") == unique_name
    ]
    assert len(leaked_names) == 0, (
        f"Asset '{unique_name}' from tenant A leaked into "
        f"tenant B listing!"
    )


def test_contract_invisible_across_tenants():
    """Create a contract in tenant A, then try to GET it from
    tenant B.  Tenant B should receive 404.
    """
    creds = provision_persona("tenant_admin")
    tenant_a, tenant_b = _setup_two_tenants(creds)
    base = api_base_url()

    # Create contract in tenant A
    contract_name = fresh_id("iso-contract")
    create_resp = requests.post(
        f"{base}/contracts/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "name": contract_name,
            "description": "Cross-tenant isolation test contract",
        },
        timeout=15,
    )

    if create_resp.status_code in (404, 405):
        pytest.skip("Contracts endpoint not available")

    assert create_resp.status_code in (200, 201), (
        f"Contract creation failed: {create_resp.status_code}: "
        f"{create_resp.text[:300]}"
    )
    contract_body = create_resp.json()
    contract_id = contract_body.get("id")
    assert contract_id, (
        f"Contract response missing id: {contract_body}"
    )

    # Try to read from tenant B
    get_resp = requests.get(
        f"{base}/contracts/{contract_id}/",
        headers=_auth_headers(creds.api_key, tenant_b),
        timeout=15,
    )
    assert get_resp.status_code in (403, 404), (
        f"Contract from tenant A was visible in tenant B! "
        f"GET returned {get_resp.status_code}: "
        f"{get_resp.text[:300]}"
    )


def test_compliance_run_invisible_across_tenants():
    """Create a compliance run in tenant A, then try to GET it from
    tenant B.  Tenant B should receive 404.
    """
    creds = provision_persona("tenant_admin")
    tenant_a, tenant_b = _setup_two_tenants(creds)
    base = api_base_url()

    # Trigger a compliance run in tenant A
    run_resp = requests.post(
        f"{base}/compliance/runs/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "name": fresh_id("iso-compliance"),
            "description": "Cross-tenant isolation compliance run",
        },
        timeout=15,
    )

    if run_resp.status_code in (404, 405):
        pytest.skip("Compliance runs endpoint not available")

    assert run_resp.status_code in (200, 201, 202), (
        f"Compliance run creation failed: "
        f"{run_resp.status_code}: {run_resp.text[:300]}"
    )
    run_body = run_resp.json()
    run_id = run_body.get("id") or run_body.get("run_id")
    assert run_id, (
        f"Compliance run response missing id: {run_body}"
    )

    # Try to read from tenant B
    get_resp = requests.get(
        f"{base}/compliance/runs/{run_id}/",
        headers=_auth_headers(creds.api_key, tenant_b),
        timeout=15,
    )
    assert get_resp.status_code in (403, 404), (
        f"Compliance run from tenant A was visible in tenant B! "
        f"GET returned {get_resp.status_code}: "
        f"{get_resp.text[:300]}"
    )
