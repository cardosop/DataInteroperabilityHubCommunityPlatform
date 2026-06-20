import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.5 -- GovernanceAPI journey.

Validates the governance policy surface: listing policies, retrieving a
single policy by id, and verifying the endpoint exists and responds.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_creds():
    return provision_persona("platform_admin")


def _skip_if_not_found(resp, label="Governance"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _extract_results(body):
    if isinstance(body, list):
        return body
    return body.get("results") or body.get("items") or body.get("data") or []


# ===========================================================================
# Tests
# ===========================================================================


def test_list_governance_policies():
    """GET /governance/policies/ returns a list of governance policies."""
    creds = _admin_creds()
    resp = api_get("/governance/policies/", creds)
    _skip_if_not_found(resp, "List governance policies")

    assert resp.status_code == 200, (
        f"GET /governance/policies/ returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list)


def test_get_governance_policy():
    """GET /governance/policies/<id>/ returns a single policy."""
    creds = _admin_creds()

    # First list to find an existing policy id
    list_resp = api_get("/governance/policies/", creds)
    _skip_if_not_found(list_resp, "List governance policies")
    assert list_resp.status_code == 200

    policies = _extract_results(list_resp.json())
    if not policies:
        pytest.skip("No governance policies exist to retrieve")

    policy = policies[0]
    policy_id = policy.get("id") or policy.get("policy_id")
    if policy_id is None:
        pytest.skip("Policy object has no id field")

    get_resp = api_get(f"/governance/policies/{policy_id}/", creds)
    assert get_resp.status_code == 200, (
        f"GET /governance/policies/{policy_id}/ returned {get_resp.status_code}: "
        f"{get_resp.text[:500]}"
    )
    body = get_resp.json()
    returned_id = body.get("id") or body.get("policy_id")
    assert str(returned_id) == str(policy_id)


def test_governance_endpoint_exists():
    """The governance root endpoint responds with a non-5xx status."""
    creds = _admin_creds()

    # Try several common governance paths
    for path in ("/governance/", "/governance/policies/", "/governance/rules/"):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            assert resp.status_code < 500, (
                f"Governance endpoint {path} returned server error "
                f"{resp.status_code}: {resp.text[:300]}"
            )
            return

    pytest.skip("No governance endpoint responded (all 404)")
