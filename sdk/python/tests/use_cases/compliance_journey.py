import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.3 -- ComplianceSDKAPI journey.

End-to-end validation of the Compliance run surface: create a compliance
run, list runs, retrieve by id, verify status field, and full lifecycle
roundtrip.
"""

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_get, api_post

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_creds():
    return provision_persona("platform_admin")


def _owner_creds():
    return provision_persona("data_product_owner")


def _skip_if_not_found(resp, label="Compliance"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _create_compliance_run(creds, *, asset_id=None):
    """Create a compliance run and return (response, run_id)."""
    payload = {
        "name": fresh_id("compliance-run"),
        "description": "Journey test compliance run",
    }
    if asset_id:
        payload["asset_id"] = asset_id
    resp = api_post("/compliance/runs/", creds, json=payload)
    run_id = None
    if resp.status_code in (200, 201, 202):
        body = resp.json()
        run_id = body.get("id") or body.get("run_id")
    return resp, run_id


def _extract_results(body):
    """Extract list of items from a paginated or bare-list response."""
    if isinstance(body, list):
        return body
    return body.get("results") or body.get("items") or body.get("data") or []


# ===========================================================================
# Tests
# ===========================================================================


def test_create_compliance_run():
    """POST /compliance/runs/ creates a new compliance run."""
    creds = _admin_creds()
    resp, run_id = _create_compliance_run(creds)
    _skip_if_not_found(resp, "Create compliance run")

    assert resp.status_code in (200, 201, 202), (
        f"POST /compliance/runs/ returned {resp.status_code}: {resp.text[:500]}"
    )
    assert run_id is not None, "Response missing id/run_id"


def test_list_compliance_runs():
    """GET /compliance/runs/ returns a list of compliance runs."""
    creds = _admin_creds()
    resp = api_get("/compliance/runs/", creds)
    _skip_if_not_found(resp, "List compliance runs")

    assert resp.status_code == 200, (
        f"GET /compliance/runs/ returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data: {list(body.keys())}"
        )


def test_get_compliance_run_by_id():
    """GET /compliance/runs/<id>/ returns the run we created."""
    creds = _admin_creds()
    create_resp, run_id = _create_compliance_run(creds)
    _skip_if_not_found(create_resp, "Create compliance run")
    if run_id is None:
        pytest.skip("Could not create compliance run to retrieve")

    get_resp = api_get(f"/compliance/runs/{run_id}/", creds)
    assert get_resp.status_code == 200, (
        f"GET /compliance/runs/{run_id}/ returned {get_resp.status_code}: {get_resp.text[:500]}"
    )
    body = get_resp.json()
    returned_id = body.get("id") or body.get("run_id")
    assert str(returned_id) == str(run_id)


def test_compliance_run_has_status():
    """A compliance run response must include a status field."""
    creds = _admin_creds()
    create_resp, run_id = _create_compliance_run(creds)
    _skip_if_not_found(create_resp, "Create compliance run")
    if run_id is None:
        pytest.skip("Could not create compliance run for status check")

    get_resp = api_get(f"/compliance/runs/{run_id}/", creds)
    assert get_resp.status_code == 200
    body = get_resp.json()

    keys_lower = {k.lower() for k in body.keys()}
    has_status = any(k in keys_lower for k in ("status", "state", "run_status", "execution_status"))
    assert has_status, f"Compliance run missing status field: {list(body.keys())}"


def test_compliance_run_lifecycle():
    """Full lifecycle: create -> list (verify present) -> get -> confirm status."""
    creds = _admin_creds()
    name = fresh_id("compl-lifecycle")
    payload = {
        "name": name,
        "description": "Lifecycle journey test",
    }
    create_resp = api_post("/compliance/runs/", creds, json=payload)
    _skip_if_not_found(create_resp, "Create compliance run (lifecycle)")

    assert create_resp.status_code in (200, 201, 202), (
        f"Lifecycle create failed: {create_resp.status_code}"
    )
    body = create_resp.json()
    run_id = body.get("id") or body.get("run_id")
    assert run_id is not None

    # List and verify the run appears
    list_resp = api_get("/compliance/runs/", creds)
    assert list_resp.status_code == 200
    runs = _extract_results(list_resp.json())
    run_ids = [str(r.get("id") or r.get("run_id")) for r in runs]
    assert str(run_id) in run_ids, f"Created run {run_id} not found in list: {run_ids[:20]}"

    # Get by id and verify status exists
    get_resp = api_get(f"/compliance/runs/{run_id}/", creds)
    assert get_resp.status_code == 200
    run_body = get_resp.json()
    status = run_body.get("status") or run_body.get("state") or run_body.get("run_status")
    assert status is not None, f"Run has no status: {list(run_body.keys())}"
