"""
Unit tests for Scheduled Export Models

Tests model creation, validation, tenant scope, and relationships.
Uses real database - no mocks.
"""

import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.scheduled_export.models import (
    DestinationType,
    ExportRunCost,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class ScheduledExportModelTest(TestCase):
    """Test ScheduledExport model creation, validation, and tenant scope"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        self.other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

    def test_create_scheduled_export_success(self):
        """Test successful scheduled export creation"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Daily Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "my-bucket",
                "prefix": "exports/",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret...",
            },
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        self.assertIsNotNone(export.id)
        self.assertEqual(export.tenant, self.tenant)
        self.assertEqual(export.name, "Daily Export")
        self.assertEqual(export.destination_type, DestinationType.S3)
        self.assertEqual(export.status, ScheduledExportStatus.ACTIVE)
        self.assertIsNotNone(export.next_run_at)
        self.assertIsNotNone(export.created_at)
        self.assertIsNotNone(export.updated_at)

    def test_create_scheduled_export_with_dataset_ids(self):
        """Test creating scheduled export with dataset_ids in source_scope"""
        dataset_id1 = str(uuid.uuid4())
        dataset_id2 = str(uuid.uuid4())
        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Dataset Export",
            schedule_config={"cron": "0 2 * * *", "timezone": "UTC"},
            destination_type=DestinationType.GCS,
            destination_config={"bucket": "my-gcs-bucket", "credentials": "encrypted..."},
            source_scope={"dataset_ids": [dataset_id1, dataset_id2]},
        )

        self.assertEqual(export.source_scope["dataset_ids"], [dataset_id1, dataset_id2])

    def test_create_scheduled_export_with_file_ids(self):
        """Test creating scheduled export with file_ids in source_scope"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="File Export",
            schedule_config={"cron": "0 3 * * *", "timezone": "UTC"},
            destination_type=DestinationType.AZURE_BLOB,
            destination_config={
                "container": "exports",
                "account_name": "myaccount",
                "account_key": "encrypted...",
            },
            source_scope={"file_ids": [str(uuid.uuid4())]},
        )

        self.assertIn("file_ids", export.source_scope)

    def test_create_scheduled_export_with_contract_id(self):
        """Test creating scheduled export with contract_id in source_scope"""
        contract_id = str(uuid.uuid4())
        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Contract Export",
            schedule_config={"cron": "0 4 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"contract_id": contract_id},
        )

        self.assertEqual(export.source_scope["contract_id"], contract_id)

    def test_create_scheduled_export_unique_name_per_tenant(self):
        """Test that export names are unique per tenant"""
        ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Unique Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        # Same tenant, same name should fail (full_clean validates UniqueConstraint)
        with self.assertRaises(ValidationError) as cm:
            ScheduledExport.objects.create(
                tenant=self.tenant,
                name="Unique Export",
                schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
                destination_type=DestinationType.S3,
                destination_config={"bucket": "my-bucket"},
                source_scope={"asset_ids": [str(uuid.uuid4())]},
            )
        self.assertIn("name", str(cm.exception).lower())

        # Different tenant, same name should succeed
        export2 = ScheduledExport.objects.create(
            tenant=self.other_tenant,
            name="Unique Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        self.assertIsNotNone(export2.id)

    def test_scheduled_export_validation_invalid_cron(self):
        """Test validation fails with invalid cron expression"""
        with self.assertRaises(ValidationError):
            export = ScheduledExport(
                tenant=self.tenant,
                name="Invalid Cron Export",
                schedule_config={"cron": "invalid cron", "timezone": "UTC"},
                destination_type=DestinationType.S3,
                destination_config={"bucket": "my-bucket"},
                source_scope={"asset_ids": [str(uuid.uuid4())]},
            )
            export.full_clean()

    def test_scheduled_export_validation_missing_cron(self):
        """Test validation fails when cron is missing"""
        with self.assertRaises(ValidationError):
            export = ScheduledExport(
                tenant=self.tenant,
                name="Missing Cron Export",
                schedule_config={"timezone": "UTC"},
                destination_type=DestinationType.S3,
                destination_config={"bucket": "my-bucket"},
                source_scope={"asset_ids": [str(uuid.uuid4())]},
            )
            export.full_clean()

    def test_scheduled_export_validation_empty_source_scope(self):
        """Test validation fails when source_scope is empty"""
        with self.assertRaises(ValidationError):
            export = ScheduledExport(
                tenant=self.tenant,
                name="Empty Scope Export",
                schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
                destination_type=DestinationType.S3,
                destination_config={"bucket": "my-bucket"},
                source_scope={},
            )
            export.full_clean()

    def test_scheduled_export_validation_invalid_source_scope_type(self):
        """Test validation fails when source_scope is not a dict"""
        with self.assertRaises(ValidationError):
            export = ScheduledExport(
                tenant=self.tenant,
                name="Invalid Scope Export",
                schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
                destination_type=DestinationType.S3,
                destination_config={"bucket": "my-bucket"},
                source_scope="not a dict",
            )
            export.full_clean()

    def test_scheduled_export_validation_invalid_destination_config_type(self):
        """Test validation fails when destination_config is not a dict"""
        with self.assertRaises(ValidationError):
            export = ScheduledExport(
                tenant=self.tenant,
                name="Invalid Config Export",
                schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
                destination_type=DestinationType.S3,
                destination_config="not a dict",
                source_scope={"asset_ids": [str(uuid.uuid4())]},
            )
            export.full_clean()

    def test_scheduled_export_tenant_filtering(self):
        """Test tenant-scoped queries"""
        export1 = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Tenant1 Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        export2 = ScheduledExport.objects.create(
            tenant=self.other_tenant,
            name="Tenant2 Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        # Filter by tenant
        tenant1_exports = ScheduledExport.objects.filter(tenant=self.tenant)
        self.assertEqual(tenant1_exports.count(), 1)
        self.assertEqual(tenant1_exports.first(), export1)

        tenant2_exports = ScheduledExport.objects.filter(tenant=self.other_tenant)
        self.assertEqual(tenant2_exports.count(), 1)
        self.assertEqual(tenant2_exports.first(), export2)

    def test_scheduled_export_status_choices(self):
        """Test status field accepts valid choices"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Status Test Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
            status=ScheduledExportStatus.PAUSED,
        )

        self.assertEqual(export.status, ScheduledExportStatus.PAUSED)

        export.status = ScheduledExportStatus.ERROR
        export.save()
        self.assertEqual(export.status, ScheduledExportStatus.ERROR)

    def test_scheduled_export_next_run_at_calculation(self):
        """Test next_run_at is calculated on creation"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Next Run Test Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        self.assertIsNotNone(export.next_run_at)
        self.assertGreater(export.next_run_at, timezone.now())

    def test_scheduled_export_str_representation(self):
        """Test string representation"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="String Test Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        self.assertIn("String Test Export", str(export))
        self.assertIn(self.tenant.name, str(export))


class ScheduledExportRunModelTest(TestCase):
    """Test ScheduledExportRun model creation, validation, and tenant scope"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Test Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

    def test_create_scheduled_export_run_success(self):
        """Test successful scheduled export run creation"""
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            items_found=10,
            items_exported=0,
            items_failed=0,
            started_at=timezone.now(),
        )

        self.assertIsNotNone(run.id)
        self.assertEqual(run.scheduled_export, self.scheduled_export)
        self.assertEqual(run.tenant, self.tenant)
        self.assertEqual(run.status, ScheduledExportRunStatus.RUNNING)
        self.assertEqual(run.items_found, 10)
        self.assertEqual(run.items_exported, 0)
        self.assertEqual(run.items_failed, 0)
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.created_at)

    def test_create_scheduled_export_run_completed(self):
        """Test creating completed export run"""
        started_at = timezone.now() - timedelta(hours=1)
        completed_at = timezone.now()

        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=100,
            items_exported=100,
            items_failed=0,
            started_at=started_at,
            completed_at=completed_at,
            result_json={
                "items_exported": 100,
                "destination": "s3://my-bucket/exports/2024-01-01/",
                "files_created": ["file1.csv", "file2.csv"],
            },
        )

        self.assertEqual(run.status, ScheduledExportRunStatus.COMPLETED)
        self.assertEqual(run.items_exported, 100)
        self.assertIsNotNone(run.completed_at)
        self.assertIn("items_exported", run.result_json)

    def test_create_scheduled_export_run_failed(self):
        """Test creating failed export run"""
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.FAILED,
            items_found=50,
            items_exported=30,
            items_failed=20,
            started_at=timezone.now() - timedelta(minutes=30),
            completed_at=timezone.now(),
            result_json={
                "error": "Connection timeout",
                "items_failed_details": [{"item_id": str(uuid.uuid4()), "error": "Timeout"}],
            },
        )

        self.assertEqual(run.status, ScheduledExportRunStatus.FAILED)
        self.assertEqual(run.items_failed, 20)
        self.assertIn("error", run.result_json)

    def test_create_scheduled_export_run_with_prefect_flow_run_id(self):
        """Test creating export run with Prefect flow run ID"""
        prefect_flow_run_id = "prefect-flow-run-12345"
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            items_found=10,
            prefect_flow_run_id=prefect_flow_run_id,
        )

        self.assertEqual(run.prefect_flow_run_id, prefect_flow_run_id)

    def test_scheduled_export_run_tenant_filtering(self):
        """Test tenant-scoped queries for runs"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        other_export = ScheduledExport.objects.create(
            tenant=other_tenant,
            name="Other Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "other-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        run1 = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=10,
            items_exported=10,
        )

        run2 = ScheduledExportRun.objects.create(
            scheduled_export=other_export,
            tenant=other_tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=20,
            items_exported=20,
        )

        # Filter by tenant
        tenant1_runs = ScheduledExportRun.objects.filter(tenant=self.tenant)
        self.assertEqual(tenant1_runs.count(), 1)
        self.assertEqual(tenant1_runs.first(), run1)

        tenant2_runs = ScheduledExportRun.objects.filter(tenant=other_tenant)
        self.assertEqual(tenant2_runs.count(), 1)
        self.assertEqual(tenant2_runs.first(), run2)

    def test_scheduled_export_run_relationship(self):
        """Test relationship between ScheduledExport and ScheduledExportRun"""
        run1 = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=10,
            items_exported=10,
        )

        run2 = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=20,
            items_exported=20,
        )

        # Access runs from export
        runs = self.scheduled_export.runs.all()
        self.assertEqual(runs.count(), 2)
        self.assertIn(run1, runs)
        self.assertIn(run2, runs)

    def test_scheduled_export_run_str_representation(self):
        """Test string representation"""
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            items_found=10,
        )

        self.assertIn(str(run.id), str(run))
        self.assertIn(self.scheduled_export.name, str(run))


class ExportRunCostModelTest(TestCase):
    """Test ExportRunCost model creation, validation, and tenant scope"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Test Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "my-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        self.export_run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=100,
            items_exported=100,
            items_failed=0,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
        )

    def test_create_export_run_cost_success(self):
        """Test successful export run cost creation"""
        cost = ExportRunCost.objects.create(
            run=self.export_run,
            tenant=self.tenant,
            cost_components={
                "storage": {"cost_usd": 0.50, "size_gb": 10},
                "compute": {"cost_usd": 0.25, "hours": 1.0},
                "network": {"cost_usd": 0.15, "data_transfer_gb": 5},
                "total_cost_usd": 0.90,
            },
        )

        self.assertIsNotNone(cost.id)
        self.assertEqual(cost.run, self.export_run)
        self.assertEqual(cost.tenant, self.tenant)
        self.assertIn("storage", cost.cost_components)
        self.assertIn("compute", cost.cost_components)
        self.assertIn("network", cost.cost_components)
        self.assertIsNotNone(cost.calculated_at)
        self.assertIsNotNone(cost.created_at)

    def test_export_run_cost_tenant_filtering(self):
        """Test tenant-scoped queries for costs"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        other_export = ScheduledExport.objects.create(
            tenant=other_tenant,
            name="Other Export",
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "other-bucket"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

        other_run = ScheduledExportRun.objects.create(
            scheduled_export=other_export,
            tenant=other_tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=50,
            items_exported=50,
        )

        cost1 = ExportRunCost.objects.create(
            run=self.export_run, tenant=self.tenant, cost_components={"total_cost_usd": 0.90}
        )

        cost2 = ExportRunCost.objects.create(
            run=other_run, tenant=other_tenant, cost_components={"total_cost_usd": 0.45}
        )

        # Filter by tenant
        tenant1_costs = ExportRunCost.objects.filter(tenant=self.tenant)
        self.assertEqual(tenant1_costs.count(), 1)
        self.assertEqual(tenant1_costs.first(), cost1)

        tenant2_costs = ExportRunCost.objects.filter(tenant=other_tenant)
        self.assertEqual(tenant2_costs.count(), 1)
        self.assertEqual(tenant2_costs.first(), cost2)

    def test_export_run_cost_relationship(self):
        """Test relationship between ScheduledExportRun and ExportRunCost"""
        cost1 = ExportRunCost.objects.create(
            run=self.export_run, tenant=self.tenant, cost_components={"total_cost_usd": 0.50}
        )

        cost2 = ExportRunCost.objects.create(
            run=self.export_run, tenant=self.tenant, cost_components={"total_cost_usd": 0.75}
        )

        # Access costs from run
        costs = self.export_run.costs.all()
        self.assertEqual(costs.count(), 2)
        self.assertIn(cost1, costs)
        self.assertIn(cost2, costs)

    def test_export_run_cost_str_representation(self):
        """Test string representation"""
        cost = ExportRunCost.objects.create(
            run=self.export_run, tenant=self.tenant, cost_components={"total_cost_usd": 0.90}
        )

        self.assertIn(str(self.export_run.id), str(cost))

    def test_export_run_cost_default_values(self):
        """Test default values for cost components"""
        cost = ExportRunCost.objects.create(run=self.export_run, tenant=self.tenant)

        self.assertEqual(cost.cost_components, {})
        self.assertIsNotNone(cost.calculated_at)
