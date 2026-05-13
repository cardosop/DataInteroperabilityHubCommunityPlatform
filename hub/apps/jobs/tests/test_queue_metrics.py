"""
Phase 277.B.071 — RQ queue depth metric tests.
"""
from unittest.mock import MagicMock, patch

import pytest

from hub.apps.observability.otel_metrics import rq_queue_depth


class TestRqQueueDepthMetric:
    """Test the rq_queue_depth gauge metric definition and labels."""

    def test_metric_exists_with_expected_labels(self):
        assert rq_queue_depth.name == "rq_queue_depth"
        assert set(rq_queue_depth._expected_labels) == {"queue_name", "status"}

    def test_set_value_updates_labeled_gauge(self):
        labeled = rq_queue_depth.labels(queue_name="job_default", status="queued")
        before = labeled._value.get()
        labeled.set(42)
        after = labeled._value.get()
        assert after == 42

    def test_set_updates_different_labels_independently(self):
        a = rq_queue_depth.labels(queue_name="job_default", status="queued")
        b = rq_queue_depth.labels(queue_name="job_critical", status="queued")
        a.set(10)
        b.set(20)
        assert a._value.get() == 10
        assert b._value.get() == 20

    def test_set_resets_previous_value(self):
        labeled = rq_queue_depth.labels(queue_name="job_default", status="queued")
        labeled.set(100)
        labeled.set(5)
        assert labeled._value.get() == 5

    def test_all_status_labels(self):
        for status in ("queued", "started", "deferred", "finished", "failed"):
            labeled = rq_queue_depth.labels(queue_name="job_default", status=status)
            labeled.set(1)
            assert labeled._value.get() == 1, f"Failed for status={status}"

    def test_all_queue_labels(self):
        for queue in ("job_critical", "job_default", "job_low", "default"):
            labeled = rq_queue_depth.labels(queue_name=queue, status="queued")
            labeled.set(1)
            assert labeled._value.get() == 1, f"Failed for queue={queue}"


@pytest.mark.django_db
class TestEmitRqQueueDepth:
    """Test the emit_rq_queue_depth function with a fake Redis connection."""

    def test_emit_returns_empty_dict_when_no_queues(self, settings):
        settings.RQ_QUEUES = {}
        from hub.apps.jobs.queue_metrics import emit_rq_queue_depth

        with patch("hub.apps.jobs.queue_metrics._get_redis_connection") as mock_conn:
            mock_conn.return_value = MagicMock()
            result = emit_rq_queue_depth()
            assert result == {}

    def test_emit_returns_empty_on_redis_failure(self, settings):
        settings.RQ_QUEUES = {"default": {}}
        from hub.apps.jobs.queue_metrics import emit_rq_queue_depth

        with patch("hub.apps.jobs.queue_metrics._get_redis_connection") as mock_conn:
            mock_conn.side_effect = OSError("connection refused")
            result = emit_rq_queue_depth()
            assert result == {}

    def test_emit_samples_queue_depths(self, settings):
        settings.RQ_QUEUES = {"job_default": {}, "job_critical": {}}
        from hub.apps.jobs.queue_metrics import emit_rq_queue_depth

        fake_redis = MagicMock()
        # llen returns queue depth, zcard returns registry counts
        fake_redis.llen.side_effect = lambda key: {
            "rq:queue:job_default": 15,
            "rq:queue:job_critical": 3,
        }.get(key, 0)
        fake_redis.zcard.return_value = 0

        with patch("hub.apps.jobs.queue_metrics._get_redis_connection") as mock_conn:
            mock_conn.return_value = fake_redis
            result = emit_rq_queue_depth()

        assert result["job_default"] == 15
        assert result["job_critical"] == 3

        # Verify the gauge was updated
        default_labeled = rq_queue_depth.labels(
            queue_name="job_default", status="queued"
        )
        assert default_labeled._value.get() == 15
        critical_labeled = rq_queue_depth.labels(
            queue_name="job_critical", status="queued"
        )
        assert critical_labeled._value.get() == 3

    def test_emit_reports_registry_counts(self, settings):
        settings.RQ_QUEUES = {"job_default": {}}
        from hub.apps.jobs.queue_metrics import emit_rq_queue_depth

        fake_redis = MagicMock()
        fake_redis.llen.return_value = 0
        fake_redis.zcard.side_effect = lambda key: {
            "rq:started:job_default": 5,
            "rq:deferred:job_default": 2,
            "rq:finished:job_default": 100,
            "rq:failed:job_default": 3,
        }.get(key, 0)

        with patch("hub.apps.jobs.queue_metrics._get_redis_connection") as mock_conn:
            mock_conn.return_value = fake_redis
            emit_rq_queue_depth()

        started = rq_queue_depth.labels(queue_name="job_default", status="started")
        assert started._value.get() == 5
        failed = rq_queue_depth.labels(queue_name="job_default", status="failed")
        assert failed._value.get() == 3
