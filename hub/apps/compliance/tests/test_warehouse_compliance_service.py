"""
285.10.3.4.2 — Tests for warehouse compliance service.
"""
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.integration
class TestRunWarehouseCompliance(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name=f"c-{uuid.uuid4().hex[:8]}", slug=f"c-{uuid.uuid4().hex[:8]}",
        )
        cls.user = User.objects.create_user(
            email=f"u-{uuid.uuid4().hex[:8]}@test.com",
            password="testpass",
        )
        cls.file = File.objects.create(
            tenant=cls.tenant,
            name="test.csv",
            size=1024,
            storage_path=f"tests/{uuid.uuid4().hex}.csv",
            created_by=cls.user,
        )

    @pytest.mark.integration
    def test_rejects_non_warehouse_scan_mode(self):
        from hub.apps.compliance.services import ComplianceService
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            scan_mode="file_scan",
            status=ComplianceRunStatus.PENDING,
        )
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        with self.assertRaises(Exception):
            svc.run_warehouse_compliance(run_id=str(run.id))

    @pytest.mark.integration
    def test_returns_job_id_pending(self):
        from hub.apps.compliance.services import ComplianceService
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            scan_mode="warehouse_sql",
            status=ComplianceRunStatus.PENDING,
            warehouse_config={"table_fqn": "DB.S.T", "warehouse_type": "snowflake"},
        )
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        result = svc.run_warehouse_compliance(run_id=str(run.id))
        self.assertIn("job_id", result)
        self.assertEqual(result["status"], "PENDING")


@pytest.mark.integration
class TestScanInmemoryWarehouse(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name=f"cs-{uuid.uuid4().hex[:8]}", slug=f"cs-{uuid.uuid4().hex[:8]}",
        )

    @pytest.mark.integration
    def test_creates_run_with_warehouse_mode(self):
        from hub.apps.compliance.services import ComplianceService
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            warehouse_config={"table_fqn": "T", "checks": [
                {"type": "pii_email", "column": "email"},
            ]}, tenant_id=str(self.tenant.id),
        )
        self.assertEqual(run.scan_mode, "warehouse_sql")
        self.assertIn(run.status, (ComplianceRunStatus.SUCCEEDED, ComplianceRunStatus.FAILED))

    @pytest.mark.integration
    def test_terminal_status(self):
        from hub.apps.compliance.services import ComplianceService
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            warehouse_config={"table_fqn": "T", "checks": []}, tenant_id=str(self.tenant.id),
        )
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.completed_at)

    @pytest.mark.integration
    def test_empty_checks_succeeds(self):
        from hub.apps.compliance.services import ComplianceService
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            warehouse_config={"table_fqn": "T"}, tenant_id=str(self.tenant.id),
        )
        self.assertEqual(run.status, ComplianceRunStatus.SUCCEEDED)

    @pytest.mark.integration
    def test_policy_evaluation_sets_allowed_to_store(self):
        from hub.apps.compliance.services import ComplianceService
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            warehouse_config={"table_fqn": "T", "checks": [
                {"type": "pii_ssn", "column": "ssn"},
            ]}, tenant_id=str(self.tenant.id),
        )
        self.assertIsNotNone(run.allowed_to_store)
