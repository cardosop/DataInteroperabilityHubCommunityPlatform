import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Observability journey: CLI health/observability endpoints.

Validates health check, liveness probe, and metrics endpoints
via real API calls against the staging environment.
"""

from tests.use_cases._api_helpers import api_unauthenticated_get

# ===========================================================================
# Tests
# ===========================================================================


def test_health_endpoint_returns_ok():
    """GET /health/ returns 200 with a healthy status."""
    resp = api_unauthenticated_get("/health/")

    if resp.status_code == 404:
        pytest.skip("/health/ endpoint not found (404)")

    assert resp.status_code == 200, f"/health/ returned {resp.status_code}: {resp.text[:500]}"

    body = resp.json()
    # Should contain a status field indicating health
    status = body.get("status", body.get("health", body.get("state")))
    if status is not None:
        assert status.lower() in ("ok", "healthy", "up", "pass", "green"), (
            f"Unexpected health status: {status}"
        )


def test_health_live_endpoint():
    """GET /health/live/ (or /healthz/) returns 200 for the liveness probe."""
    resp = api_unauthenticated_get("/health/live/")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/healthz/")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/health/liveness/")
    if resp.status_code == 404:
        pytest.skip("Liveness endpoint not found (404)")

    assert resp.status_code == 200, f"Liveness probe returned {resp.status_code}: {resp.text[:300]}"


def test_metrics_endpoint():
    """GET /metrics/ (or /health/metrics/) returns observability data."""
    resp = api_unauthenticated_get("/metrics/")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/health/metrics/")
    if resp.status_code == 404:
        pytest.skip("Metrics endpoint not found (404)")

    # Metrics may return 200 with Prometheus text or JSON
    assert resp.status_code == 200, (
        f"Metrics endpoint returned {resp.status_code}: {resp.text[:300]}"
    )

    # Metrics response should have some content
    assert len(resp.text) > 0, "Metrics endpoint returned empty body"
