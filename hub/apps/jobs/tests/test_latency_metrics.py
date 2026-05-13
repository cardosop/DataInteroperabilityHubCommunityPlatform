"""
Phase 277.B.075 — worker latency + uptime metric tests.
"""
import time
from unittest.mock import patch

import pytest

from hub.apps.observability.otel_metrics import (
    job_queue_latency_seconds,
    worker_uptime_seconds,
)
from hub.apps.jobs.latency_metrics import (
    record_job_latency,
    record_worker_uptime,
    task_latency_tracker,
)


class TestJobQueueLatencyMetric:
    """Test the job_queue_latency_seconds histogram definition + labels."""

    def test_metric_exists_with_expected_labels(self):
        assert job_queue_latency_seconds.name == "job_queue_latency_seconds"
        assert set(job_queue_latency_seconds._expected_labels) == {
            "queue_name", "job_type", "status",
        }

    def test_observe_records_latency(self):
        labeled = job_queue_latency_seconds.labels(
            queue_name="job_default", job_type="TEST_JOB", status="COMPLETED"
        )
        before = labeled._value.get()
        labeled.observe(2.5)
        after = labeled._value.get()
        assert after > before

    def test_independent_labels_track_separately(self):
        a = job_queue_latency_seconds.labels(
            queue_name="job_default", job_type="A", status="COMPLETED"
        )
        b = job_queue_latency_seconds.labels(
            queue_name="job_critical", job_type="B", status="COMPLETED"
        )
        a.observe(1.0)
        b.observe(3.0)
        # Both should have recorded observations
        assert a._value.get() > 0
        assert b._value.get() > 0


class TestRecordJobLatency:
    def test_records_completed_latency(self):
        record_job_latency("job_default", "WEBHOOK_DELIVERY", 2.3, status="COMPLETED")
        labeled = job_queue_latency_seconds.labels(
            queue_name="job_default", job_type="WEBHOOK_DELIVERY", status="COMPLETED"
        )
        assert labeled._value.get() > 0

    def test_records_failed_latency(self):
        record_job_latency("job_critical", "DQ_RUN", 0.5, status="FAILED")
        labeled = job_queue_latency_seconds.labels(
            queue_name="job_critical", job_type="DQ_RUN", status="FAILED"
        )
        assert labeled._value.get() > 0

    def test_all_queues_separated(self):
        for q in ("job_critical", "job_default", "job_low"):
            record_job_latency(q, "TASK", 1.0)
            labeled = job_queue_latency_seconds.labels(
                queue_name=q, job_type="TASK", status="COMPLETED"
            )
            assert labeled._value.get() > 0, f"Failed for queue={q}"


class TestRecordWorkerUptime:
    def test_metric_exists_with_expected_labels(self):
        assert worker_uptime_seconds.name == "worker_uptime_seconds"
        assert set(worker_uptime_seconds._expected_labels) == {"queue_name",}

    def test_set_uptime(self):
        record_worker_uptime("job_default", 3600.0)
        labeled = worker_uptime_seconds.labels(queue_name="job_default")
        assert labeled._value.get() == 3600.0

    def test_uptime_updates(self):
        record_worker_uptime("job_critical", 100.0)
        record_worker_uptime("job_critical", 200.0)
        labeled = worker_uptime_seconds.labels(queue_name="job_critical")
        assert labeled._value.get() == 200.0

    def test_independent_queues(self):
        record_worker_uptime("job_default", 500.0)
        record_worker_uptime("job_critical", 1000.0)
        assert worker_uptime_seconds.labels(queue_name="job_default")._value.get() == 500.0
        assert worker_uptime_seconds.labels(queue_name="job_critical")._value.get() == 1000.0


class TestTaskLatencyTracker:
    def test_records_latency_on_success(self):
        with task_latency_tracker("job_default", "TRACKER_TEST"):
            time.sleep(0.01)

        labeled = job_queue_latency_seconds.labels(
            queue_name="job_default", job_type="TRACKER_TEST", status="COMPLETED"
        )
        assert labeled._value.get() > 0

    def test_records_latency_on_failure_and_re_raises(self):
        with pytest.raises(ValueError, match="tracker boom"):
            with task_latency_tracker("job_default", "FAIL_TRACKER"):
                raise ValueError("tracker boom")

        labeled = job_queue_latency_seconds.labels(
            queue_name="job_default", job_type="FAIL_TRACKER", status="FAILED"
        )
        assert labeled._value.get() > 0
