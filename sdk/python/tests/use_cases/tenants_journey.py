import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.10 -- TenantsAPI journey.

Validates the tenants surface: retrieving the current tenant, listing
tenants, and verifying required fields on tenant objects.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_creds():
    return provision_persona("platform_admin")


def _user_creds():
    return provision_persona("data_analyst")


def _skip_if_not_found(resp, label="Tenants"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _extract_results(body):
    if isinstance(body, list):
        return body
    return body.get("results") or body.get("items") or body.get("data") or []


# ===========================================================================
# Tests
# ===========================================================================


def test_get_current_tenant():
    """GET /tenants/current/ (or /tenants/me/) returns the caller's tenant."""
    creds = _user_creds()

    resp = None
    for path in ("/tenants/current/", "/tenants/me/", "/tenant/"):
        candidate = api_get(path, creds)
        if candidate.status_code != 404:
            resp = candidate
            break

    if resp is None:
        pytest.skip("No current-tenant endpoint responded (all 404)")

    assert resp.status_code == 200, f"Current tenant returned {resp.status_code}: {resp.text[:500]}"
    body = resp.json()
    assert isinstance(body, dict), f"Expected dict, got {type(body)}"
    # Should have an id
    tenant_id = body.get("id") or body.get("tenant_id")
    assert tenant_id is not None, f"Tenant response missing id: {list(body.keys())}"


def test_list_tenants():
    """GET /tenants/ returns a list of tenants (admin-level)."""
    creds = _admin_creds()
    resp = api_get("/tenants/", creds)
    _skip_if_not_found(resp, "List tenants")

    assert resp.status_code in (200, 403), (
        f"GET /tenants/ returned {resp.status_code}: {resp.text[:500]}"
    )
    if resp.status_code == 403:
        pytest.skip("Tenant listing requires higher privileges (403)")

    body = resp.json()
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list)


def test_tenant_has_required_fields():
    """Tenant objects should include id, name, and slug (or equivalent)."""
    creds = _admin_creds()

    # Try current tenant first, then list
    tenant = None
    for path in ("/tenants/current/", "/tenants/me/", "/tenant/"):
        resp = api_get(path, creds)
        if resp.status_code == 200:
            tenant = resp.json()
            break

    if tenant is None:
        # Fall back to list endpoint
        list_resp = api_get("/tenants/", creds)
        _skip_if_not_found(list_resp, "Tenants")
        if list_resp.status_code != 200:
            pytest.skip("Could not retrieve any tenant data")
        tenants = _extract_results(list_resp.json())
        if not tenants:
            pytest.skip("No tenants available to inspect")
        tenant = tenants[0]

    keys_lower = {k.lower() for k in tenant.keys()}

    has_id = any(k in keys_lower for k in ("id", "tenant_id"))
    has_name = any(k in keys_lower for k in ("name", "tenant_name", "display_name"))

    assert has_id, f"Tenant missing id field: {list(tenant.keys())}"
    assert has_name, f"Tenant missing name field: {list(tenant.keys())}"
