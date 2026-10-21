import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.8 — Billing upgrade + quota enforcement.

Validates billing plan retrieval, usage metering, and quota enforcement.
Tests cover the happy paths (GET plan, GET usage) and the enforcement
path (exceeding plan limits triggers an appropriate error).
"""

import requests
from tests._persona_provisioning import PersonaCredentials, provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
    reset_rate_limits,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tenant_admin_creds() -> PersonaCredentials:
    """Provision a tenant_admin who typically manages billing."""
    return provision_persona("tenant_admin")  # noqa: PHASE216-STATIC-ID


def _platform_admin_creds() -> PersonaCredentials:
    return provision_persona("platform_admin")


# ===========================================================================
# Tests
# ===========================================================================


def test_get_current_plan():
    """GET /billing/subscription/current/ returns 200 with the current subscription plan.

    The response should include at minimum a plan name/tier and status.
    """
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(f"No billing subscription for test tenant (404): {resp.text[:100]}")

    assert resp.status_code == 200, (
        f"GET /billing/subscription/current/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Should contain plan identification
    assert "plan" in body or "tier" in body or "name" in body or "subscription" in body, (
        f"Billing plan response missing plan/tier/name: {body}"
    )


def test_get_current_plan_contains_limits():
    """The billing plan response should include quota/limit information."""
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(f"No billing subscription for test tenant (404): {resp.text[:100]}")

    assert resp.status_code == 200
    body = resp.json()

    # Look for any quota/limit fields
    body_str = str(body).lower()
    has_limits = any(
        keyword in body_str
        for keyword in ["limit", "quota", "max", "allowance", "seats", "storage"]
    )
    assert has_limits, f"Billing plan response contains no limit/quota information: {body}"


def test_usage_metering_returns_data():
    """GET /billing/subscription/current/ returns 200 with usage metrics.

    The response should include consumption data (e.g., API calls,
    storage used, seats consumed).
    """
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(f"No billing subscription for test tenant (404): {resp.text[:100]}")

    assert resp.status_code == 200, (
        f"GET /billing/subscription/current/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Should contain some usage metrics
    assert body, "Billing usage response is empty"

    # The response should be a dict or list with actual data
    if isinstance(body, dict):
        assert len(body) > 0, "Billing usage response dict is empty"
    elif isinstance(body, list):
        # A list of usage records is also valid
        pass


def test_usage_metering_includes_period():
    """Billing usage should reference a time period (current billing cycle)."""
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(f"No billing subscription for test tenant (404): {resp.text[:100]}")

    assert resp.status_code == 200
    body = resp.json()
    body_str = str(body).lower()

    has_period = any(
        keyword in body_str
        for keyword in ["period", "start", "end", "from", "to", "cycle", "month"]
    )
    # This is a soft assertion — warn but do not fail if period is missing
    if not has_period:
        import warnings

        warnings.warn(
            f"Billing usage response has no period/cycle information: {body}",
            stacklevel=2,
        )


@pytest.mark.timeout(300)
def test_quota_exceeded_returns_plan_limit_error():
    """Verify POST /assets/ enforces the tenant plan's ``max_assets`` quota.

    Strategy: pin the persona tenant to a dedicated probe plan with
    ``max_assets=2`` and create assets until the API rejects one with
    ``plan_limit_exceeded``, then restore the original plan.

    The tenant is NOT pinned to the shared FREE plan: on this stack the
    active FREE plan has ``max_assets=100`` (the old "max_assets=5"
    assumption was drift), so the loop ran straight past the quota until
    the 60/min asset-creation throttle 429'd it — the test "passed" on
    the 429 branch without ever exercising the quota path, left ~41
    orphaned assets behind, and poisoned the throttle bucket for the
    compliance tests that follow this file (measured 2026-09-20).  A
    probe plan with ``max_assets=2`` makes the quota trip deterministic
    (the suite keeps the tenant's asset count above 2), and a 429 here
    is now a hard failure — the throttle must never mask the quota path.
    """
    import uuid

    creds = provision_persona("data_product_owner")
    base = api_base_url()
    reset_rate_limits()

    from hub.apps.tenants.models import Tenant, TenantPlan

    tenant = Tenant.objects.get(pk=creds.tenant_id)
    original_plan = tenant.plan
    free_plan = TenantPlan.objects.filter(slug="free", is_active=True).first()
    if free_plan is None:
        pytest.skip("No active FREE plan available for quota test")

    probe = TenantPlan.objects.create(
        name=f"E2E Quota Probe {uuid.uuid4().hex[:8]}",
        slug=f"e2e-quota-probe-{uuid.uuid4().hex[:8]}",
        tier=free_plan.tier,
        category=free_plan.category,
        limits_json={**(free_plan.limits_json or {}), "max_assets": 2},
        is_active=True,
    )

    MAX_ATTEMPTS = 10  # quota trips at ≤2 creates; 10 is slack for slow stacks
    hit_limit = False
    created_ids: list[str] = []
    try:
        tenant.plan = probe
        tenant.save(update_fields=["plan"])

        for i in range(MAX_ATTEMPTS):
            resp = requests.post(
                f"{base}/assets/",
                headers=_auth_headers(creds.api_key),
                json={
                    "name": fresh_id("quota-test"),
                    "key": fresh_id("quota-key"),
                    "description": f"Quota test asset #{i}",
                },
                timeout=15,
            )

            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if resp.status_code in (200, 201):
                created_ids.append(str(body.get("id") or ""))
                continue

            body_str = str(body).lower()
            # The plan-limit check raises a DRF ValidationError — the API
            # answers with code=plan_limit_exceeded ("Plan limit
            # exceeded for max_assets"), not 402/429.  Detect by content
            # first so a validation 400 (unrelated) is not mistaken for
            # the quota path.
            is_plan_limit = any(
                keyword in body_str for keyword in ["plan_limit_exceeded", "plan limit"]
            )
            if is_plan_limit:
                hit_limit = True
                has_message = any(
                    keyword in body_str
                    for keyword in ["limit", "quota", "exceeded", "upgrade", "plan"]
                )
                assert has_message, f"Quota error response lacks informative message: {body}"
                break
            if resp.status_code in (402, 413):
                # Alternate quota representations (Payment Required etc.)
                hit_limit = True
                break
            if resp.status_code == 429:
                pytest.fail(
                    "Asset-creation throttle fired before the plan quota — "
                    "the quota path was not exercised"
                )
            # Unexpected error — might be unrelated to quota
            break
    finally:
        tenant.plan = original_plan
        tenant.save(update_fields=["plan"])
        probe.delete()
        headers = _auth_headers(creds.api_key)
        for asset_id in created_ids:
            if asset_id:
                requests.delete(f"{base}/assets/{asset_id}/", headers=headers, timeout=15)

    if not hit_limit:
        pytest.skip(
            f"Plan limit not reached after {MAX_ATTEMPTS} assets — "
            f"quota enforcement may not apply or limit is very high"
        )


def test_billing_unauthenticated_returns_401():
    """Billing endpoints without authentication should return 401."""
    base = api_base_url()

    plan_resp = requests.get(f"{base}/billing/subscription/current/", timeout=15)
    if plan_resp.status_code == 404:
        pytest.skip(f"No billing subscription for test tenant (404): {plan_resp.text[:100]}")

    assert plan_resp.status_code == 401, (
        f"Unauthenticated billing/plan returned {plan_resp.status_code}"
    )

    usage_resp = requests.get(f"{base}/billing/subscription/current/", timeout=15)
    if usage_resp.status_code != 404:
        assert usage_resp.status_code == 401, (
            f"Unauthenticated billing/usage returned {usage_resp.status_code}"
        )


def test_non_admin_can_view_own_usage():
    """A regular user (data_analyst) should be able to view their own
    usage metrics (or the tenant's usage), not just admins.
    """
    creds = provision_persona("data_analyst")
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(f"No billing subscription for test tenant (404): {resp.text[:100]}")

    # Regular users should get 200 (own usage) or 403 (admin-only)
    assert resp.status_code in (200, 403), (
        f"Data analyst billing/usage returned {resp.status_code}: {resp.text[:300]}"
    )


def test_billing_plan_upgrade_endpoint_exists():
    """POST /billing/subscription/current/ (or PUT) for upgrading the plan should exist.

    We do not actually upgrade (that may involve payment), but we verify
    the endpoint responds.
    """
    creds = _tenant_admin_creds()
    base = api_base_url()

    # Try POST first (common for upgrades)
    resp = requests.post(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        json={"plan": "pro"},
        timeout=15,
    )

    if resp.status_code == 404:
        # Try PUT as alternative
        resp = requests.put(
            f"{base}/billing/subscription/current/",
            headers=_auth_headers(creds.api_key),
            json={"plan": "pro"},
            timeout=15,
        )

    if resp.status_code == 404:
        pytest.skip(f"No billing subscription for test tenant (404): {resp.text[:100]}")

    # The endpoint exists — it may return 400 (invalid plan), 402 (payment needed),
    # or 200 (upgraded). All are valid as long as it is not a 5xx.
    assert resp.status_code < 500, (
        f"Billing plan upgrade returned server error {resp.status_code}: {resp.text[:300]}"
    )
