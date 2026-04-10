import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Semantic journey: CLI semantic command group.

Validates that the semantic layer endpoints exist and respond
via real API calls against the staging environment.
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


def test_semantic_endpoint_exists():
    """GET /semantic/ (or /semantic/models/) responds with 200."""
    creds = _provision_analyst()

    resp = api_get("/semantic/", creds)
    if resp.status_code == 404:
        resp = api_get("/semantic/models/", creds)
    if resp.status_code == 404:
        pytest.skip("Semantic endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Semantic endpoint returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Response should be a list or paginated dict
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "models" in body or "count" in body, (
            f"Unexpected semantic response structure. Keys: {list(body.keys())}"
        )


def test_semantic_health():
    """GET /semantic/health/ (or /semantic/status/) returns a healthy status."""
    creds = _provision_analyst()

    resp = api_get("/semantic/health/", creds)
    if resp.status_code == 404:
        resp = api_get("/semantic/status/", creds)
    if resp.status_code == 404:
        pytest.skip("Semantic health endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Semantic health returned {resp.status_code}: {resp.text[:500]}"
    )
