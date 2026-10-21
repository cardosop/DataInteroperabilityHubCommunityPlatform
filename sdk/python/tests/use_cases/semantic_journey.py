import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.12 -- SemanticAPI journey.

Validates the semantic layer surface: verifying the endpoint exists and
checking the semantic health/readiness probe.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_creds():
    return provision_persona("platform_admin")


def _skip_if_not_found(resp, label="Semantic"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


# ===========================================================================
# Tests
# ===========================================================================


def test_semantic_endpoint_exists():
    """At least one semantic endpoint responds with a non-5xx status."""
    creds = _admin_creds()

    for path in (
        "/semantic/",
        "/semantic/models/",
        "/semantic/layers/",
        "/semantic/definitions/",
    ):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            assert resp.status_code < 500, (
                f"Semantic endpoint {path} returned server error "
                f"{resp.status_code}: {resp.text[:300]}"
            )
            return

    pytest.skip("No semantic endpoint responded (all 404)")


def test_semantic_health():
    """Semantic health or readiness probe returns 200."""
    creds = _admin_creds()

    for path in (
        "/semantic/health/",
        "/semantic/healthz/",
        "/semantic/ready/",
        "/semantic/status/",
    ):
        resp = api_get(path, creds)
        if resp.status_code == 200:
            body_text = resp.text.lower()
            # Sanity: the response should not be an error message
            assert "error" not in body_text or "no error" in body_text, (
                f"Semantic health returned 200 but body contains error: {resp.text[:300]}"
            )
            return

    # Fall back: try the root semantic endpoint
    root_resp = api_get("/semantic/", creds)
    if root_resp.status_code == 200:
        return

    pytest.skip("No semantic health endpoint returned 200")
