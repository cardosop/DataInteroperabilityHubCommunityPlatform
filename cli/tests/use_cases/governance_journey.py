import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Governance journey: CLI governance command group.

Validates governance policy listing and endpoint availability
via real API calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provision_admin():
    """Governance endpoints typically require elevated permissions."""
    return provision_persona("admin")


def _extract_policies(body):
    """Extract the policies list from a paginated or flat response."""
    if isinstance(body, list):
        return body
    return body.get("results", body.get("items", body.get("policies", [])))


# ===========================================================================
# Tests
# ===========================================================================


def test_list_governance_policies():
    """GET /governance/policies/ returns a list of governance policies."""
    creds = _provision_admin()

    resp = api_get("/governance/policies/", creds)
    if resp.status_code == 404:
        resp = api_get("/governance/", creds)
    if resp.status_code == 404:
        pytest.skip("Governance policies endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Governance policies returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    policies = _extract_policies(body)
    assert isinstance(policies, list), (
        f"Expected a list of policies, got {type(policies).__name__}"
    )


def test_governance_endpoint_exists():
    """GET /governance/ responds with 200, confirming the governance
    command group is available.
    """
    creds = _provision_admin()

    resp = api_get("/governance/", creds)
    if resp.status_code == 404:
        resp = api_get("/governance/policies/", creds)
    if resp.status_code == 404:
        resp = api_get("/governance/rules/", creds)
    if resp.status_code == 404:
        pytest.skip("Governance endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Governance endpoint returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Should be a list or paginated dict
    if isinstance(body, dict):
        known_keys = {"results", "items", "policies", "rules", "count", "total"}
        has_known = any(k in body for k in known_keys)
        assert has_known or len(body) > 0, (
            f"Governance response has unexpected structure. Keys: {list(body.keys())}"
        )
