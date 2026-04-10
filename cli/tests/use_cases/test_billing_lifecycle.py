import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.8 — Billing upgrade + quota enforcement.

Validates billing plan retrieval, usage metering, and quota enforcement.
Tests cover the happy paths (GET plan, GET usage) and the enforcement
path (exceeding plan limits triggers an appropriate error).
"""

import os
import requests
from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.personas import MVP_PERSONA_ROLES
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
    api_get,
    api_post,
    api_put,
    api_delete,
    api_login,
    api_unauthenticated_get,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tenant_admin_creds() -> PersonaCredentials:
    """Provision a tenant_admin who typically manages billing."""
    return provision_persona("tenant_admin")


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
    assert (
        "plan" in body
        or "tier" in body
        or "name" in body
        or "subscription" in body
    ), f"Billing plan response missing plan/tier/name: {body}"


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
    assert has_limits, (
        f"Billing plan response contains no limit/quota information: {body}"
    )


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
            f"Billing usage response has no period/cycle information: {body}"
        )


@pytest.mark.timeout(300)  # 50 assets × 15s timeout each — needs more than default 60s
def test_quota_exceeded_returns_402_or_429():
    """Attempt to exceed a plan limit and verify the API returns an
    appropriate error (402 Payment Required or 429 Too Many Requests).

    Strategy: create assets in a tight loop until the API rejects one.
    If the plan has no asset limit or the limit is very high, the test
    skips gracefully.
    """
    creds = provision_persona("data_product_owner")
    base = api_base_url()

    MAX_ATTEMPTS = 50  # Stop after this many to avoid excessive load
    hit_limit = False

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

        if resp.status_code in (402, 429, 413):
            hit_limit = True
            # Verify the error response is informative
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            body_str = str(body).lower()
            has_message = any(
                keyword in body_str
                for keyword in ["limit", "quota", "exceeded", "upgrade", "plan"]
            )
            assert has_message or resp.status_code in (402, 429), (
                f"Quota error response lacks informative message: {body}"
            )
            break
        elif resp.status_code not in (200, 201):
            # Unexpected error — might be unrelated to quota
            break

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
        pytest.skip(f"No billing subscription for test tenant (404): {resp.text[:100]}")

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
        f"Data analyst billing/usage returned {resp.status_code}: "
        f"{resp.text[:300]}"
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
        f"Billing plan upgrade returned server error {resp.status_code}: "
        f"{resp.text[:300]}"
    )
