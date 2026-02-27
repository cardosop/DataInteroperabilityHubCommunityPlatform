"""
Integration tests for tenant_id propagation from Hub to compliance-service (5.3.2).

When Hub runs a file scan (execute_compliance_run), it must pass tenant_id to the
compliance-service. The compliance-service accepts it and uses it in metrics/logging.
Tests use real Hub + compliance-service path; no mocks. Run with docker-compose.test
so compliance-service is available.
"""

import time
import uuid

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.compliance.views import execute_compliance_run
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

try:
    import httpx
except ImportError:
    httpx = None

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantPropagationIntegrationTest(TestCase):
    """Verify Hub passes tenant_id to compliance-service and it appears in metrics."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Tenant Propagation Test",
            slug="tenant-propagation-test",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email="propagation@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            tenant=self.tenant,
            name="small.csv",
            content_type="text/csv",
            size=64,
            storage_path=f"{self.tenant.id}/{file_id}/small.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        self._setup_test_file_content()
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            timeout_seconds=1800,
            details_json={"scan_mode": "internal", "applicable_regulations": []},
        )

    def _setup_test_file_content(self):
        max_attempts = 6
        delay_seconds = 3
        for attempt in range(max_attempts):
            try:
                storage_client = S3StorageClient()
                storage_client._ensure_bucket_exists()
                storage_client.upload_file(
                    file_path=self.file.storage_path,
                    file_content=b"a,b\n1,2\n3,4",
                    content_type="text/csv",
                )
                self.storage_available = True
                return
            except Exception:
                if attempt < max_attempts - 1:
                    time.sleep(delay_seconds)
                    continue
                self.storage_available = False

    def test_hub_file_scan_sends_tenant_id_compliance_service_receives_in_metrics(self):
        """
        Hub file scan with tenant A → compliance-service receives tenant_id (e.g. metrics).
        Real Hub + compliance-service; no mocks in this path.
        """
        if not getattr(self, "storage_available", False):
            self.skipTest("Storage not available - requires real storage for file content")

        client = ComplianceServiceClient()
        try:
            is_healthy, _ = client.health_check()
            if not is_healthy:
                self.skipTest("Compliance service not available - run with docker-compose.test")
        except Exception:
            self.skipTest("Compliance service not available - run with docker-compose.test")

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
        )
        execute_compliance_run(str(compliance_run.id))

        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.SUCCEEDED)

        # Compliance-service must have received tenant_id; it appears in Prometheus metrics
        base_url = getattr(client, "base_url", None) or getattr(
            settings, "COMPLIANCE_SERVICE_URL", "http://localhost:8082"
        )
        if base_url.endswith("/"):
            base_url = base_url.rstrip("/")
        metrics_url = f"{base_url}/metrics"

        if httpx is None:
            self.skipTest("httpx not available to fetch compliance-service metrics")

        try:
            with httpx.Client(timeout=10.0) as http_client:
                response = http_client.get(metrics_url)
        except Exception as e:
            self.skipTest(f"Cannot reach compliance-service metrics: {e}")

        self.assertEqual(response.status_code, 200, "compliance-service /metrics should be reachable")
        metrics_text = response.text
        tenant_uuid = str(self.tenant.id)
        # Prometheus format: compliance_runs_total{...,tenant_id="<uuid>"} ...
        self.assertIn(
            f'tenant_id="{tenant_uuid}"',
            metrics_text,
            "compliance_runs_total (or similar) should include tenant_id from Hub",
        )
        self.assertIn(
            "compliance_runs_total",
            metrics_text,
            "compliance-service should expose compliance_runs_total",
        )
