import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.8 -- ObservabilityAPI journey.

Validates the observability surface: health check endpoint, metrics
endpoint, and verifying the health response contains an OK status.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_creds():
    return provision_persona("platform_admin")


def _skip_if_not_found(resp, label="Observability"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


# ===========================================================================
# Tests
# ===========================================================================


def test_health_endpoint():
    """GET /health/ returns 200."""
    creds = _admin_creds()

    for path in ("/health/", "/healthz/", "/health"):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            assert resp.status_code == 200, (
                f"Health endpoint {path} returned {resp.status_code}: "
                f"{resp.text[:500]}"
            )
            return

    pytest.skip("No health endpoint responded (all 404)")


def test_metrics_endpoint():
    """GET /metrics/ (or /observability/metrics/) returns data."""
    creds = _admin_creds()

    for path in ("/metrics/", "/observability/metrics/", "/metrics"):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            assert resp.status_code in (200, 204), (
                f"Metrics endpoint {path} returned {resp.status_code}: "
                f"{resp.text[:500]}"
            )
            return

    pytest.skip("No metrics endpoint responded (all 404)")


def test_health_returns_ok():
    """Health response body should indicate a healthy status."""
    creds = _admin_creds()

    resp = None
    for path in ("/health/", "/healthz/", "/health"):
        candidate = api_get(path, creds)
        if candidate.status_code == 200:
            resp = candidate
            break

    if resp is None:
        pytest.skip("No health endpoint returned 200")

    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

    if isinstance(body, dict):
        body_str = str(body).lower()
        assert any(
            keyword in body_str
            for keyword in ("ok", "healthy", "up", "pass", "alive")
        ), f"Health response does not indicate OK status: {body}"
    # Plain-text "ok" is also acceptable
    elif resp.text.strip().lower() in ("ok", "healthy", "alive"):
        pass
    else:
        pytest.fail(f"Unexpected health response format: {resp.text[:300]}")
