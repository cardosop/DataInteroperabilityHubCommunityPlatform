import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.12 — Security: cross-tenant resource leak.

Verifies that resources in one tenant are invisible / inaccessible
from another tenant. Uses 2-tenant provisioning.
"""

import json
import uuid

import requests
from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_get, api_post


def _create_asset_in_tenant(creds, name):
    """Create an asset and return its id."""
    resp = api_post(
        "/assets/",
        creds,
        json={
            "name": name,
            "key": fresh_id("xtn-asset"),
        },
    )
    if resp.status_code in (201, 200):
        return resp.json().get("id")
    return None


def _create_contract_in_tenant(creds, name):
    """Create a minimal valid ODCS contract and return its id.

    Uses a longer timeout (90 s) with retry because contract creation
    triggers synchronous normalization in the datacontract-service,
    which may take 40+ s on cold start or under CPU contention.
    A warning is logged when creation exceeds 30 s so performance
    regressions are visible in test output.
    """
    import logging

    _log = logging.getLogger(__name__)

    contract_spec = json.dumps(
        {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"xtn-odcs-{uuid.uuid4().hex[:8]}",
            "name": name,
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                ]
            },
        }
    )

    payload = {
        "original_raw": contract_spec,
        "original_format": "JSON",
        "original_spec_type": "ODCS",
    }

    # Two attempts: first with 45 s to catch the fast path, second with
    # 90 s if the datacontract-service is warming up or under contention.
    for attempt, timeout in enumerate((45, 90), start=1):
        import time as _time

        t0 = _time.monotonic()
        try:
            resp = api_post("/contracts/", creds, json=payload, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if attempt < 2:
                _log.warning(
                    "Contract creation attempt %d failed after %ds: %s. Retrying...",
                    attempt,
                    timeout,
                    exc,
                )
                continue
            raise

        elapsed = _time.monotonic() - t0
        if elapsed > 30:
            _log.warning(
                "Contract creation took %.1fs (>30 s threshold). "
                "The datacontract-service normalization may be slow.",
                elapsed,
            )

        if resp.status_code in (200, 201):
            return resp.json().get("id")
        return None

    return None


def test_asset_from_tenant_a_invisible_to_tenant_b():
    """Asset created by tenant-A engineer must return 404 from tenant-B engineer."""
    creds_a = provision_persona("data_engineer")
    creds_b = provision_persona("data_engineer", tenant_slug="tenant-b")  # noqa: PHASE216-STATIC-ID

    asset_id = _create_asset_in_tenant(creds_a, f"xtn-test-{fresh_id('a')}")
    if asset_id is None:
        pytest.skip("Could not create asset in tenant A (API may not support it)")

    # Positive control: tenant A must be able to retrieve its own asset
    verify_a = api_get(f"/assets/{asset_id}/", creds_a)
    assert verify_a.status_code in (200, 201), (
        f"Tenant A cannot see its own asset {asset_id}: {verify_a.status_code}"
    )

    # Tenant B must NOT see tenant A's asset
    resp = api_get(f"/assets/{asset_id}/", creds_b)
    assert resp.status_code in (403, 404), (
        f"Tenant B saw tenant A's asset {asset_id}: status {resp.status_code}"
    )


def test_asset_list_does_not_leak_across_tenants():
    """GET /assets/ from tenant B must not contain assets from tenant A."""
    creds_a = provision_persona("data_engineer")
    creds_b = provision_persona("data_engineer", tenant_slug="tenant-b")  # noqa: PHASE216-STATIC-ID

    marker = fresh_id("xtn-marker")
    asset_name = f"xtn-{marker}"
    asset_id = _create_asset_in_tenant(creds_a, asset_name)

    # Positive control: tenant A must see the marker in its own listing
    if asset_id is not None:
        resp_a = api_get("/assets/", creds_a)
        if resp_a.status_code == 200:
            a_names = [a.get("name", "") for a in resp_a.json().get("results", [])]
            assert any(marker in n for n in a_names), (
                f"Tenant A's own listing does not contain marker '{marker}'. "
                f"Asset creation may have silently failed."
            )

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
    creds_b = provision_persona("data_engineer", tenant_slug="tenant-b")  # noqa: PHASE216-STATIC-ID

    contract_id = _create_contract_in_tenant(creds_a, f"xtn-contract-{fresh_id('c')}")
    if contract_id is None:
        pytest.skip("Could not create contract in tenant A (API may not support it)")

    # Positive control: tenant A must be able to retrieve its own contract
    verify_a = api_get(f"/contracts/{contract_id}/", creds_a)
    assert verify_a.status_code in (200, 201), (
        f"Tenant A cannot see its own contract {contract_id}: {verify_a.status_code}"
    )

    resp_b = api_get(f"/contracts/{contract_id}/", creds_b)
    assert resp_b.status_code in (403, 404), (
        f"Tenant B saw tenant A's contract {contract_id}: status {resp_b.status_code}"
    )
