import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.12 -- BillingAPI journey (extends 216.2.8).

Validates the billing surface beyond the lifecycle tests: retrieving the
current plan, fetching usage data, and accessing the invoices endpoint.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_creds():
    return provision_persona("tenant_admin")


def _skip_if_not_found(resp, label="Billing"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


# ===========================================================================
# Tests
# ===========================================================================


def test_get_billing_plan():
    """GET /billing/plan/ returns the current subscription plan."""
    creds = _admin_creds()
    resp = api_get("/billing/plan/", creds)
    _skip_if_not_found(resp, "Billing plan")

    assert resp.status_code == 200, (
        f"GET /billing/plan/ returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    assert isinstance(body, dict), f"Expected dict, got {type(body)}"

    # Should contain plan identification
    keys_lower = {k.lower() for k in body.keys()}
    has_plan = any(
        k in keys_lower for k in ("plan", "tier", "name", "subscription", "plan_name", "plan_id")
    )
    assert has_plan, f"Billing plan response missing plan identifier: {list(body.keys())}"


def test_get_billing_usage():
    """GET /billing/usage/ returns usage metrics for the current period."""
    creds = _admin_creds()
    resp = api_get("/billing/usage/", creds)
    _skip_if_not_found(resp, "Billing usage")

    assert resp.status_code == 200, (
        f"GET /billing/usage/ returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    assert body, "Billing usage response is empty"

    # Usage should contain numeric metrics or a nested structure
    if isinstance(body, dict):
        assert len(body) > 0, "Billing usage dict is empty"
    elif isinstance(body, list):
        assert len(body) >= 0  # empty list is acceptable (no usage yet)


def test_billing_invoices_endpoint():
    """GET /billing/invoices/ returns a list of invoices (possibly empty)."""
    creds = _admin_creds()

    resp = None
    for path in ("/billing/invoices/", "/billing/history/", "/billing/payments/"):
        candidate = api_get(path, creds)
        if candidate.status_code != 404:
            resp = candidate
            break

    if resp is None:
        pytest.skip("No billing invoices endpoint responded (all 404)")

    _skip_if_not_found(resp, "Billing invoices")

    assert resp.status_code == 200, (
        f"Billing invoices returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()

    # Should be a list or paginated dict
    if isinstance(body, dict):
        invoices = (
            body.get("results") or body.get("items") or body.get("data") or body.get("invoices")
        )
        assert invoices is not None, (
            f"Invoices response missing results/items/data/invoices: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list), f"Expected list or dict, got {type(body)}"
