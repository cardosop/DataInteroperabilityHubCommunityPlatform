"""
Unit tests for Prometheus metrics collection

Tests verify that metrics are incremented correctly and labels are set properly.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from prometheus_client import REGISTRY

from hub.apps.observability.otel_metrics import (
    compliance_runs_total,
    contract_validations_total,
    dq_runs_total,
    http_errors_total,
    http_request_duration_seconds,
    http_requests_total,
    job_duration_seconds,
    jobs_completed_total,
    jobs_failed_total,
    jobs_started_total,
)
from hub.apps.tenants.models import KYCStatus, Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MetricsCollectionTest(TestCase):
    """Test metrics collection and labeling"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(email=f"test-{uid}@example.com", tenant=self.tenant)

    def test_http_metrics_incremented(self):
        """Test that HTTP request counter increments correctly"""
        labeled = http_requests_total.labels(
            method="GET", route="/health/", status_class="2xx"
        )
        before = labeled._value.get()
        labeled.inc()
        after = labeled._value.get()
        self.assertEqual(after, before + 1, "HTTP counter did not increment")

    def test_http_metrics_labels(self):
        """Test that HTTP metrics have correct labels"""
        # Verify metric has expected labels
        labels = http_requests_total._labelnames
        self.assertIn("method", labels)
        self.assertIn("route", labels)
        self.assertIn("status_class", labels)

    def test_http_duration_metrics(self):
        """Test that HTTP duration metrics are recorded"""
        self.assertIsNotNone(http_request_duration_seconds)

        labels = http_request_duration_seconds._labelnames
        self.assertIn("method", labels)
        self.assertIn("route", labels)
        self.assertIn("status_class", labels)

        labeled = http_request_duration_seconds.labels(
            method="GET", route="/health/", status_class="2xx"
        )
        before_count = labeled._value.get()
        labeled.observe(0.1)
        after_count = labeled._value.get()
        self.assertGreater(after_count, before_count, "Duration metric was not recorded")

    def test_http_error_metrics(self):
        """Test that HTTP error metrics are incremented"""
        self.assertIsNotNone(http_errors_total)

        labels = http_errors_total._labelnames
        self.assertIn("method", labels)
        self.assertIn("route", labels)
        self.assertIn("status_code", labels)

        labeled = http_errors_total.labels(method="GET", route="/nonexistent/", status_code=404)
        before = labeled._value.get()
        labeled.inc()
        self.assertEqual(labeled._value.get(), before + 1)

    def test_job_metrics_labels(self):
        """Test that job metrics have correct labels"""
        tenant_id = str(self.tenant.id)

        # Test jobs_started_total
        labels = jobs_started_total._labelnames
        self.assertIn("job_type", labels)
        self.assertIn("tenant_id", labels)

        # Test jobs_completed_total
        labels = jobs_completed_total._labelnames
        self.assertIn("job_type", labels)
        self.assertIn("status", labels)
        self.assertIn("tenant_id", labels)

        # Test jobs_failed_total
        labels = jobs_failed_total._labelnames
        self.assertIn("job_type", labels)
        self.assertIn("error_code", labels)
        self.assertIn("tenant_id", labels)

    def test_job_metrics_incremented(self):
        """Test that job metrics are incremented correctly"""
        tenant_id = str(self.tenant.id)

        labeled = jobs_started_total.labels(job_type="DQ_RUN", tenant_id=tenant_id)
        before = labeled._value.get()
        labeled.inc()
        self.assertEqual(labeled._value.get(), before + 1)

        labeled2 = jobs_completed_total.labels(job_type="DQ_RUN", status="COMPLETED", tenant_id=tenant_id)
        before2 = labeled2._value.get()
        labeled2.inc()
        self.assertEqual(labeled2._value.get(), before2 + 1)

        labeled3 = jobs_failed_total.labels(job_type="DQ_RUN", error_code="TIMEOUT", tenant_id=tenant_id)
        before3 = labeled3._value.get()
        labeled3.inc()
        self.assertEqual(labeled3._value.get(), before3 + 1)

    def test_job_duration_metrics(self):
        """Test that job duration metrics are recorded"""
        self.assertIsNotNone(job_duration_seconds)

        labels = job_duration_seconds._labelnames
        self.assertIn("job_type", labels)
        self.assertIn("status", labels)

        labeled = job_duration_seconds.labels(job_type="DQ_RUN", status="COMPLETED")
        before = labeled._value.get()
        labeled.observe(10.5)
        after = labeled._value.get()
        self.assertGreater(after, before, "Job duration metric was not recorded")

    def test_dq_metrics_labels(self):
        """Test that DQ metrics have correct labels"""
        tenant_id = str(self.tenant.id)

        labels = dq_runs_total._labelnames
        self.assertIn("status", labels)
        self.assertIn("engine", labels)
        self.assertIn("tenant_id", labels)

        labeled = dq_runs_total.labels(
            status="success", engine="great_expectations", tenant_id=tenant_id
        )
        before = labeled._value.get()
        labeled.inc()
        self.assertEqual(labeled._value.get(), before + 1)

    def test_compliance_metrics_labels(self):
        """Test that compliance metrics have correct labels"""
        tenant_id = str(self.tenant.id)

        labels = compliance_runs_total._labelnames
        self.assertIn("status", labels)
        self.assertIn("risk_level", labels)
        self.assertIn("tenant_id", labels)

        labeled = compliance_runs_total.labels(status="success", risk_level="low", tenant_id=tenant_id)
        before = labeled._value.get()
        labeled.inc()
        self.assertEqual(labeled._value.get(), before + 1)

    def test_contract_validation_metrics_labels(self):
        """Test that contract validation metrics have correct labels"""
        tenant_id = str(self.tenant.id)

        labels = contract_validations_total._labelnames
        self.assertIn("status", labels)
        self.assertIn("spec_type", labels)
        self.assertIn("tenant_id", labels)

        labeled = contract_validations_total.labels(
            status="valid", spec_type="DATACONTRACT_COM", tenant_id=tenant_id
        )
        before = labeled._value.get()
        labeled.inc()
        self.assertEqual(labeled._value.get(), before + 1)

    def test_per_tenant_metrics_isolation(self):
        """Test that per-tenant metrics are isolated"""
        tenant1 = Tenant.objects.create(
            name="Tenant 1", slug="tenant-1", kyc_status=KYCStatus.VERIFIED
        )
        tenant2 = Tenant.objects.create(
            name="Tenant 2", slug="tenant-2", kyc_status=KYCStatus.VERIFIED
        )

        tenant1_id = str(tenant1.id)
        tenant2_id = str(tenant2.id)

        # Increment metrics for tenant 1
        jobs_started_total.labels(job_type="DQ_RUN", tenant_id=tenant1_id).inc()

        # Increment metrics for tenant 2
        jobs_started_total.labels(job_type="DQ_RUN", tenant_id=tenant2_id).inc()

        # Verify both metrics exist (they should be separate)
        metric1 = jobs_started_total.labels(job_type="DQ_RUN", tenant_id=tenant1_id)
        metric2 = jobs_started_total.labels(job_type="DQ_RUN", tenant_id=tenant2_id)

        self.assertIsNotNone(metric1)
        self.assertIsNotNone(metric2)
        # They should be different metric instances
        self.assertNotEqual(id(metric1), id(metric2))
