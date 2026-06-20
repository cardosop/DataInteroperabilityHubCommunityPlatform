"""
285.10.3.4.2 — Tests for warehouse compliance service.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.integration
class TestRunWarehouseCompliance(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"c-{uid}",
            slug=f"c-{uid}",
            status="ACTIVE",
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com",
            password="testpass",
            tenant=self.tenant,
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            storage_path=f"tests/{uuid.uuid4().hex}.csv",
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_rejects_non_warehouse_scan_mode(self):
        from hub.apps.compliance.services import ComplianceService
        from hub.apps.core.services.base import ValidationError

        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            scan_mode="FILE_SCAN",
            status=ComplianceRunStatus.PENDING,
        )
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        with self.assertRaises(ValidationError) as ctx:
            svc.run_warehouse_compliance(run_id=str(run.id))
        self.assertEqual(ctx.exception.code, "WAREHOUSE_SCAN_MODE_REQUIRED")

    @pytest.mark.integration
    def test_returns_job_id_pending(self):
        from hub.apps.compliance.services import ComplianceService

        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.PENDING,
            warehouse_config={"table_fqn": "DB.S.T", "warehouse_type": "snowflake"},
        )
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        result = svc.run_warehouse_compliance(run_id=str(run.id))
        self.assertIn("job_id", result)
        self.assertEqual(result["status"], "QUEUED")

    @pytest.mark.integration
    def test_rejects_non_pending_status(self):
        """A SUCCEEDED run is terminal — dispatch must be rejected."""
        from hub.apps.compliance.services import ComplianceService
        from hub.apps.core.services.base import ValidationError

        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.SUCCEEDED,
            warehouse_config={"table_fqn": "DB.S.T", "warehouse_type": "snowflake"},
        )
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        with self.assertRaises(ValidationError) as ctx:
            svc.run_warehouse_compliance(run_id=str(run.id))
        self.assertEqual(ctx.exception.code, "COMPLIANCE_RUN_NOT_DISPATCHABLE")

    @pytest.mark.integration
    def test_accepts_queued_status(self):
        """A QUEUED run should be dispatchable per the implementation."""
        from hub.apps.compliance.services import ComplianceService

        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.QUEUED,
            warehouse_config={"table_fqn": "DB.S.T", "warehouse_type": "snowflake"},
        )
        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        result = svc.run_warehouse_compliance(run_id=str(run.id))
        self.assertIn("job_id", result)

    @pytest.mark.integration
    def test_invalid_run_id_raises_not_found(self):
        """A non-existent run_id must raise NotFoundError."""
        from hub.apps.compliance.services import ComplianceService
        from hub.apps.core.services.base import NotFoundError

        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        with self.assertRaises(NotFoundError):
            svc.run_warehouse_compliance(run_id=str(uuid.uuid4()))


@pytest.mark.integration
class TestScanInmemoryWarehouse(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"cs-{uid}",
            slug=f"cs-{uid}",
            status="ACTIVE",
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            format="CSV",
            kind="EXTERNAL_REF",
        )

    @pytest.mark.integration
    def test_creates_run_with_warehouse_mode(self):
        from hub.apps.compliance.services import ComplianceService

        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            dataset=self.dataset,
            tenant=self.tenant,
            warehouse_config={
                "table_fqn": "T",
                "warehouse_type": "snowflake",
                "checks": [
                    {"type": "pii_email", "column": "email"},
                ],
            },
        )
        self.assertEqual(run.scan_mode, "WAREHOUSE_SQL")
        self.assertIn(run.status, (ComplianceRunStatus.SUCCEEDED, ComplianceRunStatus.FAILED))

    @pytest.mark.integration
    def test_terminal_status(self):
        from hub.apps.compliance.services import ComplianceService

        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            dataset=self.dataset,
            tenant=self.tenant,
            warehouse_config={
                "table_fqn": "T",
                "warehouse_type": "snowflake",
                "checks": [],
            },
        )
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.completed_at)

    @pytest.mark.integration
    def test_empty_checks_succeeds(self):
        from hub.apps.compliance.services import ComplianceService

        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            dataset=self.dataset,
            tenant=self.tenant,
            warehouse_config={
                "table_fqn": "T",
                "warehouse_type": "snowflake",
            },
        )
        self.assertEqual(run.status, ComplianceRunStatus.SUCCEEDED)

    @pytest.mark.integration
    def test_policy_evaluation_sets_allowed_to_store(self):
        from hub.apps.compliance.services import ComplianceService

        svc = ComplianceService(tenant_id=str(self.tenant.id), user_id=None)
        run = svc.scan_inmemory_warehouse(
            dataset=self.dataset,
            tenant=self.tenant,
            warehouse_config={
                "table_fqn": "T",
                "warehouse_type": "snowflake",
                "checks": [
                    {"type": "pii_ssn", "column": "ssn"},
                ],
            },
        )
        self.assertIsNotNone(run.allowed_to_store)
        # Fail-closed: when the warehouse is unavailable the run should
        # be marked with allowed_to_store=False to block intake.
        self.assertFalse(
            run.allowed_to_store,
            "Fail-closed: allowed_to_store must be False when warehouse is "
            "unavailable (scan_inmemory_warehouse exception handler sets it)",
        )
