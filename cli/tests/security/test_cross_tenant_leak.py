import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.12 — Security: cross-tenant resource leak.

Verifies that resources in one tenant are invisible / inaccessible
from another tenant. Uses 2-tenant provisioning.
"""

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_get, api_post


def _create_asset_in_tenant(creds, name):
    """Create an asset and return its id."""
    resp = api_post("/assets/", creds, json={
        "name": name,
        "key": fresh_id("xtn-asset"),
    })
    if resp.status_code in (201, 200):
        return resp.json().get("id")
    return None


def test_asset_from_tenant_a_invisible_to_tenant_b():
    """Asset created by tenant-A engineer must return 404 from tenant-B engineer."""
    creds_a = provision_persona("data_engineer")
    creds_b = provision_persona("data_engineer", tenant_slug="tenant-b")

    asset_id = _create_asset_in_tenant(creds_a, f"xtn-test-{fresh_id('a')}")
    if asset_id is None:
        pytest.skip("Could not create asset in tenant A (API may not support it)")

    resp = api_get(f"/assets/{asset_id}/", creds_b)
    assert resp.status_code in (403, 404), (
        f"Tenant B saw tenant A's asset {asset_id}: status {resp.status_code}"
    )


def test_asset_list_does_not_leak_across_tenants():
    """GET /assets/ from tenant B must not contain assets from tenant A."""
    creds_a = provision_persona("data_engineer")
    creds_b = provision_persona("data_engineer", tenant_slug="tenant-b")

    marker = fresh_id("xtn-marker")
    _create_asset_in_tenant(creds_a, f"xtn-{marker}")

    resp = api_get("/assets/", creds_b)
    if resp.status_code != 200:
        pytest.skip(f"GET /assets/ returned {resp.status_code}")

    names = [a.get("name", "") for a in resp.json().get("results", [])]
    assert not any(marker in n for n in names), (
        f"Tenant B's asset list contains tenant A's marker '{marker}': {names}"
    )


def test_contract_from_tenant_a_invisible_to_tenant_b():
    """Contract created by tenant-A must return 404 from tenant-B."""
    creds_a = provision_persona("data_engineer")
    creds_b = provision_persona("data_engineer", tenant_slug="tenant-b")

    resp = api_post("/contracts/", creds_a, json={
        "name": f"xtn-contract-{fresh_id('c')}",
    })
    if resp.status_code not in (200, 201):
        pytest.skip("Could not create contract in tenant A")

    contract_id = resp.json().get("id")
    resp_b = api_get(f"/contracts/{contract_id}/", creds_b)
    assert resp_b.status_code in (403, 404), (
        f"Tenant B saw tenant A's contract {contract_id}: status {resp_b.status_code}"
    )
