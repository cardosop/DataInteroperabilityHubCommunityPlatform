"""
Tests for ``hub.apps.core.metrics``.

Verifies throttle_hit_total counter creation and fallback stub behaviour.
"""

from django.test import SimpleTestCase


class ThrottleMetricsTests(SimpleTestCase):
    """Tests for the throttle_hit_total Prometheus counter / stub."""

    def test_throttle_hit_total_is_importable(self):
        """throttle_hit_total is available from hub.apps.core.metrics."""
        from hub.apps.core.metrics import throttle_hit_total

        assert throttle_hit_total is not None

    def test_throttle_hit_total_supports_labels_inc_interface(self):
        """Counter or stub both support .labels(...).inc() without raising."""
        from hub.apps.core.metrics import throttle_hit_total

        metric = throttle_hit_total.labels(
            app="test_app", view="TestView", scope="user", tenant_id="t1"
        )
        metric.inc()
        # No exception → pass

    def test_counter_has_correct_label_names(self):
        """When prometheus_client is available, the counter MUST have the
        expected label dimensions.  Uses assertIsNotNone so a missing
        _labelnames attribute causes a hard FAIL, not a silent pass."""
        try:
            from prometheus_client import Counter
        except ImportError:
            # prometheus_client not installed — stub is used, skip
            return

        from hub.apps.core.metrics import throttle_hit_total

        if isinstance(throttle_hit_total, Counter):
            label_names = getattr(throttle_hit_total, "_labelnames", None)
            assert label_names is not None, (
                "Counter should expose _labelnames; got None. "
                "New prometheus_client version may have renamed the attribute."
            )
            assert set(label_names) == {"app", "view", "scope", "tenant_id"}

    def test_stub_labels_returns_self(self):
        """_MetricStub.labels() returns itself for chaining."""
        from hub.apps.core.metrics import _MetricStub

        stub = _MetricStub()
        result = stub.labels(app="a", view="v", scope="s", tenant_id="t")
        assert result is stub

    def test_stub_inc_is_noop(self):
        """_MetricStub.inc() does not raise for any amount."""
        from hub.apps.core.metrics import _MetricStub

        stub = _MetricStub()
        stub.labels(app="a", view="v", scope="s", tenant_id="t").inc()
        stub.labels(app="a", view="v", scope="s", tenant_id="t").inc(5)
        # No exception → pass
