"""
Integration tests for event bus metrics exposure.

Tests that event bus metrics are properly exposed via the Prometheus endpoint.
"""

import pytest


@pytest.fixture(autouse=True, scope="class")
def _ensure_event_metrics_registered():
    """Emit a dummy observation on every event-bus metric the tests expect.

    OTEL instruments are lazily created on first ``.inc()`` / ``.observe()``
    call, and the Prometheus text output only includes a metric after at least
    one observation with a label set has been recorded.  Without this fixture
    the test process may not have processed any events yet, so the registry
    is empty for event-bus metrics.

    The dummy labels use ``_test_metrics_exposure`` to be distinguishable
    from real traffic in case the process is ever scraped.
    """
    from hub.apps.core.events.metrics import (
        event_consumed_total,
        event_consume_failed_total,
        event_dlq_size,
        event_handler_retry_count,
        event_latency_seconds,
        event_processing_duration_seconds,
        event_publish_duration_seconds,
        event_publish_failed_total,
        event_published_total,
        event_queue_depth,
        event_retry_attempts_total,
    )
    from hub.apps.observability.otel_metrics import get_meter

    get_meter()  # ensure MeterProvider + PrometheusMetricReader are initialised

    base = {"event_type": "_test_metrics_exposure", "tenant_id": "system"}
    event_published_total.labels(**base, status="success").inc()
    event_publish_duration_seconds.labels(**base, status="success").observe(0.001)
    event_publish_failed_total.labels(**base, error_type="test").inc()

    sub = {**base, "subscriber_name": "_test_metrics_exposure"}
    event_consumed_total.labels(**sub, status="success").inc()
    event_consume_failed_total.labels(**sub, error_type="test").inc()
    event_processing_duration_seconds.labels(**sub, status="success").observe(0.001)
    event_latency_seconds.labels(**sub).observe(0.001)
    event_queue_depth.labels(**sub).inc()
    event_handler_retry_count.labels(**sub).observe(0)
    event_retry_attempts_total.labels(**sub).inc()
    event_dlq_size.labels(**sub).inc()


def _require_metrics(client):
    """Return the GET /metrics/ response, or skip if the endpoint is unavailable."""
    response = client.get("/metrics/")
    if response.status_code == 503:
        pytest.skip("Metrics endpoint not available (OTEL Prometheus registry not initialized)")
    return response


@pytest.mark.integration
class TestEventBusMetricsExposure:
    """Test event bus metrics exposure via Prometheus endpoint."""

    def test_metrics_endpoint_accessible(self, client):
        """Test that metrics endpoint is accessible."""
        response = _require_metrics(client)
        assert response.status_code == 200
        assert (
            "text/plain" in response["Content-Type"]
            or "text/plain; version=0.0.4" in response["Content-Type"]
        )

    def test_event_publish_metrics_exposed(self, client):
        """Test that event publish metrics are exposed."""
        response = _require_metrics(client)
        content = response.content.decode("utf-8")
        assert "event_published_total" in content
        assert "event_publish_duration_seconds" in content
        assert "event_publish_failed_total" in content

    def test_event_consume_metrics_exposed(self, client):
        """Test that event consume metrics are exposed."""
        response = _require_metrics(client)
        content = response.content.decode("utf-8")
        assert "event_consumed_total" in content
        assert "event_processing_duration_seconds" in content
        assert "event_consume_failed_total" in content

    def test_event_latency_metrics_exposed(self, client):
        """Test that event latency metrics are exposed."""
        response = _require_metrics(client)
        content = response.content.decode("utf-8")
        assert "event_latency_seconds" in content

    def test_event_queue_depth_metrics_exposed(self, client):
        """Test that event queue depth metrics are exposed."""
        response = _require_metrics(client)
        content = response.content.decode("utf-8")
        assert "event_queue_depth" in content

    def test_event_retry_metrics_exposed(self, client):
        """Test that event retry metrics are exposed."""
        response = _require_metrics(client)
        content = response.content.decode("utf-8")
        assert "event_handler_retry_count" in content
        assert "event_retry_attempts_total" in content

    def test_dlq_metrics_exposed(self, client):
        """Test that DLQ metrics are exposed."""
        response = _require_metrics(client)
        content = response.content.decode("utf-8")
        assert "event_dlq_size" in content

    def test_metrics_format_valid(self, client):
        """Test that metrics are in valid Prometheus format."""
        response = _require_metrics(client)
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        lines = content.split("\n")
        help_lines = [l for l in lines if l.startswith("# HELP")]
        type_lines = [l for l in lines if l.startswith("# TYPE")]

        assert len(help_lines) > 0 or len(type_lines) > 0
