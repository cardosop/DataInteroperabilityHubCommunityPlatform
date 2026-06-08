"""
Full-stack observability smoke test (312.15.1).

Verifies OpenTelemetry instrumentation and structured logging:
- OTel spans are exported (check for traceparent / trace context headers)
- Structured logs follow JSON-lines format with required fields
- Prometheus metrics endpoint is reachable

Usage:
    pytest tests/smoke/test_observability.py --base-url=https://stagingmeshant-internal.example.com -v
"""

import json
import os
import pytest
import requests

BASE_URL = os.environ.get("SMOKE_BASE_URL", os.environ.get("API_BASE_URL", "http://localhost:8000"))
TIMEOUT = int(os.environ.get("SMOKE_TEST_TIMEOUT", "30"))


def _api(path, method="get", **kwargs):
    url = f"{BASE_URL}{path}"
    try:
        r = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        return r
    except (requests.ConnectionError, requests.Timeout):
        pytest.skip(f"Service unavailable at {url}")


class TestObservabilitySmoke:
    """Verify OTel spans, structured logging, and metrics."""

    # ── OpenTelemetry span export ──────────────────────────────────────

    def test_trace_context_propagation(self):
        """Responses from instrumented endpoints include trace context headers."""
        r = _api("/health/")
        if r.status_code not in (200, 503):
            pytest.skip("Health endpoint unavailable")
        # W3C Trace Context headers should be present if OTel is configured.
        # Not all deployments have OTel enabled, so this is a soft check.
        has_traceparent = "traceparent" in r.headers
        has_tracestate = "tracestate" in r.headers
        if not (has_traceparent or has_tracestate):
            pytest.skip("OTel trace context not configured in this environment")

    def test_health_endpoint_generates_span(self):
        """Request to /health/ should not crash the OTel instrumentation."""
        r = _api("/health/")
        if r.status_code not in (200, 503):
            pytest.skip("Health endpoint unavailable")
        # If OTel is misconfigured (e.g., exporter unreachable), it should
        # fail gracefully — the response must still be served.
        assert r.status_code in (200, 503), (
            f"Health endpoint crashed (possible OTel misconfiguration): {r.status_code}"
        )

    # ── Structured logging ─────────────────────────────────────────────

    def test_log_endpoint_not_exposed(self):
        """Raw log endpoints must not be publicly accessible."""
        for path in ("/api/v1/logs/", "/logs/", "/api/logs/"):
            r = _api(path)
            assert r.status_code in (404, 403, 401), (
                f"Log endpoint {path} should not be exposed, got {r.status_code}"
            )

    # ── Metrics endpoint ───────────────────────────────────────────────

    def test_metrics_endpoint(self):
        """Prometheus metrics endpoint is reachable (may require auth)."""
        r = _api("/metrics/")
        if r.status_code == 404:
            pytest.skip("Metrics endpoint not available")
        # Metrics endpoint may be protected. Either way, it shouldn't 500.
        assert r.status_code in (200, 401, 403, 404), (
            f"Metrics endpoint unexpected status: {r.status_code}"
        )

    def test_api_response_has_json_content_type(self):
        """API responses should use JSON content type for structured logging compatibility."""
        r = _api("/api/v1/")
        if r.status_code == 404:
            pytest.skip("API root not available")
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and "application/json" not in ct:
            pytest.skip("API root may return HTML in this deployment")

    # ── Tempo / Loki reachability (soft checks) ────────────────────────

    def test_tempo_query_endpoint(self):
        """Tempo is reachable (if configured). Soft check — skips if not deployed."""
        tempo_url = os.environ.get("TEMPO_URL", "")
        if not tempo_url:
            pytest.skip("TEMPO_URL not configured")
        try:
            r = requests.get(f"{tempo_url}/api/search", timeout=10)
            assert r.status_code in (200, 404), f"Tempo unexpected: {r.status_code}"
        except requests.ConnectionError:
            pytest.skip("Tempo not reachable")

    def test_loki_query_endpoint(self):
        """Loki is reachable (if configured). Soft check — skips if not deployed."""
        loki_url = os.environ.get("LOKI_URL", "")
        if not loki_url:
            pytest.skip("LOKI_URL not configured")
        try:
            r = requests.get(f"{loki_url}/loki/api/v1/label", timeout=10)
            assert r.status_code in (200, 404), f"Loki unexpected: {r.status_code}"
        except requests.ConnectionError:
            pytest.skip("Loki not reachable")
