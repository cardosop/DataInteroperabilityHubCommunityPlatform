"""
Smoke test — health endpoint.

Validates the primary API liveness endpoint returns 200 with a healthy status.
This is the first gate in the post-deploy pipeline; if this fails, rollback
is triggered immediately without running the remaining smoke suites.

Endpoint contract (from Helm liveness probe configuration):
    GET /api/health/
    200 OK
    { "status": "healthy", ... }
"""

import requests


class TestHealth:
    """Verify the API is alive and reports healthy after deployment."""

    def test_api_health_returns_200(
        self, base_url: str, api_session: requests.Session, timeout: int
    ) -> None:
        """GET /api/health/ must return HTTP 200."""
        response = api_session.get(f"{base_url}/api/health/", timeout=timeout)
        assert response.status_code == 200, (
            f"Health endpoint returned {response.status_code}: {response.text[:300]}"
        )

    def test_api_health_reports_healthy(
        self, base_url: str, api_session: requests.Session, timeout: int
    ) -> None:
        """Response body must include status=healthy."""
        response = api_session.get(f"{base_url}/api/health/", timeout=timeout)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data, f"Missing 'status' key in health response: {data}"
        assert data["status"] == "healthy", (
            f"Expected status='healthy', got status='{data['status']}'"
        )

    def test_api_health_content_type_is_json(
        self, base_url: str, api_session: requests.Session, timeout: int
    ) -> None:
        """Health endpoint must return application/json."""
        response = api_session.get(f"{base_url}/api/health/", timeout=timeout)
        assert "application/json" in response.headers.get("Content-Type", ""), (
            f"Expected JSON content-type, got: {response.headers.get('Content-Type')}"
        )

    def test_api_health_response_time_under_2s(
        self, base_url: str, api_session: requests.Session, timeout: int
    ) -> None:
        """Health endpoint must respond within 2 seconds (SLO gate)."""
        response = api_session.get(f"{base_url}/api/health/", timeout=timeout)
        assert response.elapsed.total_seconds() < 2.0, (
            f"Health endpoint took {response.elapsed.total_seconds():.2f}s (SLO: <2s)"
        )
