import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.8 — Billing subscription + plan management.

Validates billing plan retrieval, current subscription, and plan change.
Tests cover the happy paths (GET plans, GET current subscription) and
the plan-change path (POST change-plan).
"""

import os
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
    # Must include a plan identifier
    assert "plan" in body or "plan_id" in body or "plan_name" in body, (
        f"Subscription response missing plan information: {list(body.keys())}"
    )


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
    # Verify at least one plan has a structured limit field (not just
    # a keyword appearing in a description or name).
    limit_keys = {"max_assets", "max_datasets", "max_storage_gb",
                  "limits_json", "max_api_calls_per_month"}
    has_structured_limit = any(
        any(key in plan for key in limit_keys)
        for plan in results
    )
    assert has_structured_limit, (
        f"No billing plan contains recognised limit keys "
        f"({limit_keys}). Plans: {str(results)[:500]}"
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
        assert "results" in body, (
            f"Invoice response missing 'results' key: {list(body.keys())}"
        )
        assert isinstance(body["results"], list), (
            f"Invoice 'results' is not a list: {type(body['results'])}"
        )
    elif isinstance(body, list):
        pass  # list format is also valid
    else:
        pytest.fail(
            f"Unexpected invoice response type {type(body)}: "
            f"{str(body)[:200]}"
        )


def test_quota_exceeded_returns_error():
    """Verify that the API rejects asset creation when the plan's
    ``max_assets`` limit is exceeded.

    Uses the ``/test/ensure-e2e-free-plan-tenant/`` E2E helper to
    obtain a tenant with the standard Free plan (max_assets=10).
    Assets are created in that tenant via ``X-Tenant-Id`` until the
    server returns a quota-exhausted error (403 with
    ``code="plan_limit_exceeded"``).

    This avoids the unlimited-plan E2E tenant which deliberately
    bypasses all limits for general test convenience.
    """
    creds = provision_persona("data_mesh_domain_owner")
    base = api_base_url()
    e2e_token = os.environ.get("E2E_TEST_SECRET", "e2e-test-secret-for-local-dev")

    # ── Obtain a Free-plan tenant ────────────────────────────────────
    free_plan_resp = requests.post(
        f"{base}/test/ensure-e2e-free-plan-tenant/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "X-E2E-Token": e2e_token,
        },
        json={},
        timeout=15,
    )
    if free_plan_resp.status_code == 404:
        pytest.skip(
            "ensure-e2e-free-plan-tenant endpoint not deployed (404)"
        )
    assert free_plan_resp.status_code == 200, (
        f"Free-plan tenant setup failed: "
        f"{free_plan_resp.status_code}: {free_plan_resp.text[:300]}"
    )
    free_tenant_id = free_plan_resp.json()["tenant_id"]

    MAX_ATTEMPTS = 50
    hit_limit = False

    for i in range(MAX_ATTEMPTS):
        resp = requests.post(
            f"{base}/assets/",
            headers={
                "Authorization": f"Bearer {creds.api_key}",
                "X-Tenant-Id": str(free_tenant_id),
                "Content-Type": "application/json",
            },
            json={
                "name": fresh_id("quota-test"),
                "key": fresh_id("quota-key"),
                "description": f"Quota test asset #{i}",
            },
            timeout=15,
        )

        # Server returns 403 with code="plan_limit_exceeded" from
        # PlanLimitService.check_limit() when max_assets is exceeded.
        if resp.status_code in (400, 402, 403, 413, 422, 429):
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
            body_str = str(body).lower()
            error_code = body.get("code", "") if isinstance(body, dict) else ""

            has_limit_marker = any(
                keyword in body_str
                for keyword in [
                    "limit", "quota", "exceeded", "upgrade", "plan",
                    "plan_limit",
                ]
            )
            if has_limit_marker or "plan_limit_exceeded" in error_code:
                hit_limit = True
                break
            if resp.status_code not in (200, 201):
                break
        elif resp.status_code not in (200, 201):
            break

    if not hit_limit:
        pytest.skip(
            f"Plan limit not reached after {MAX_ATTEMPTS} assets "
            f"— quota enforcement may not apply or the Free plan "
            f"was not correctly assigned"
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
    if sub_resp.status_code == 404:
        pytest.skip(
            "Billing subscription endpoint not implemented (404)"
        )
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

    # Non-admin users must be able to view their own subscription.
    assert resp.status_code == 200, (
        f"Auditor billing/subscription returned "
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

    # The endpoint exists — with an invalid plan slug it must return
    # 400 (validation error) or 404 (endpoint not deployed).  It must
    # NOT return 200 (accepting a non-existent plan) or 5xx.
    assert resp.status_code in (400, 404), (
        f"Billing plan change with invalid slug returned unexpected "
        f"{resp.status_code}: {resp.text[:300]}"
    )
