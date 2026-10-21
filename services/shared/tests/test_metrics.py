"""
Phase 79.5 — Shared Prometheus metrics tests.

Validates that counters/histograms are registered, can be
incremented, and that get_metrics_response() returns valid
Prometheus exposition format.
"""

from prometheus_client import REGISTRY

# ── Counter / histogram registration ────────────────────────────


def test_http_requests_total_registered():
    """http_requests_total counter exists in the registry."""
    from shared.metrics import http_requests_total

    assert http_requests_total is not None
    # Must have expected label names
    assert "service" in http_requests_total._labelnames
    assert "method" in http_requests_total._labelnames


def test_http_request_duration_registered():
    """http_request_duration_seconds histogram exists."""
    from shared.metrics import (
        http_request_duration_seconds,
    )

    assert http_request_duration_seconds is not None
    assert "service" in http_request_duration_seconds._labelnames


def test_sparql_queries_total_registered():
    """sparql_queries_total counter exists (semantic service)."""
    from shared.metrics import sparql_queries_total

    assert sparql_queries_total is not None


def test_compliance_runs_total_registered():
    """compliance_runs_total counter exists."""
    from shared.metrics import compliance_runs_total

    assert compliance_runs_total is not None


# ── get_metrics_response format ─────────────────────────────────


def test_get_metrics_response_format():
    """get_metrics_response() returns (bytes, content_type) in
    Prometheus exposition format containing our registered metrics."""
    from shared.metrics import get_metrics_response

    data, content_type = get_metrics_response()
    assert isinstance(data, bytes)
    assert "text/plain" in content_type or "openmetrics" in content_type
    text = data.decode("utf-8")
    # Must contain our specific registered metric — not just any # HELP
    assert "http_requests_total" in text


# ── Counter increment ───────────────────────────────────────────


def test_shacl_violations_counter_increments():
    """shacl_violations_total can be incremented."""
    from shared.metrics import shacl_violations_total

    before = (
        REGISTRY.get_sample_value(
            "shacl_violations_total",
            {"service": "test", "severity": "warning", "shape": "x"},
        )
        or 0.0
    )
    shacl_violations_total.labels(
        service="test",
        severity="warning",
        shape="x",
    ).inc()
    after = REGISTRY.get_sample_value(
        "shacl_violations_total",
        {"service": "test", "severity": "warning", "shape": "x"},
    )
    assert after == before + 1


def test_tenant_isolation_violations_counter():
    """tenant_isolation_violations_total increments."""
    from shared.metrics import (
        tenant_isolation_violations_total,
    )

    before = (
        REGISTRY.get_sample_value(
            "tenant_isolation_violations_total",
            {"service": "test"},
        )
        or 0.0
    )
    tenant_isolation_violations_total.labels(
        service="test",
    ).inc()
    after = REGISTRY.get_sample_value(
        "tenant_isolation_violations_total",
        {"service": "test"},
    )
    assert after == before + 1


def test_semantic_cache_hit_counter():
    """semantic_cache_hit_total increments."""
    from shared.metrics import semantic_cache_hit_total

    before = (
        REGISTRY.get_sample_value(
            "semantic_cache_hit_total",
            {"service": "test"},
        )
        or 0.0
    )
    semantic_cache_hit_total.labels(service="test").inc()
    after = REGISTRY.get_sample_value(
        "semantic_cache_hit_total",
        {"service": "test"},
    )
    assert after == before + 1


# ── _safe_counter / _safe_histogram deduplication ────────────────


def test_safe_counter_deduplication():
    """Calling _safe_counter twice with the same name returns the
    same collector object (not a new one, no ValueError)."""
    from shared.metrics import _safe_counter

    c1 = _safe_counter(
        "test_dedup_counter",
        "test",
        ["label_a"],
    )
    c2 = _safe_counter(
        "test_dedup_counter",
        "test",
        ["label_a"],
    )
    assert c1 is c2


def test_safe_histogram_deduplication():
    """Calling _safe_histogram twice with the same name returns the
    same collector object."""
    from shared.metrics import _safe_histogram

    h1 = _safe_histogram(
        "test_dedup_histogram",
        "test",
        ["label_a"],
    )
    h2 = _safe_histogram(
        "test_dedup_histogram",
        "test",
        ["label_a"],
    )
    assert h1 is h2


def test_safe_gauge_deduplication():
    """Calling _safe_gauge twice with the same name returns the
    same collector object."""
    from shared.metrics import _safe_gauge

    g1 = _safe_gauge("test_dedup_gauge", "test", ["label_a"])
    g2 = _safe_gauge("test_dedup_gauge", "test", ["label_a"])
    assert g1 is g2


# ── Helper functions ────────────────────────────────────────────


def test_get_status_class():
    """get_status_class returns correct bucket for all HTTP ranges."""
    from shared.metrics import get_status_class

    assert get_status_class(200) == "2xx"
    assert get_status_class(201) == "2xx"
    assert get_status_class(204) == "2xx"
    assert get_status_class(299) == "2xx"
    assert get_status_class(301) == "other"
    assert get_status_class(304) == "other"
    assert get_status_class(400) == "4xx"
    assert get_status_class(404) == "4xx"
    assert get_status_class(422) == "4xx"
    assert get_status_class(500) == "5xx"
    assert get_status_class(503) == "5xx"
    assert get_status_class(100) == "other"


def test_normalize_route_replaces_uuids():
    """normalize_route replaces UUIDs with {id}."""
    from shared.metrics import normalize_route

    route = "/api/contracts/550e8400-e29b-41d4-a716-446655440000"
    assert normalize_route(route) == "/api/contracts/{id}"


def test_normalize_route_replaces_numeric_ids():
    """normalize_route replaces numeric path segments with {id}."""
    from shared.metrics import normalize_route

    assert normalize_route("/api/items/42") == "/api/items/{id}"
    assert normalize_route("/api/items/42/details") == "/api/items/{id}/details"


def test_normalize_route_replaces_multiple_ids():
    """normalize_route handles multiple UUIDs and numeric IDs in one path."""
    from shared.metrics import normalize_route

    route = "/api/tenants/550e8400-e29b-41d4-a716-446655440000/items/99"
    assert normalize_route(route) == "/api/tenants/{id}/items/{id}"


# ── track_request_metrics decorator ─────────────────────────────


async def test_track_request_metrics_records_success():
    """track_request_metrics decorator records counter and histogram
    for a successful request."""
    from unittest.mock import MagicMock

    from shared.metrics import track_request_metrics

    # Snapshot before
    before = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {
                "service": "test-svc",
                "method": "GET",
                "route": "/api/test",
                "status_class": "2xx",
            },
        )
        or 0.0
    )

    # Create a mock request
    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/api/test"

    # Create a mock response
    mock_response = MagicMock()
    mock_response.status_code = 200

    @track_request_metrics("test-svc")
    async def handler(request):
        return mock_response

    result = await handler(mock_request)
    assert result.status_code == 200

    after = REGISTRY.get_sample_value(
        "http_requests_total",
        {
            "service": "test-svc",
            "method": "GET",
            "route": "/api/test",
            "status_class": "2xx",
        },
    )
    assert after == before + 1


async def test_track_request_metrics_records_errors():
    """track_request_metrics decorator records error metrics and
    re-raises the exception."""
    from unittest.mock import MagicMock

    import pytest

    from shared.metrics import track_request_metrics

    before = (
        REGISTRY.get_sample_value(
            "http_errors_total",
            {
                "service": "test-err-svc",
                "method": "POST",
                "route": "/api/fail",
                "status_code": "500",
            },
        )
        or 0.0
    )

    mock_request = MagicMock()
    mock_request.method = "POST"
    mock_request.url.path = "/api/fail"

    @track_request_metrics("test-err-svc")
    async def failing_handler(request):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await failing_handler(mock_request)

    after = REGISTRY.get_sample_value(
        "http_errors_total",
        {
            "service": "test-err-svc",
            "method": "POST",
            "route": "/api/fail",
            "status_code": "500",
        },
    )
    assert after == before + 1
