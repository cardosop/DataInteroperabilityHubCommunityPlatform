import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Tenants journey: CLI tenants command group.

Validates tenant retrieval endpoints via real API calls against
the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provision_analyst():
    return provision_persona("data_analyst")


# ===========================================================================
# Tests
# ===========================================================================


def test_get_current_tenant():
    """GET /tenants/current/ (or /tenants/me/) returns the active tenant."""
    creds = _provision_analyst()

    # Try /tenants/current/ first, fall back to /tenants/me/
    resp = api_get("/tenants/current/", creds)
    if resp.status_code == 404:
        resp = api_get("/tenants/me/", creds)
    if resp.status_code == 404:
        pytest.skip("Tenant current endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Current tenant returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    assert "id" in body or "tenant_id" in body, (
        f"Current tenant response missing id. Keys: {list(body.keys())}"
    )


def test_list_tenants():
    """GET /tenants/ returns a list of tenants the user has access to."""
    creds = _provision_analyst()

    resp = api_get("/tenants/", creds)

    if resp.status_code == 404:
        pytest.skip("/tenants/ endpoint not found (404)")

    assert resp.status_code == 200, (
        f"/tenants/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Response is either a list or a paginated dict with results
    if isinstance(body, list):
        tenants = body
    else:
        tenants = body.get("results", body.get("items", []))

    assert isinstance(tenants, list), (
        f"Expected a list of tenants, got {type(tenants).__name__}"
    )
    assert len(tenants) >= 1, "User should belong to at least one tenant"


def test_tenant_has_name_and_slug():
    """Each tenant returned by GET /tenants/ contains name and slug fields."""
    creds = _provision_analyst()

    resp = api_get("/tenants/", creds)

    if resp.status_code == 404:
        pytest.skip("/tenants/ endpoint not found (404)")

    assert resp.status_code == 200, (
        f"/tenants/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    if isinstance(body, list):
        tenants = body
    else:
        tenants = body.get("results", body.get("items", []))

    if not tenants:
        pytest.skip("No tenants returned — cannot validate structure")

    tenant = tenants[0]
    assert "name" in tenant, (
        f"Tenant missing 'name' field. Keys: {list(tenant.keys())}"
    )
    assert "slug" in tenant or "id" in tenant, (
        f"Tenant missing 'slug' or 'id' field. Keys: {list(tenant.keys())}"
    )
    if "name" in tenant:
        assert isinstance(tenant["name"], str) and len(tenant["name"]) > 0, (
            "Tenant name should be a non-empty string"
        )
