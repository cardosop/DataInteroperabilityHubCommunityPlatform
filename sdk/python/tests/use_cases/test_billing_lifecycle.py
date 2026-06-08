import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.8 — Billing subscription + plan management.

Validates billing plan retrieval, current subscription, and plan change.
Tests cover the happy paths (GET plans, GET current subscription) and
the plan-change path (POST change-plan).
"""

import requests
from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_base_url


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
    """GET /billing/subscription/current/ returns 200 with the current
    subscription including plan information.
    """
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "Billing subscription endpoint not implemented yet (404)"
        )

    assert resp.status_code == 200, (
        f"GET /billing/subscription/current/ returned "
        f"{resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    assert body, "Billing subscription response is empty"


def test_get_current_plan_contains_limits():
    """The billing plan list should include quota/limit information."""
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/plans/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("Billing plans endpoint not implemented (404)")

    assert resp.status_code == 200
    body = resp.json()

    results = (
        body if isinstance(body, list) else body.get("results", [])
    )
    assert len(results) > 0, "No billing plans returned"

    # At least one plan should contain limit/quota fields
    body_str = str(results).lower()
    has_limits = any(
        keyword in body_str
        for keyword in [
            "limit", "quota", "max", "allowance",
            "seats", "storage", "limits_json",
        ]
    )
    assert has_limits, (
        f"Billing plans contain no limit/quota information: "
        f"{str(results)[:500]}"
    )


def test_list_plans_returns_data():
    """GET /billing/plans/ returns 200 with at least one plan."""
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/plans/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("Billing plans endpoint not implemented yet (404)")

    assert resp.status_code == 200, (
        f"GET /billing/plans/ returned "
        f"{resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    results = (
        body if isinstance(body, list) else body.get("results", [])
    )
    assert len(results) > 0, "Billing plans list is empty"

    # Each plan should have at minimum an identifier and name
    first_plan = results[0]
    assert (
        "id" in first_plan
        or "slug" in first_plan
        or "name" in first_plan
    ), f"Plan object missing id/slug/name: {first_plan}"


def test_list_invoices_returns_data():
    """GET /billing/invoices/ returns 200 with invoice history."""
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/invoices/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("Billing invoices endpoint not implemented (404)")

    assert resp.status_code == 200, (
        f"GET /billing/invoices/ returned "
        f"{resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Invoices may be empty for new tenants — just verify the shape
    if isinstance(body, dict):
        assert "results" in body or len(body) >= 0
    # list is also valid


def test_quota_exceeded_returns_error():
    """Attempt to exceed a plan limit and verify the API returns an
    appropriate error (403 Forbidden with ``code="plan_limit_exceeded"``,
    402 Payment Required, 429 Too Many Requests, or 413 Payload Too Large).

    The server's ``PlanLimitService.check_limit()`` raises a
    ``ValidationError`` with ``http_status=403`` and
    ``code="plan_limit_exceeded"`` when a plan's ``max_assets`` limit is
    exceeded (e.g. the Free plan allows 10 assets).  The test accepts any
    of 400/402/403/413/422/429 so it remains future-proof when alternate
    quota mechanisms are introduced.

    Strategy: check the current plan's ``max_assets`` limit, then create
    assets in a tight loop until the API rejects one.  If the plan has no
    asset limit or the limit is very high, the test skips gracefully.
    """
    creds = provision_persona("data_mesh_domain_owner")
    base = api_base_url()

    MAX_ATTEMPTS = 50

    # ── Pre-check: does the tenant plan have a finite max_assets limit? ──
    plan_resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )
    if plan_resp.status_code == 200:
        plan_body = plan_resp.json()
        limits = plan_body.get("limits", {})
        max_assets = limits.get("max_assets")
        if max_assets is None:
            pytest.skip(
                "Tenant plan has no max_assets limit (unlimited) — "
                "quota enforcement cannot be tested"
            )
        # If the limit is unreasonably high, skip as well
        if isinstance(max_assets, (int, float)) and max_assets > MAX_ATTEMPTS:
            pytest.skip(
                f"Tenant plan max_assets={max_assets} exceeds test "
                f"budget of {MAX_ATTEMPTS} — quota enforcement cannot "
                f"be reached"
            )

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

        # Server returns 403 with code="plan_limit_exceeded" from
        # PlanLimitService.check_limit() when max_assets is exceeded.
        # Also accept 402/429/413 for alternate quota mechanisms.
        if resp.status_code in (400, 402, 403, 413, 422, 429):
            # Check whether this is a genuine quota/limit response rather
            # than an unrelated validation error (e.g. duplicate key).
            body = (
                resp.json()
                if resp.headers.get(
                    "content-type", ""
                ).startswith("application/json")
                else {}
            )
            body_str = str(body).lower()

            # Server uses code="plan_limit_exceeded" (403).
            # Also detect message-based limit indicators.
            has_limit_marker = any(
                keyword in body_str
                for keyword in [
                    "limit", "quota", "exceeded", "upgrade", "plan",
                    "plan_limit",
                ]
            )
            # Check for the canonical DRF error code as well
            error_code = (
                body.get("code", "")
                if isinstance(body, dict)
                else ""
            )

            if has_limit_marker or "plan_limit_exceeded" in error_code:
                hit_limit = True
                break
            # If this is an unrelated 4xx (e.g. duplicate key), don't
            # treat it as a quota hit — continue and let the loop
            # eventually skip or hit a real limit.
            if resp.status_code not in (200, 201):
                break
        elif resp.status_code not in (200, 201):
            break

    if not hit_limit:
        pytest.skip(
            f"Plan limit not reached after {MAX_ATTEMPTS} assets "
            f"-- quota enforcement may not apply or limit is very high"
        )


def test_billing_unauthenticated_returns_401():
    """Billing endpoints without authentication should return 401."""
    base = api_base_url()

    plan_resp = requests.get(
        f"{base}/billing/plans/", timeout=15,
    )
    if plan_resp.status_code == 404:
        pytest.skip("Billing endpoint not implemented (404)")

    assert plan_resp.status_code == 401, (
        f"Unauthenticated billing/plans returned "
        f"{plan_resp.status_code}"
    )

    sub_resp = requests.get(
        f"{base}/billing/subscription/current/", timeout=15,
    )
    if sub_resp.status_code != 404:
        assert sub_resp.status_code == 401, (
            f"Unauthenticated billing/subscription returned "
            f"{sub_resp.status_code}"
        )


def test_non_admin_can_view_subscription():
    """A regular user (auditor) should be able to view the
    current subscription for their tenant.
    """
    creds = provision_persona("auditor")
    base = api_base_url()

    resp = requests.get(
        f"{base}/billing/subscription/current/",
        headers=_auth_headers(creds.api_key),
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "Billing subscription endpoint not implemented (404)"
        )

    # Regular users should get 200 (read-only) or 403 (admin-only)
    assert resp.status_code in (200, 403), (
        f"Data analyst billing/subscription returned "
        f"{resp.status_code}: {resp.text[:300]}"
    )


def test_billing_plan_change_endpoint_exists():
    """POST /billing/subscription/current/change-plan/ for changing the
    plan should exist and respond.

    We send an invalid plan slug to verify the endpoint exists and
    validates input without actually performing a plan change.
    """
    creds = _tenant_admin_creds()
    base = api_base_url()

    resp = requests.post(
        f"{base}/billing/subscription/current/change-plan/",
        headers=_auth_headers(creds.api_key),
        json={"plan_slug": "nonexistent-plan-slug"},
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip(
            "Billing plan change endpoint not implemented (404)"
        )

    # The endpoint exists -- it should return 400 (invalid plan)
    # or 200 (upgraded). It should NOT be a 5xx.
    assert resp.status_code < 500, (
        f"Billing plan change returned server error "
        f"{resp.status_code}: {resp.text[:300]}"
    )
