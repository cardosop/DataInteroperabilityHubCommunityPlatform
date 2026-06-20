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

from tests._persona_provisioning import PersonaCredentials, provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_base_url

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _e2e_token() -> str:
    """Return the E2E shared secret for /test/ensure-e2e-* endpoints."""
    import os as _os

    return _os.environ.get("E2E_TEST_SECRET", "e2e-test-secret-for-local-dev")


def _auth_headers(
    token: str,
    tenant_id: str | None = None,
    *,
    e2e: bool = False,
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant_id:
        headers["X-Tenant-Id"] = str(tenant_id)
    if e2e:
        headers["X-E2E-Token"] = _e2e_token()
    return headers


def _setup_two_tenants(creds: PersonaCredentials):
    """Use the E2E helper to ensure the user has access to two tenants.

    Returns (primary_tenant_id, secondary_tenant_id) or calls
    pytest.skip if multi-tenant setup is not available.

    When earlier tests have invalidated the persona's cached JWT
    (token_version bump), the helper re-provisions fresh credentials
    and retries once.
    """
    current_creds = creds

    for attempt in range(2):
        base = api_base_url()
        resp = requests.post(
            f"{base}/test/ensure-e2e-tenant-switch-setup/",
            headers=_auth_headers(current_creds.api_key, e2e=True),
            json={},
            timeout=15,
        )

        if resp.status_code == 200:
            body = resp.json()
            primary = body.get("primary_tenant_id")
            secondary = body.get("secondary_tenant_id")

            if not primary or not secondary:
                pytest.skip(f"Tenant setup did not return two tenant IDs: {body}")
            if primary == secondary:
                pytest.skip(
                    "Primary and secondary tenants are the same -- isolation test not possible"
                )
            return primary, secondary

        if resp.status_code == 404:
            pytest.skip("E2E tenant-switch-setup helper not available (404)")

        # Any non-404, non-200 error — force fresh persona login
        # (bypass cache) and retry once.
        if attempt == 0:
            import glob as _glob
            import pathlib as _pl

            from tests._persona_provisioning import _CACHE_DIR as _cdir

            role = current_creds.role
            for _f in _glob.glob(str(_cdir / f"*{role}*.json")):
                _pl.Path(_f).unlink(missing_ok=True)
            current_creds = provision_persona(role)
            continue

        pytest.skip(f"E2E tenant-switch-setup returned {resp.status_code}: {resp.text[:200]}")

    pytest.skip("E2E tenant-switch-setup failed after retry")


# ===========================================================================
# Tests
# ===========================================================================


def test_asset_invisible_across_tenants():
    """Create an asset in tenant A, then try to GET it from tenant B.
    Tenant B should receive 404 (or an empty result).
    """
    creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID
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
        f"Asset creation in tenant A failed: {create_resp.status_code}: {create_resp.text[:300]}"
    )
    asset_body = create_resp.json()
    asset_id = asset_body.get("id") or asset_body.get("key")
    assert asset_id, f"Asset creation response missing id: {asset_body}"

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
    creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID
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
        f"Asset listing in tenant B returned {list_resp.status_code}"
    )

    list_body = list_resp.json()
    results = list_body if isinstance(list_body, list) else list_body.get("results", [])
    leaked_names = [a.get("name") for a in results if a.get("name") == unique_name]
    assert len(leaked_names) == 0, (
        f"Asset '{unique_name}' from tenant A leaked into tenant B listing!"
    )


def test_contract_invisible_across_tenants():
    """Create a contract in tenant A, then try to GET it from
    tenant B.  Tenant B should receive 404.
    """
    creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID
    tenant_a, tenant_b = _setup_two_tenants(creds)
    base = api_base_url()

    # Create contract in tenant A.  The ODCS normaliser requires a valid
    # Open Data Contract Standard document with ``schema.fields[]`` so the
    # structural-floor check passes.
    import json as _json

    contract_name = fresh_id("iso-contract")
    odcs_doc = {
        "apiVersion": "odcs/v3",
        "kind": "Contract",
        "id": contract_name,
        "name": contract_name,
        "hub_contract_version": "1.0.0",
        "info": {
            "name": contract_name,
            "description": "Cross-tenant isolation test contract",
        },
        "schema": {
            "fields": [
                {"name": "id", "type": "string", "description": "Primary key"},
                {"name": "value", "type": "integer", "description": "Test value"},
            ],
        },
    }
    create_resp = requests.post(
        f"{base}/contracts/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "name": contract_name,
            "description": "Cross-tenant isolation test contract",
            "original_raw": _json.dumps(odcs_doc),
            "original_format": "JSON",
        },
        timeout=15,
    )

    if create_resp.status_code in (404, 405):
        pytest.skip("Contracts endpoint not available")

    assert create_resp.status_code in (200, 201), (
        f"Contract creation failed: {create_resp.status_code}: {create_resp.text[:300]}"
    )
    contract_body = create_resp.json()
    contract_id = contract_body.get("id")
    assert contract_id, f"Contract response missing id: {contract_body}"

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
    creds = provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID
    tenant_a, tenant_b = _setup_two_tenants(creds)
    base = api_base_url()

    # First create a test asset in tenant A so the compliance run has
    # a resource to scan.  (ComplianceRunCreateSerializer requires at
    # least one of asset_id / dataset_id / file_id.)
    asset_key = fresh_id("iso-comp-asset")
    asset_resp = requests.post(
        f"{base}/assets/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "name": f"Compliance Asset {asset_key}",
            "key": asset_key,
            "description": "Asset for compliance isolation test",
            "visibility": "INTERNAL",
        },
        timeout=15,
    )
    assert asset_resp.status_code in (200, 201), (
        f"Asset creation for compliance test failed: "
        f"{asset_resp.status_code}: {asset_resp.text[:200]}"
    )
    asset_id = asset_resp.json().get("id") or asset_resp.json().get("key")

    # Trigger a compliance run in tenant A
    run_resp = requests.post(
        f"{base}/compliance/runs/",
        headers=_auth_headers(creds.api_key, tenant_a),
        json={
            "asset_id": asset_id,
        },
        timeout=15,
    )

    if run_resp.status_code in (404, 405):
        pytest.skip("Compliance runs endpoint not available")

    assert run_resp.status_code in (200, 201, 202), (
        f"Compliance run creation failed: {run_resp.status_code}: {run_resp.text[:300]}"
    )
    run_body = run_resp.json()
    run_id = run_body.get("id") or run_body.get("run_id")
    assert run_id, f"Compliance run response missing id: {run_body}"

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
