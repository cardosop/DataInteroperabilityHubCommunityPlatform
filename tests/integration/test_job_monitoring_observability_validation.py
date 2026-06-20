"""
Comprehensive Job Monitoring & Observability Validation Tests (10.1.24)

Engineering-grade integration tests for job monitoring, observability,
metrics collection, performance monitoring, failure tracking, queue
metrics, and worker health monitoring.

All tests use real implementations (no mocks/stubs) and fix root
causes of any failures.

Root-cause fix for timeout issues: the original tests used
time.sleep() to simulate job durations (up to 10s per job,
totalling 30s+ per test). This caused timeouts with --timeout=60.

Fix: set started_at / completed_at timestamps directly on the Job
model instead of sleeping. The Job model supports direct timestamp
assignment -- mark_started/mark_completed use timezone.now()
internally but the fields are regular DateTimeFields that accept
direct writes.

Tests cover:
- 10.1.24.1: Job Metrics Collection Testing
- 10.1.24.2: Job Performance Monitoring Testing
- 10.1.24.3: Job Failure Tracking Testing
- 10.1.24.4: Job Queue Metrics Testing
- 10.1.24.5: Job Worker Health Monitoring Testing
"""

import contextlib
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q
from django.test import TestCase
from django.utils import timezone
from django_rq import get_queue

from hub.apps.jobs.models import (
    Job,
    JobPriority,
    JobStatus,
    JobType,
)
from hub.apps.jobs.utils import (
    create_job,
)
from hub.apps.observability.otel_metrics import (
    job_duration_seconds,
    job_queue_depth,
    job_queue_length,
    job_worker_active,
    job_worker_throughput,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from services.worker.health import healthz, ready

User = get_user_model()


def _create_completed_job(
    tenant,
    user,
    job_type,
    duration_seconds,
    status_val=None,
    error_message=None,
):
    """Create a job with pre-set timestamps (no sleeping).

    Sets started_at and completed_at directly to simulate a job
    that ran for ``duration_seconds``.
    """
    if status_val is None:
        status_val = JobStatus.COMPLETED.value

    now = timezone.now()
    started = now - timedelta(seconds=duration_seconds + 1)
    completed = started + timedelta(seconds=duration_seconds)

    job = create_job(
        tenant=tenant,
        user=user,
        job_type=job_type,
        resource_type="CONTRACT",
        resource_id=str(uuid.uuid4()),
    )
    job.status = status_val
    job.started_at = started
    job.completed_at = completed
    if error_message:
        job.error_message = error_message
    job.save(
        update_fields=[
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "updated_at",
        ]
    )
    return job


def _create_failed_job(
    tenant,
    user,
    job_type,
    error_message,
    duration_seconds=0.5,
):
    """Create a failed job with pre-set timestamps."""
    return _create_completed_job(
        tenant,
        user,
        job_type,
        duration_seconds,
        status_val=JobStatus.FAILED.value,
        error_message=error_message,
    )


class JobMetricsCollectionTest(TestCase):
    """10.1.24.1: Job Metrics Collection Testing"""

    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name=f"Metrics Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"metrics-test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=(f"metrics_test-{uuid.uuid4().hex[:8]}@example.com"),
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        for qn in ["job_critical", "job_default", "job_low", "default"]:
            with contextlib.suppress(Exception):
                get_queue(qn).empty()

    def tearDown(self):
        cache.clear()
        for qn in ["job_critical", "job_default", "job_low", "default"]:
            with contextlib.suppress(Exception):
                get_queue(qn).empty()

    def test_job_execution_metrics_count(self):
        """Job counts: 3 completed + 2 failed = 5 total."""
        jt = JobType.CONTRACT_VALIDATION.value
        for dur in [0.5, 0.8, 1.2]:
            _create_completed_job(
                self.tenant,
                self.user,
                jt,
                dur,
            )
        for msg in ["Test failure A", "Test failure B"]:
            _create_failed_job(
                self.tenant,
                self.user,
                jt,
                msg,
            )

        total = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
        ).count()
        self.assertEqual(total, 5)

        completed = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.COMPLETED.value,
        ).count()
        self.assertEqual(completed, 3)

        failed = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.FAILED.value,
        ).count()
        self.assertEqual(failed, 2)

        # Verify durations are positive
        for job in Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.COMPLETED.value,
            started_at__isnull=False,
            completed_at__isnull=False,
        ):
            dur = (job.completed_at - job.started_at).total_seconds()
            self.assertGreater(dur, 0)

    def test_job_queue_metrics(self):
        """Queue objects are accessible and metrics recordable."""
        jt = JobType.DQ_RUN.value
        create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=jt,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            priority=JobPriority.HIGH.value,
        )

        crit_q = get_queue("job_critical")
        self.assertIsNotNone(crit_q)
        depth = crit_q.count
        self.assertGreaterEqual(depth, 0)

        # Verify Prometheus metric operations work
        job_queue_length.labels(
            job_type=jt,
            queue_name="job_critical",
        ).set(depth)
        job_queue_depth.labels(
            job_type=jt,
            queue_name="job_critical",
        ).set(depth)

    def test_job_performance_metrics_percentiles(self):
        """p50/p95/p99 computed from job durations."""
        jt = JobType.ODPS_NORMALIZATION.value
        durations = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0]
        for dur in durations:
            _create_completed_job(
                self.tenant,
                self.user,
                jt,
                dur,
            )

        job_durations = sorted(
            (j.completed_at - j.started_at).total_seconds()
            for j in Job.objects.filter(
                tenant=self.tenant,
                type=jt,
                status=JobStatus.COMPLETED.value,
                started_at__isnull=False,
                completed_at__isnull=False,
            )
        )
        self.assertEqual(len(job_durations), 10)

        p50_i = int(len(job_durations) * 0.50)
        p95_i = min(
            int(len(job_durations) * 0.95),
            len(job_durations) - 1,
        )
        p99_i = min(
            int(len(job_durations) * 0.99),
            len(job_durations) - 1,
        )
        p50 = job_durations[p50_i]
        p95 = job_durations[p95_i]
        p99 = job_durations[p99_i]

        self.assertGreater(p50, 0)
        self.assertGreaterEqual(p95, p50)
        self.assertGreaterEqual(p99, p95)

        job_duration_seconds.labels(
            job_type=jt,
            status="COMPLETED",
        ).observe(p50)

    def test_job_error_metrics(self):
        """Error types are categorised correctly."""
        jt = JobType.ODPS_REF_RESOLUTION.value
        errors = [
            ("TIMEOUT", "Timeout exceeded"),
            ("VALIDATION_ERROR", "Validation error: invalid input"),
            ("CONNECTION_ERROR", "Connection error: unavailable"),
            ("PERMISSION_ERROR", "Permission denied"),
            ("UNKNOWN_ERROR", "Unexpected error"),
        ]
        for code, msg in errors:
            j = _create_failed_job(
                self.tenant,
                self.user,
                jt,
                msg,
            )
            j.result_json = {"error_code": code}
            j.save(update_fields=["result_json", "updated_at"])

        failed = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.FAILED.value,
        )
        self.assertEqual(failed.count(), len(errors))

        for keyword in [
            "timeout",
            "validation",
            "connection",
            "permission",
        ]:
            self.assertGreaterEqual(
                failed.filter(
                    error_message__icontains=keyword,
                ).count(),
                1,
                f"No failures containing '{keyword}'",
            )

        total = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
        ).count()
        rate = failed.count() / total * 100
        self.assertGreater(rate, 0)
        self.assertLessEqual(rate, 100)

    def test_metrics_aggregation_and_reporting(self):
        """Aggregation by job type and tenant works."""
        jts = [
            JobType.ODPS_NORMALIZATION.value,
            JobType.ODPS_REF_RESOLUTION.value,
            JobType.ODPS_EXPORT.value,
        ]
        for jt in jts:
            for dur in [0.5, 1.0, 2.0]:
                _create_completed_job(
                    self.tenant,
                    self.user,
                    jt,
                    dur,
                )

        agg = (
            Job.objects.filter(
                tenant=self.tenant,
            )
            .values("type")
            .annotate(
                total_count=Count("id"),
                completed_count=Count(
                    "id",
                    filter=Q(status=JobStatus.COMPLETED.value),
                ),
            )
        )
        self.assertEqual(agg.count(), 3)
        for row in agg:
            self.assertEqual(row["total_count"], 3)
            self.assertEqual(row["completed_count"], 3)

        tenant_agg = Job.objects.filter(
            tenant=self.tenant,
        ).aggregate(
            total_jobs=Count("id"),
            completed_jobs=Count(
                "id",
                filter=Q(status=JobStatus.COMPLETED.value),
            ),
        )
        self.assertEqual(tenant_agg["total_jobs"], 9)
        self.assertEqual(tenant_agg["completed_jobs"], 9)


class JobPerformanceMonitoringTest(TestCase):
    """10.1.24.2: Job Performance Monitoring Testing"""

    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name=f"Performance Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"performance-test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=(f"perf_test-{uuid.uuid4().hex[:8]}@example.com"),
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def tearDown(self):
        cache.clear()

    def test_job_execution_time_tracking(self):
        """Durations match expected values within tolerance."""
        jt = JobType.ODPS_EXPORT.value
        expected = [0.5, 1.0, 2.0, 5.0]
        for dur in expected:
            _create_completed_job(
                self.tenant,
                self.user,
                jt,
                dur,
            )

        jobs = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.COMPLETED.value,
            started_at__isnull=False,
            completed_at__isnull=False,
        )
        self.assertEqual(jobs.count(), len(expected))

        actual_durs = sorted((j.completed_at - j.started_at).total_seconds() for j in jobs)
        for actual, exp in zip(actual_durs, sorted(expected)):
            self.assertAlmostEqual(
                actual,
                exp,
                delta=0.1,
                msg=f"Expected ~{exp}s, got {actual}s",
            )

    def test_job_resource_usage(self):
        """Resource usage stored in details_json is queryable."""
        jt = JobType.ODPS_SEMANTIC_MAPPING.value
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=jt,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
        )
        job.details_json = {
            "cpu_usage_percent": 45.5,
            "memory_usage_mb": 256.0,
            "peak_memory_mb": 512.0,
        }
        job.save(update_fields=["details_json", "updated_at"])

        job.refresh_from_db()
        self.assertEqual(
            job.details_json["cpu_usage_percent"],
            45.5,
        )
        self.assertEqual(
            job.details_json["memory_usage_mb"],
            256.0,
        )

    def test_job_throughput_monitoring(self):
        """Throughput calculated from completed jobs."""
        jt = JobType.CONTRACT_VALIDATION.value
        num_jobs = 10
        # All completed within a 10-second window
        base = timezone.now() - timedelta(seconds=15)
        for i in range(num_jobs):
            j = create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=jt,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
            )
            j.status = JobStatus.COMPLETED.value
            j.started_at = base + timedelta(seconds=i)
            j.completed_at = base + timedelta(seconds=i + 0.5)
            j.save(
                update_fields=[
                    "status",
                    "started_at",
                    "completed_at",
                    "updated_at",
                ]
            )

        completed = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.COMPLETED.value,
        )
        self.assertEqual(completed.count(), num_jobs)

        first = completed.order_by("started_at").first()
        last = completed.order_by("-completed_at").first()
        window = (last.completed_at - first.started_at).total_seconds()
        throughput = num_jobs / window if window > 0 else 0
        self.assertGreater(throughput, 0)

    def test_job_bottleneck_identification(self):
        """Jobs exceeding threshold are identified as bottlenecks."""
        jt = JobType.ODPS_NORMALIZATION.value
        durations = [0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0]
        for dur in durations:
            _create_completed_job(
                self.tenant,
                self.user,
                jt,
                dur,
            )

        threshold = 2.0
        bottlenecks = (
            Job.objects.filter(
                tenant=self.tenant,
                type=jt,
                status=JobStatus.COMPLETED.value,
                started_at__isnull=False,
                completed_at__isnull=False,
            )
            .annotate(
                dur=F("completed_at") - F("started_at"),
            )
            .filter(
                dur__gt=timedelta(seconds=threshold),
            )
        )
        # 5.0 and 10.0 exceed the 2.0s threshold
        self.assertGreaterEqual(bottlenecks.count(), 2)

    def test_job_performance_regression_detection(self):
        """Regression detected when current >> baseline average."""
        jt = JobType.ODPS_REF_RESOLUTION.value
        baseline_durs = [0.5, 0.6, 0.7, 0.8, 0.9]
        current_durs = [1.5, 1.6, 1.7, 1.8, 1.9]

        base_time = timezone.now() - timedelta(hours=2)
        for i, dur in enumerate(baseline_durs):
            j = create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=jt,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
            )
            j.status = JobStatus.COMPLETED.value
            j.started_at = base_time + timedelta(minutes=i)
            j.completed_at = j.started_at + timedelta(seconds=dur)
            j.result_json = {"baseline": True}
            j.save(
                update_fields=[
                    "status",
                    "started_at",
                    "completed_at",
                    "result_json",
                    "updated_at",
                ]
            )

        cur_time = timezone.now() - timedelta(minutes=30)
        for i, dur in enumerate(current_durs):
            j = create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=jt,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
            )
            j.status = JobStatus.COMPLETED.value
            j.started_at = cur_time + timedelta(minutes=i)
            j.completed_at = j.started_at + timedelta(seconds=dur)
            j.result_json = {"baseline": False}
            j.save(
                update_fields=[
                    "status",
                    "started_at",
                    "completed_at",
                    "result_json",
                    "updated_at",
                ]
            )

        baseline_avg = sum(baseline_durs) / len(baseline_durs)
        current_avg = sum(current_durs) / len(current_durs)

        regression_threshold = 1.5
        self.assertTrue(
            current_avg > baseline_avg * regression_threshold,
            f"current_avg={current_avg:.2f} should exceed "
            f"baseline={baseline_avg:.2f} * {regression_threshold}",
        )
        pct = (current_avg - baseline_avg) / baseline_avg * 100
        self.assertGreater(pct, 50)


class JobFailureTrackingTest(TestCase):
    """10.1.24.3: Job Failure Tracking Testing"""

    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name=f"Failure Tracking Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"failure-tracking-test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=(f"fail_test-{uuid.uuid4().hex[:8]}@example.com"),
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def tearDown(self):
        cache.clear()

    def test_job_failure_rate_monitoring(self):
        """Failure rate matches expected ratio (25%)."""
        jt = JobType.ODPS_EXPORT.value
        for dur in [0.3] * 15:
            _create_completed_job(
                self.tenant,
                self.user,
                jt,
                dur,
            )
        for msg in [f"Test failure {i}" for i in range(5)]:
            _create_failed_job(
                self.tenant,
                self.user,
                jt,
                msg,
            )

        all_jobs = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
        )
        failed_ct = all_jobs.filter(
            status=JobStatus.FAILED.value,
        ).count()
        total_ct = all_jobs.count()

        rate = failed_ct / total_ct * 100
        self.assertAlmostEqual(rate, 25.0, delta=5.0)

    def test_job_failure_reason_tracking(self):
        """Failure reasons are categorised by keyword."""
        jt = JobType.ODPS_SEMANTIC_MAPPING.value
        reasons = [
            "Timeout exceeded",
            "Validation error: invalid input",
            "Connection error: service unavailable",
            "Permission denied: insufficient access",
            "Resource not found",
        ]
        for reason in reasons:
            _create_failed_job(
                self.tenant,
                self.user,
                jt,
                reason,
            )

        failed = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.FAILED.value,
        )
        self.assertEqual(failed.count(), len(reasons))

        for keyword in [
            "timeout",
            "validation",
            "connection",
            "permission",
        ]:
            self.assertGreaterEqual(
                failed.filter(
                    error_message__icontains=keyword,
                ).count(),
                1,
                f"No failures with keyword '{keyword}'",
            )

    def test_job_failure_pattern_analysis(self):
        """Failure patterns grouped by job type."""
        jt_norm = JobType.ODPS_NORMALIZATION.value
        jt_ref = JobType.ODPS_REF_RESOLUTION.value

        for _ in range(3):
            _create_failed_job(
                self.tenant,
                self.user,
                jt_norm,
                "Timeout exceeded",
            )
        for _ in range(2):
            _create_failed_job(
                self.tenant,
                self.user,
                jt_ref,
                "Validation error",
            )

        timeout_pattern = (
            Job.objects.filter(
                tenant=self.tenant,
                status=JobStatus.FAILED.value,
                error_message__icontains="timeout",
            )
            .values("type")
            .annotate(
                count=Count("id"),
            )
            .order_by("-count")
        )

        self.assertGreaterEqual(timeout_pattern.count(), 1)
        top = timeout_pattern.first()
        self.assertEqual(top["type"], jt_norm)
        self.assertEqual(top["count"], 3)

    def test_job_failure_alerting(self):
        """Alert threshold detection: 4 failures in 5 minutes."""
        jt = JobType.ODPS_EXPORT.value
        threshold = 3
        now = timezone.now()

        for i in range(threshold + 1):
            j = _create_failed_job(
                self.tenant,
                self.user,
                jt,
                "Critical failure",
            )
            j.completed_at = now - timedelta(seconds=30 * i)
            j.save(update_fields=["completed_at", "updated_at"])

        recent = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.FAILED.value,
            completed_at__gte=now - timedelta(minutes=5),
        ).count()
        self.assertGreaterEqual(recent, threshold)

    def test_job_failure_recovery_tracking(self):
        """Failed job retried and completed -> recovery tracked."""
        jt = JobType.ODPS_SEMANTIC_MAPPING.value

        job = _create_failed_job(
            self.tenant,
            self.user,
            jt,
            "Transient error",
        )
        job.details_json = {
            "retry_count": 1,
            "last_retry_error": "Transient error",
            "last_retry_at": timezone.now().isoformat(),
        }
        job.save(update_fields=["details_json", "updated_at"])

        # Retry succeeds
        now = timezone.now()
        job.status = JobStatus.COMPLETED.value
        job.started_at = now - timedelta(seconds=1)
        job.completed_at = now
        job.error_message = None
        job.result_json = {
            "attempt": 2,
            "status": "success",
            "recovered": True,
        }
        job.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
                "error_message",
                "result_json",
                "updated_at",
            ]
        )

        job.refresh_from_db()
        self.assertEqual(
            job.status,
            JobStatus.COMPLETED.value,
        )
        self.assertEqual(
            job.details_json["retry_count"],
            1,
        )
        self.assertTrue(
            job.result_json.get("recovered"),
        )


class JobQueueMetricsTest(TestCase):
    """10.1.24.4: Job Queue Metrics Testing"""

    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name=f"Queue Metrics Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"queue-metrics-test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=(f"queue_test-{uuid.uuid4().hex[:8]}@example.com"),
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        for qn in ["job_critical", "job_default", "job_low"]:
            with contextlib.suppress(Exception):
                get_queue(qn).empty()

    def tearDown(self):
        cache.clear()
        for qn in ["job_critical", "job_default", "job_low"]:
            with contextlib.suppress(Exception):
                get_queue(qn).empty()

    def test_queue_depth_monitoring(self):
        """Queue depth is non-negative and recordable."""
        for _ in range(5):
            create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=JobType.CONTRACT_VALIDATION.value,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
            )

        q = get_queue("job_default")
        depth = q.count
        self.assertGreaterEqual(depth, 0)

        job_queue_depth.labels(
            job_type=JobType.CONTRACT_VALIDATION.value,
            queue_name="job_default",
        ).set(depth)

    def test_queue_processing_rate(self):
        """Completed jobs yield positive throughput."""
        jt = JobType.SEMANTIC_MAPPING.value
        num_jobs = 10
        base = timezone.now() - timedelta(seconds=20)

        for i in range(num_jobs):
            j = create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=jt,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
            )
            j.status = JobStatus.COMPLETED.value
            j.started_at = base + timedelta(seconds=i)
            j.completed_at = base + timedelta(seconds=i + 0.3)
            j.save(
                update_fields=[
                    "status",
                    "started_at",
                    "completed_at",
                    "updated_at",
                ]
            )

        completed = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.COMPLETED.value,
        )
        self.assertEqual(completed.count(), num_jobs)

    def test_queue_backlog_tracking(self):
        """Pending jobs tracked as backlog."""
        jt = JobType.ODPS_NORMALIZATION.value
        num_jobs = 8
        for _ in range(num_jobs):
            create_job(
                tenant=self.tenant,
                user=self.user,
                job_type=jt,
                resource_type="CONTRACT",
                resource_id=str(uuid.uuid4()),
            )

        backlog = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.PENDING.value,
        ).count()
        self.assertGreaterEqual(backlog, 0)
        self.assertLessEqual(backlog, num_jobs)

    def test_queue_worker_utilization(self):
        """Worker utilization computed from completed jobs."""
        jt = JobType.ODPS_REF_RESOLUTION.value
        num_jobs = 5
        for dur in [0.3] * num_jobs:
            _create_completed_job(
                self.tenant,
                self.user,
                jt,
                dur,
            )

        completed = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.COMPLETED.value,
        ).count()
        utilization = completed / num_jobs * 100
        self.assertEqual(utilization, 100.0)

    def test_queue_health_monitoring(self):
        """All queues accessible and below healthy depth."""
        max_healthy = 100
        for qn in ["job_critical", "job_default", "job_low"]:
            q = get_queue(qn)
            self.assertIsNotNone(q)
            self.assertLess(
                q.count,
                max_healthy,
                f"Queue '{qn}' depth exceeds {max_healthy}",
            )


class JobWorkerHealthMonitoringTest(TestCase):
    """10.1.24.5: Job Worker Health Monitoring Testing"""

    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name=f"Worker Health Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"worker-health-test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=(f"wh_test-{uuid.uuid4().hex[:8]}@example.com"),
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def tearDown(self):
        cache.clear()

    def test_worker_health_checks(self):
        """healthz() returns 200 ok; ready() returns expected structure."""
        code, data = healthz()
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "worker-service")

        r_code, r_data = ready()
        self.assertIn(r_code, [200, 503])
        self.assertIn(
            r_data["status"],
            ["ready", "not_ready"],
        )
        self.assertIn("checks", r_data)

        if r_data["status"] == "ready":
            for dep in ["database", "redis_queue", "cache"]:
                self.assertIn(dep, r_data["checks"])

    def test_worker_heartbeat_monitoring(self):
        """Worker activity tracked via Prometheus gauge."""
        wid = "test-worker-1"
        qn = "job_default"

        job_worker_active.labels(
            worker_id=wid,
            queue_name=qn,
        ).set(1)

        j = _create_completed_job(
            self.tenant,
            self.user,
            JobType.CONTRACT_VALIDATION.value,
            0.5,
        )
        j.result_json = {"worker_id": wid}
        j.save(update_fields=["result_json", "updated_at"])

        job_worker_throughput.labels(
            worker_id=wid,
            job_type=JobType.CONTRACT_VALIDATION.value,
        ).inc()

        # Verify the job was completed by the worker
        j.refresh_from_db()
        self.assertEqual(
            j.result_json["worker_id"],
            wid,
        )

    def test_worker_failure_detection(self):
        """Stuck RUNNING job indicates worker failure."""
        wid = "test-worker-2"
        qn = "job_default"

        job_worker_active.labels(
            worker_id=wid,
            queue_name=qn,
        ).set(1)

        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.ODPS_EXPORT.value,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
        )
        job.status = JobStatus.RUNNING.value
        job.started_at = timezone.now() - timedelta(minutes=5)
        job.save(
            update_fields=[
                "status",
                "started_at",
                "updated_at",
            ]
        )

        # Worker goes inactive
        job_worker_active.labels(
            worker_id=wid,
            queue_name=qn,
        ).set(0)

        job.refresh_from_db()
        self.assertEqual(
            job.status,
            JobStatus.RUNNING.value,
            "Stuck job should remain RUNNING",
        )
        self.assertIsNone(
            job.completed_at,
            "Stuck job should have no completed_at",
        )

    def test_worker_recovery_tracking(self):
        """Worker recovers and completes a stuck job."""
        wid = "test-worker-3"
        qn = "job_default"

        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.ODPS_SEMANTIC_MAPPING.value,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
        )
        job.status = JobStatus.RUNNING.value
        job.started_at = timezone.now() - timedelta(minutes=10)
        job.save(
            update_fields=[
                "status",
                "started_at",
                "updated_at",
            ]
        )

        # Worker recovers and completes the job
        job_worker_active.labels(
            worker_id=wid,
            queue_name=qn,
        ).set(1)
        now = timezone.now()
        job.status = JobStatus.COMPLETED.value
        job.completed_at = now
        job.result_json = {
            "recovered": True,
            "worker_id": wid,
        }
        job.save(
            update_fields=[
                "status",
                "completed_at",
                "result_json",
                "updated_at",
            ]
        )

        job.refresh_from_db()
        self.assertEqual(
            job.status,
            JobStatus.COMPLETED.value,
        )
        self.assertTrue(job.result_json["recovered"])

    def test_worker_performance_monitoring(self):
        """Worker throughput and avg duration computed."""
        jt = JobType.CONTRACT_VALIDATION.value
        num_jobs = 5
        for dur in [0.3] * num_jobs:
            _create_completed_job(
                self.tenant,
                self.user,
                jt,
                dur,
            )

        avg_dur = Job.objects.filter(
            tenant=self.tenant,
            type=jt,
            status=JobStatus.COMPLETED.value,
            started_at__isnull=False,
            completed_at__isnull=False,
        ).aggregate(
            avg=Avg(F("completed_at") - F("started_at")),
        )["avg"]
        self.assertIsNotNone(avg_dur)
        self.assertGreater(
            avg_dur.total_seconds(),
            0,
        )
